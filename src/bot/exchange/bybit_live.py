"""Bybit live adapter wrapping pybit unified_trading (REST + WebSocket).

Strategy code only sees the ExchangeAdapter ABC. This file does the dirty
work: thread-bridging pybit's sync WS callbacks into asyncio queues, mapping
WS payloads to our event dataclasses, and rate-limiting REST.
"""

from __future__ import annotations

import asyncio
import errno
import socket
import time
from collections.abc import AsyncIterator
from decimal import Decimal, ROUND_DOWN
from typing import Any

from aiolimiter import AsyncLimiter

from bot.exchange.base import ExchangeAdapter, UserEvent
from bot.logger import get_logger
from bot.models import (
    Candle,
    ExecutionEvent,
    Instrument,
    Order,
    OrderAck,
    OrderEvent,
    OrderPurpose,
    Position,
    PositionEvent,
    Side,
)

log = get_logger(__name__)

CATEGORY = "linear"


def _record_rest_latency(op: str, t0: float, **fields: Any) -> None:
    """Record REST round-trip latency. Never raises — instrumentation must not break orders."""
    try:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        log.info("bybit.rest.latency", op=op, ms=round(elapsed_ms, 2), **fields)
    except Exception:
        pass


def _record_ws_event_age(kind: str, server_ts_ms: Any, **fields: Any) -> None:
    """Record WS event age = local_recv - server_emit. Never raises."""
    try:
        if not server_ts_ms:
            return
        age_ms = (time.time() * 1000.0) - float(server_ts_ms)
        log.info("bybit.ws.event_age", kind=kind, ms=round(age_ms, 2), **fields)
    except Exception:
        pass


def _floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def _format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


# Public 1m klines push at least once per minute, so silence past
# PUBLIC_WS_STALE_SECONDS is treated as a real socket problem (status
# becomes "stale" and the public loop reconnects). Private executions are
# sparse and quiet account stretches are normal: while the thread is alive,
# we surface that as "connected_idle" rather than "stale" to avoid false
# alarms on flat trading days.
PUBLIC_WS_STALE_SECONDS = 120.0
PRIVATE_WS_STALE_SECONDS = 900.0
WS_CONNECT_TIMEOUT_SECONDS = 15.0
WS_HEALTH_CHECK_SECONDS = 30.0
WS_RECONNECT_BASE_SECONDS = 2.0
WS_RECONNECT_MAX_SECONDS = 60.0
WS_WARNING_THROTTLE_SECONDS = 300.0

_PYBIT_WS_TIMEOUT_PATCHED = False
_WEBSOCKET_IPV4_PATCHED = False
_WS_WARNING_LAST_TS: dict[tuple[str, str], float] = {}


def _is_ws_timeout_error(error: BaseException) -> bool:
    if isinstance(error, (TimeoutError, socket.timeout)):
        return True
    if isinstance(error, OSError) and getattr(error, "errno", None) == errno.ETIMEDOUT:
        return True
    return "timed out" in str(error).lower()


def _log_ws_warning(event: str, *, key: str, **fields: Any) -> None:
    now = time.time()
    cache_key = (event, key)
    last = _WS_WARNING_LAST_TS.get(cache_key)
    if last is not None and now - last < WS_WARNING_THROTTLE_SECONDS:
        return
    _WS_WARNING_LAST_TS[cache_key] = now
    log.warning(event, **fields)


def _patch_pybit_ws_timeout_errors() -> None:
    """Treat raw socket timeouts from websocket-client as pybit reconnectable errors.

    pybit handles WebSocketTimeoutException, but macOS can surface Errno 60 as
    TimeoutError/OSError from websocket-client's callback. The stock pybit
    handler re-raises those as callback errors, which kills the socket thread.
    """
    global _PYBIT_WS_TIMEOUT_PATCHED
    if _PYBIT_WS_TIMEOUT_PATCHED:
        return

    from pybit import _websocket_stream

    original = _websocket_stream._WebSocketManager._on_error

    def _on_error(self, error):  # type: ignore[no-untyped-def]
        if not _is_ws_timeout_error(error):
            return original(self, error)

        if not self.exited:
            _log_ws_warning(
                "pybit_ws_timeout",
                key=f"{self.ws_name}:{self.endpoint}",
                ws_name=self.ws_name,
                endpoint=self.endpoint,
                error=str(error),
            )
            self.exit()

        if self.handle_error and not self.attempting_connection:
            self._reset()
            self._connect(self.endpoint)

    _websocket_stream._WebSocketManager._on_error = _on_error
    _PYBIT_WS_TIMEOUT_PATCHED = True


