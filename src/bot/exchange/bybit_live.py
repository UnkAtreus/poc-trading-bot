"""Bybit live adapter wrapping pybit unified_trading (REST + WebSocket).

Strategy code only sees the ExchangeAdapter ABC. This file does the dirty
work: thread-bridging pybit's sync WS callbacks into asyncio queues, mapping
WS payloads to our event dataclasses, and rate-limiting REST.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from decimal import Decimal
from threading import Thread
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
        self._instruments: dict[str, Instrument] = {}
        self._limiter = AsyncLimiter(max_rate=rps, time_period=1.0)
        self._stopping = False

    # ---- ExchangeAdapter ----

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()

    async def stop(self) -> None:
        self._stopping = True
        for ws in (self._public_ws, self._private_ws):
            if ws is not None:
                try:
                    ws.exit()  # pybit's WebSocket has .exit()
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

    async def place_limit(self, symbol, side: Side, qty, price, link_id) -> OrderAck:
        async with self._limiter:
            try:
                r = await asyncio.to_thread(
                    self._http.place_order,
                    category=CATEGORY,
                    symbol=symbol,
                    side=side.value,
                    orderType="Limit",
                    qty=str(qty),
                    price=str(price),
                    timeInForce="PostOnly",
                    orderLinkId=link_id,
                )
            except Exception as e:
                log.warning("place_order_failed", symbol=symbol, link_id=link_id, error=str(e))
                return OrderAck(link_id=link_id, order_id="", accepted=False, reason=str(e))
        if r.get("retCode") != 0:
            return OrderAck(link_id=link_id, order_id="", accepted=False, reason=r.get("retMsg"))
        return OrderAck(link_id=link_id, order_id=r["result"]["orderId"], accepted=True)

    async def cancel(self, symbol, link_id) -> None:
        async with self._limiter:
            try:
                await asyncio.to_thread(
                    self._http.cancel_order,
                    category=CATEGORY, symbol=symbol, orderLinkId=link_id,
                )
            except Exception as e:
                log.warning("cancel_failed", symbol=symbol, link_id=link_id, error=str(e))

    async def cancel_all(self, symbol) -> None:
        async with self._limiter:
            try:
                await asyncio.to_thread(
                    self._http.cancel_all_orders, category=CATEGORY, symbol=symbol
                )
            except Exception as e:
                log.warning("cancel_all_failed", symbol=symbol, error=str(e))

    async def get_position(self, symbol) -> Position:
        async with self._limiter:
            r = await asyncio.to_thread(
                self._http.get_positions, category=CATEGORY, symbol=symbol
            )
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
            r = await asyncio.to_thread(
                self._http.get_open_orders, category=CATEGORY, symbol=symbol
            )
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
        if self._public_ws is None:
            self._public_ws = self._make_public_ws()
            for sym in symbols:
                self._public_ws.kline_stream(
                    interval=interval,
                    symbol=sym,
                    callback=self._on_kline_msg,
                )
        while not self._stopping:
            yield await self._kline_q.get()

    async def stream_user_events(self) -> AsyncIterator[UserEvent]:
        if self._private_ws is None:
            self._private_ws = self._make_private_ws()
            self._private_ws.order_stream(callback=self._on_order_msg)
            self._private_ws.execution_stream(callback=self._on_execution_msg)
            self._private_ws.position_stream(callback=self._on_position_msg)
        while not self._stopping:
            yield await self._user_q.get()

    # ---- WS construction ----

    def _make_public_ws(self):
        from pybit.unified_trading import WebSocket
        return WebSocket(testnet=self._testnet, channel_type="linear")

    def _make_private_ws(self):
        from pybit.unified_trading import WebSocket
        return WebSocket(
            testnet=self._testnet,
            channel_type="private",
            api_key=self._http.api_key,
            api_secret=self._http.api_secret,
        )

    # ---- WS callbacks (run on pybit threads; bridge to asyncio) ----

    def _put(self, q: asyncio.Queue, item) -> None:
        if self._loop is None:
            return
        # Schedule a safe, thread-bridged put.
        asyncio.run_coroutine_threadsafe(q.put(item), self._loop)

    def _on_kline_msg(self, msg: dict[str, Any]) -> None:
        try:
            data = msg.get("data") or []
            topic = msg.get("topic", "")
            symbol = topic.split(".")[-1] if topic else ""
            for k in data:
                if not k.get("confirm"):
                    continue
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
        try:
            for x in msg.get("data") or []:
                self._put(self._user_q, ExecutionEvent(
                    link_id=x.get("orderLinkId", ""),
                    symbol=x.get("symbol", ""),
                    side=Side(x["side"]),
                    qty=float(x["execQty"]),
                    price=float(x["execPrice"]),
                    timestamp=int(x.get("execTime", time.time() * 1000)) / 1000.0,
                    fee=float(x.get("execFee", 0) or 0),
                    is_maker=x.get("isMaker", False),
                ))
        except Exception as e:
            log.warning("on_execution_msg_error", error=str(e))

    def _on_position_msg(self, msg: dict[str, Any]) -> None:
        try:
            for p in msg.get("data") or []:
                size = float(p.get("size", 0) or 0)
                if p.get("side") == "Sell":
                    size = -size
                self._put(self._user_q, PositionEvent(
                    symbol=p.get("symbol", ""),
                    size=size,
                    avg_price=float(p.get("entryPrice", 0) or 0),
                    timestamp=int(p.get("updatedTime", time.time() * 1000)) / 1000.0,
                ))
        except Exception as e:
            log.warning("on_position_msg_error", error=str(e))