def _patch_websocket_bybit_ipv4_preference() -> None:
    """Prefer IPv4 for Bybit websocket hosts.

    On this deployment, Bybit stream hosts resolve IPv6 records first, and
    websocket-client can hang on that IPv6 path instead of falling through to
    IPv4. Curl and websocket-client forced to IPv4 connect immediately.
    """
    global _WEBSOCKET_IPV4_PATCHED
    if _WEBSOCKET_IPV4_PATCHED:
        return

    import websocket._http

    original = websocket._http._get_addrinfo_list

    def _get_addrinfo_list(hostname, port: int, is_secure: bool, proxy):  # type: ignore[no-untyped-def]
        addrinfo_list, need_tunnel, auth = original(hostname, port, is_secure, proxy)
        if hostname.endswith(".bybit.com") and hostname.startswith("stream"):
            ipv4 = [addr for addr in addrinfo_list if addr[0] == socket.AF_INET]
            if ipv4:
                return ipv4, need_tunnel, auth
        return addrinfo_list, need_tunnel, auth

    websocket._http._get_addrinfo_list = _get_addrinfo_list
    _WEBSOCKET_IPV4_PATCHED = True


def _summarize_ws_status(
    *,
    now_ts: float,
    public_last_msg_ts: float | None,
    private_last_msg_ts: float | None,
    public_symbols: list[str],
    private_subscribed: bool,
    public_thread_alive: bool = True,
    private_thread_alive: bool = True,
) -> dict:
    def one(
        last: float | None,
        subscribed: bool,
        stale_after: float,
        thread_alive: bool,
        allow_idle: bool,
    ) -> dict:
        if not subscribed:
            return {"status": "disabled", "last_msg_age_seconds": None}
        if last is None:
            return {"status": "connecting", "last_msg_age_seconds": None}
        age = max(0.0, now_ts - last)
        if not thread_alive:
            return {"status": "stale", "last_msg_age_seconds": age}
        if age <= stale_after:
            return {"status": "connected", "last_msg_age_seconds": age}
        return {
            "status": "connected_idle" if allow_idle else "stale",
            "last_msg_age_seconds": age,
        }

    public = one(
        public_last_msg_ts,
        bool(public_symbols),
        PUBLIC_WS_STALE_SECONDS,
        public_thread_alive,
        allow_idle=False,
    )
    public["subscribed_symbols"] = list(public_symbols)
    private = one(
        private_last_msg_ts,
        private_subscribed,
        PRIVATE_WS_STALE_SECONDS,
        private_thread_alive,
        allow_idle=True,
    )
    private["subscribed"] = private_subscribed
    return {"public": public, "private": private}


def _normalize_order(inst: Instrument, qty: float, price: float) -> tuple[str, str, str | None]:
    qty_dec = _floor_to_step(Decimal(str(qty)), inst.qty_step)
    price_dec = _floor_to_step(Decimal(str(price)), inst.tick_size)

    if qty_dec < inst.min_qty:
        return "", "", f"qty_below_min({qty_dec} < {inst.min_qty})"
    if qty_dec * price_dec < inst.min_notional:
        return "", "", f"notional_below_min({qty_dec * price_dec} < {inst.min_notional})"

    return _format_decimal(qty_dec), _format_decimal(price_dec), None


class BybitLive(ExchangeAdapter):
    """Bybit USDT-perp adapter via pybit. `testnet=True` flips both REST and WS endpoints."""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True,
                 leverage: int = 10, rps: float = 5.0):
        from pybit.unified_trading import HTTP

        self._testnet = testnet
        self._leverage = leverage
        self._http = HTTP(testnet=testnet, api_key=api_key, api_secret=api_secret)
        self._user_q: asyncio.Queue[UserEvent] = asyncio.Queue()
        self._kline_q: asyncio.Queue[Candle] = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._public_ws = None
        self._private_ws = None
        self._public_symbols: list[str] = []
        self._private_subscribed = False
        self._public_last_msg_ts: float | None = None
        self._private_last_msg_ts: float | None = None
        self._public_connected_ts: float | None = None
        self._private_connected_ts: float | None = None
        self._public_last_error: str | None = None
        self._private_last_error: str | None = None
        self._instruments: dict[str, Instrument] = {}
        self._limiter = AsyncLimiter(max_rate=rps, time_period=1.0)
        self._stopping = False
        # link_id -> (expected_price, side) for slip measurement.
        # Populated on place_limit, read on execution events, cleaned up on terminal order status.
        self._expected_price: dict[str, tuple[float, Side]] = {}

    def ws_status(self) -> dict:
        return _summarize_ws_status(
            now_ts=time.time(),
            public_last_msg_ts=self._public_last_msg_ts,
            private_last_msg_ts=self._private_last_msg_ts,
            public_symbols=self._public_symbols,
            private_subscribed=self._private_subscribed,
            public_thread_alive=self._ws_thread_alive(self._public_ws),
            private_thread_alive=self._ws_thread_alive(self._private_ws),
        )

    @staticmethod
    def _ws_thread_alive(ws: Any) -> bool:
        if ws is None:
            return False
        thread = getattr(ws, "wst", None)
        if thread is None:
            # No background thread attribute yet (e.g. just constructed);
            # assume alive until proven otherwise.
            return True
        return bool(thread.is_alive())

    # ---- ExchangeAdapter ----

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()

    async def stop(self) -> None:
        self._stopping = True
        for ws in (self._public_ws, self._private_ws):
            if ws is not None:
                try:
                    await asyncio.to_thread(ws.exit)
                except Exception as e:
                    log.warning("ws.stop_error", error=str(e))

    async def get_instrument(self, symbol: str) -> Instrument:
        if symbol in self._instruments:
            return self._instruments[symbol]
        async with self._limiter:
            r = await asyncio.to_thread(
                self._http.get_instruments_info, category=CATEGORY, symbol=symbol
            )
        info = r["result"]["list"][0]
        inst = Instrument(
            symbol=symbol,
            tick_size=Decimal(info["priceFilter"]["tickSize"]),
            qty_step=Decimal(info["lotSizeFilter"]["qtyStep"]),
            min_notional=Decimal(info["lotSizeFilter"].get("minNotionalValue", "5")),
            min_qty=Decimal(info["lotSizeFilter"]["minOrderQty"]),
        )
        self._instruments[symbol] = inst
        return inst

    async def set_leverage_for(self, symbol: str) -> None:
        try:
            async with self._limiter:
                await asyncio.to_thread(
                    self._http.set_leverage,
                    category=CATEGORY, symbol=symbol,
                    buyLeverage=str(self._leverage), sellLeverage=str(self._leverage),
                )
        except Exception as e:
            # Bybit returns an error if the leverage is already set to the requested value; safe to ignore.
            msg = str(e)
            if "leverage not modified" in msg.lower():
                return
            log.warning("set_leverage_error", symbol=symbol, error=msg)

    async def place_limit(
        self,
        symbol,
        side: Side,
        qty,
        price,
        link_id,
        *,
        reduce_only: bool = False,
        post_only: bool = True,
    ) -> OrderAck:
        inst = await self.get_instrument(symbol)
        qty_str, price_str, reason = _normalize_order(inst, qty, price)
        if reason is not None:
            log.warning("place_order_invalid", symbol=symbol, link_id=link_id, reason=reason)
            return OrderAck(link_id=link_id, order_id="", accepted=False, reason=reason)

        async with self._limiter:
            t0 = time.perf_counter()
            try:
                r = await asyncio.to_thread(
                    self._http.place_order,
                    category=CATEGORY,
                    symbol=symbol,
                    side=side.value,
                    orderType="Limit",
                    qty=qty_str,
                    price=price_str,
                    timeInForce="PostOnly" if post_only else "GTC",
                    reduceOnly=reduce_only,
                    orderLinkId=link_id,
                )
            except Exception as e:
                _record_rest_latency("place_order", t0, symbol=symbol, link_id=link_id, ok=False)
                log.warning("place_order_failed", symbol=symbol, link_id=link_id, error=str(e))
                return OrderAck(link_id=link_id, order_id="", accepted=False, reason=str(e))
        _record_rest_latency(
            "place_order", t0, symbol=symbol, link_id=link_id, ok=(r.get("retCode") == 0)
        )
        if r.get("retCode") != 0:
            return OrderAck(link_id=link_id, order_id="", accepted=False, reason=r.get("retMsg"))
        try:
            self._expected_price[link_id] = (float(price_str), side)
        except (TypeError, ValueError):
            pass
        return OrderAck(link_id=link_id, order_id=r["result"]["orderId"], accepted=True)

    async def close_position_market(self, symbol: str, side: Side, link_id: str) -> OrderAck:
        """Close the full position with Bybit's reduce-only qty=0 market order.

        This intentionally bypasses local min qty/notional normalization because
        the caller uses it only when a normal reduce-only limit exit was rejected
        as dust.
        """
        async with self._limiter:
            t0 = time.perf_counter()
            try:
                r = await asyncio.to_thread(
                    self._http.place_order,
                    category=CATEGORY,
                    symbol=symbol,
                    side=side.value,
                    orderType="Market",
                    qty="0",
                    reduceOnly=True,
                    closeOnTrigger=True,
                    orderLinkId=link_id,
                )
            except Exception as e:
                _record_rest_latency(
                    "close_position_market", t0, symbol=symbol, link_id=link_id, ok=False
                )
                log.warning(
                    "close_position_market_failed",
                    symbol=symbol,
                    link_id=link_id,
                    side=side.value,
                    error=str(e),
                )
                return OrderAck(link_id=link_id, order_id="", accepted=False, reason=str(e))
        _record_rest_latency(
            "close_position_market", t0, symbol=symbol, link_id=link_id, ok=(r.get("retCode") == 0)
        )
        if r.get("retCode") != 0:
            return OrderAck(link_id=link_id, order_id="", accepted=False, reason=r.get("retMsg"))
        return OrderAck(
            link_id=link_id,
            order_id=r.get("result", {}).get("orderId", ""),
            accepted=True,
        )

    async def cancel(self, symbol, link_id) -> None:
        async with self._limiter:
            t0 = time.perf_counter()
            try:
                await asyncio.to_thread(
                    self._http.cancel_order,
                    category=CATEGORY, symbol=symbol, orderLinkId=link_id,
                )
                _record_rest_latency("cancel_order", t0, symbol=symbol, link_id=link_id, ok=True)
            except Exception as e:
                _record_rest_latency("cancel_order", t0, symbol=symbol, link_id=link_id, ok=False)
                log.warning("cancel_failed", symbol=symbol, link_id=link_id, error=str(e))

    async def cancel_all(self, symbol) -> None:
        async with self._limiter:
            t0 = time.perf_counter()
            try:
                await asyncio.to_thread(
                    self._http.cancel_all_orders, category=CATEGORY, symbol=symbol
                )
                _record_rest_latency("cancel_all_orders", t0, symbol=symbol, ok=True)
            except Exception as e:
                _record_rest_latency("cancel_all_orders", t0, symbol=symbol, ok=False)
                log.warning("cancel_all_failed", symbol=symbol, error=str(e))

    async def get_position(self, symbol) -> Position:
        async with self._limiter:
            t0 = time.perf_counter()
            r = await asyncio.to_thread(
                self._http.get_positions, category=CATEGORY, symbol=symbol
            )
            _record_rest_latency("get_positions", t0, symbol=symbol)
        lst = r.get("result", {}).get("list", [])
        if not lst:
            return Position(symbol=symbol, size=0.0, avg_price=0.0)
        p = lst[0]
        size = float(p.get("size", 0) or 0)
        if p.get("side") == "Sell":
            size = -size
        avg = float(p.get("avgPrice", 0) or 0)
        return Position(symbol=symbol, size=size, avg_price=avg)

    async def get_open_orders(self, symbol) -> list[Order]:
        async with self._limiter:
            t0 = time.perf_counter()
            r = await asyncio.to_thread(
                self._http.get_open_orders, category=CATEGORY, symbol=symbol
            )
            _record_rest_latency("get_open_orders", t0, symbol=symbol)
        out: list[Order] = []
        for o in r.get("result", {}).get("list", []):
            link = o.get("orderLinkId", "")
            purpose = OrderPurpose.ENTRY
            parts = link.split("-")
            if len(parts) >= 3:
                try:
                    purpose = OrderPurpose(parts[2])
                except ValueError:
                    pass
            side = Side(o["side"])
            out.append(Order(
                link_id=link,
                symbol=symbol,
                side=side,
                purpose=purpose,
                qty=float(o["qty"]),
                price=float(o["price"]),
            ))
        return out

    async def stream_klines(self, symbols, interval="1") -> AsyncIterator[Candle]:
        self._public_symbols = list(symbols)
        backoff = WS_RECONNECT_BASE_SECONDS
        while not self._stopping:
            if self._public_ws is None:
                try:
                    await self._connect_public_ws(self._public_symbols, interval)
                    backoff = WS_RECONNECT_BASE_SECONDS
                except Exception as e:
                    self._public_last_error = str(e)
                    _log_ws_warning(
                        "public_ws_connect_failed",
                        key="public",
                        error=str(e),
                        retry_seconds=backoff,
                    )
                    await self._reset_public_ws()
                    await asyncio.sleep(backoff)
                    backoff = min(WS_RECONNECT_MAX_SECONDS, backoff * 2)
                    continue

            try:
                yield await asyncio.wait_for(self._kline_q.get(), timeout=WS_HEALTH_CHECK_SECONDS)
            except asyncio.TimeoutError:
                if self._public_ws_needs_reconnect():
                    log.warning("public_ws_reconnecting", reason=self._public_reconnect_reason())
                    await self._reset_public_ws()

    async def stream_user_events(self) -> AsyncIterator[UserEvent]:
        self._private_subscribed = True
        backoff = WS_RECONNECT_BASE_SECONDS
        while not self._stopping:
            if self._private_ws is None:
                try:
                    await self._connect_private_ws()
                    backoff = WS_RECONNECT_BASE_SECONDS
                except Exception as e:
                    self._private_last_error = str(e)
                    _log_ws_warning(
                        "private_ws_connect_failed",
                        key="private",
                        error=str(e),
                        retry_seconds=backoff,
                    )
                    await self._reset_private_ws()
                    await asyncio.sleep(backoff)
                    backoff = min(WS_RECONNECT_MAX_SECONDS, backoff * 2)
                    continue

            try:
                yield await asyncio.wait_for(self._user_q.get(), timeout=WS_HEALTH_CHECK_SECONDS)
            except asyncio.TimeoutError:
                if self._ws_thread_dead(self._private_ws):
                    log.warning("private_ws_reconnecting", reason="thread_dead")
                    await self._reset_private_ws()

    async def _connect_public_ws(self, symbols: list[str], interval: str) -> None:
        # pybit's WebSocket constructor + subscription calls do network I/O
        # synchronously. Run them on a thread so the asyncio loop stays
        # responsive during slow connects and retries.
        ws = await asyncio.to_thread(self._make_public_ws)
        for sym in symbols:
            await asyncio.to_thread(
                ws.kline_stream,
                interval=interval,
                symbol=sym,
                callback=self._on_kline_msg,
            )
        self._public_ws = ws
        self._public_connected_ts = time.time()
        self._public_last_error = None
        log.info("public_ws_subscribed", symbols=symbols, interval=interval)

    async def _connect_private_ws(self) -> None:
        ws = await asyncio.to_thread(self._make_private_ws)
        await asyncio.to_thread(ws.order_stream, callback=self._on_order_msg)
        await asyncio.to_thread(ws.execution_stream, callback=self._on_execution_msg)
        await asyncio.to_thread(ws.position_stream, callback=self._on_position_msg)
        self._private_ws = ws
        self._private_subscribed = True
        self._private_connected_ts = time.time()
        self._private_last_error = None
        log.info("private_ws_subscribed")

    async def _reset_public_ws(self) -> None:
        ws, self._public_ws = self._public_ws, None
        self._public_connected_ts = None
        if ws is not None:
            try:
                await asyncio.to_thread(ws.exit)
            except Exception as e:
                log.warning("public_ws_exit_failed", error=str(e))

    async def _reset_private_ws(self) -> None:
        ws, self._private_ws = self._private_ws, None
        self._private_connected_ts = None
        if ws is not None:
            try:
                await asyncio.to_thread(ws.exit)
            except Exception as e:
                log.warning("private_ws_exit_failed", error=str(e))

    def _public_ws_needs_reconnect(self) -> bool:
        if self._ws_thread_dead(self._public_ws):
            return True
        ref = self._public_last_msg_ts or self._public_connected_ts
        return ref is not None and time.time() - ref > PUBLIC_WS_STALE_SECONDS

    def _public_reconnect_reason(self) -> str:
        if self._ws_thread_dead(self._public_ws):
            return "thread_dead"
        ref = self._public_last_msg_ts or self._public_connected_ts
        if ref is not None:
            return f"stale_for_{time.time() - ref:.1f}s"
        return "unknown"

    @staticmethod
    def _ws_thread_dead(ws: Any) -> bool:
        thread = getattr(ws, "wst", None)
        return thread is not None and not thread.is_alive()

    # ---- WS construction ----

    def _make_public_ws(self):
        from pybit.unified_trading import WebSocket
        _patch_pybit_ws_timeout_errors()
        _patch_websocket_bybit_ipv4_preference()
        self._set_websocket_default_timeout()
        return WebSocket(
            testnet=self._testnet,
            channel_type="linear",
            retries=2,
            restart_on_error=False,
        )

    def _make_private_ws(self):
        from pybit.unified_trading import WebSocket
        _patch_pybit_ws_timeout_errors()
        _patch_websocket_bybit_ipv4_preference()
        self._set_websocket_default_timeout()
        return WebSocket(
            testnet=self._testnet,
            channel_type="private",
            api_key=self._http.api_key,
            api_secret=self._http.api_secret,
            retries=2,
            restart_on_error=False,
        )

    @staticmethod
    def _set_websocket_default_timeout() -> None:
        import websocket
        websocket.setdefaulttimeout(WS_CONNECT_TIMEOUT_SECONDS)

    # ---- WS callbacks (run on pybit threads; bridge to asyncio) ----

    def _put(self, q: asyncio.Queue, item) -> None:
        if self._loop is None:
            return
        # Schedule a safe, thread-bridged put.
        asyncio.run_coroutine_threadsafe(q.put(item), self._loop)

    def _on_kline_msg(self, msg: dict[str, Any]) -> None:
        self._public_last_msg_ts = time.time()
        try:
            data = msg.get("data") or []
            topic = msg.get("topic", "")
            symbol = topic.split(".")[-1] if topic else ""
            for k in data:
                if not k.get("confirm"):
                    continue
                _record_ws_event_age("kline_confirm", k.get("end"), symbol=symbol)
                self._put(self._kline_q, Candle(
                    symbol=symbol,
                    timestamp=int(k["end"]) / 1000.0,
                    open=float(k["open"]),
                    high=float(k["high"]),
                    low=float(k["low"]),
                    close=float(k["close"]),
                    volume=float(k["volume"]),
                    confirm=True,
                ))
        except Exception as e:
            log.warning("on_kline_msg_error", error=str(e))

    def _on_order_msg(self, msg: dict[str, Any]) -> None:
        self._private_last_msg_ts = time.time()
        try:
            for o in msg.get("data") or []:
                status = o.get("orderStatus", "").lower()
                mapped = {
                    "new": "accepted",
                    "rejected": "rejected",
                    "cancelled": "cancelled",
                    "filled": "filled",
                    "partiallyfilled": "partial",
                }.get(status)
                if mapped is None:
                    continue
                _record_ws_event_age(
                    "order", o.get("updatedTime"),
                    symbol=o.get("symbol", ""), status=mapped,
                )
                if mapped in ("filled", "cancelled", "rejected"):
                    self._expected_price.pop(o.get("orderLinkId", ""), None)
                self._put(self._user_q, OrderEvent(
                    link_id=o.get("orderLinkId", ""),
                    symbol=o.get("symbol", ""),
                    status=mapped,  # type: ignore[arg-type]
                    timestamp=int(o.get("updatedTime", time.time() * 1000)) / 1000.0,
                    reason=o.get("rejectReason") or None,
                ))
        except Exception as e:
            log.warning("on_order_msg_error", error=str(e))

    def _on_execution_msg(self, msg: dict[str, Any]) -> None:
        self._private_last_msg_ts = time.time()
        try:
            for x in msg.get("data") or []:
                _record_ws_event_age(
                    "execution", x.get("execTime"),
                    symbol=x.get("symbol", ""), is_maker=x.get("isMaker", False),
                )
                link_id = x.get("orderLinkId", "")
                fill_price = float(x["execPrice"])
                side_str = x.get("side", "")
                self._record_slip(link_id, fill_price, side_str, x.get("symbol", ""), x.get("isMaker", False))
                self._put(self._user_q, ExecutionEvent(
                    link_id=link_id,
                    symbol=x.get("symbol", ""),
                    side=Side(side_str),
                    qty=float(x["execQty"]),
                    price=fill_price,
                    timestamp=int(x.get("execTime", time.time() * 1000)) / 1000.0,
                    fee=float(x.get("execFee", 0) or 0),
                    is_maker=x.get("isMaker", False),
                ))
        except Exception as e:
            log.warning("on_execution_msg_error", error=str(e))

    def _record_slip(self, link_id: str, fill_price: float, side_str: str, symbol: str, is_maker: Any) -> None:
        """Compute fill slip vs original expected price. Never raises."""
        try:
            entry = self._expected_price.get(link_id)
            if entry is None:
                return
            expected, _stored_side = entry
            if expected <= 0 or fill_price <= 0:
                return
            sign = 1 if side_str == "Buy" else -1
            slip_bps = ((fill_price - expected) / expected) * 10000.0 * sign
            log.info(
                "bybit.fill.slip_bps",
                link_id=link_id, symbol=symbol, side=side_str,
                expected=round(expected, 8), fill=round(fill_price, 8),
                bps=round(slip_bps, 3), is_maker=bool(is_maker),
            )
        except Exception:
            pass

    def _on_position_msg(self, msg: dict[str, Any]) -> None:
        self._private_last_msg_ts = time.time()
        try:
            for p in msg.get("data") or []:
                size = float(p.get("size", 0) or 0)
                if p.get("side") == "Sell":
                    size = -size
                _record_ws_event_age(
                    "position", p.get("updatedTime"),
                    symbol=p.get("symbol", ""),
                )
                self._put(self._user_q, PositionEvent(
                    symbol=p.get("symbol", ""),
                    size=size,
                    avg_price=float(p.get("entryPrice", 0) or 0),
                    timestamp=int(p.get("updatedTime", time.time() * 1000)) / 1000.0,
                ))
        except Exception as e:
            log.warning("on_position_msg_error", error=str(e))
