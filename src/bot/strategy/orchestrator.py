"""Per-symbol orchestrator. Drives the SM, owns the 30-min timer, executes
actions against the exchange adapter."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Callable

import ulid

from bot.config import Settings
from bot.exchange.base import ExchangeAdapter
from bot.logger import get_logger
from bot.models import (
    Candle,
    Direction,
    ExecutionEvent,
    OrderEvent,
    OrderPurpose,
    Position,
    PositionEvent,
    Side,
)
from bot.persistence.store import StateStore
from bot.risk.manager import RiskManager
from bot.signals.base import SignalEngine
from bot.strategy import state_machine as sm
from bot.strategy.state_machine import (
    Action,
    CancelAllTPs,
    CancelEntry,
    CandleClose,
    ClearMergeTimer,
    Context,
    EntryFilled,
    MergeTimerExpired,
    OrderRejected,
    Params,
    PlaceEntry,
    PlaceMergeTP,
    PlaceTP,
    StartMergeTimer,
    TPFilled,
)
from bot.strategy.states import State

log = get_logger(__name__)

MAX_BYBIT_ORDER_LINK_ID_LEN = 45
ORDER_LINK_RANDOM_LEN = 16


def _link_factory():
    def f(symbol: str, side: Side, purpose: OrderPurpose, ts: float) -> str:
        suffix = str(ulid.new())[-ORDER_LINK_RANDOM_LEN:]
        return f"{symbol}-{side.value[0]}-{purpose.value}-{suffix}"
    return f


def _is_fatal_order_rejection(reason: str | None) -> bool:
    if reason is None:
        return False
    normalized = reason.lower()
    return "errcode: 10024" in normalized or "regulatory restrictions" in normalized


def _tp_price(fill: float, direction: Direction, bps: float) -> float:
    delta = fill * (bps / 10_000.0)
    return fill + delta if direction is Direction.LONG else fill - delta


def _purpose_from_link_id(symbol: str, link_id: str) -> OrderPurpose | None:
    parts = link_id.split("-")
    if len(parts) < 3 or parts[0] != symbol:
        return None
    if parts[1] not in {"B", "S", Side.BUY.value, Side.SELL.value}:
        return None
    try:
        return OrderPurpose(parts[2])
    except ValueError:
        return None


def _execution_purpose(ev: ExecutionEvent, ctx: Context) -> OrderPurpose | None:
    purpose = _purpose_from_link_id(ev.symbol, ev.link_id)
    if purpose is not None:
        return purpose
    if ctx.direction is None:
        return None
    if ev.side is ctx.direction.tp_side:
        return OrderPurpose.TP
    if ev.side is ctx.direction.entry_side:
        return OrderPurpose.ENTRY
    return None


def _realized_pnl(direction: Direction, entry_price: float, exit_price: float, qty: float, fee: float) -> float:
    if direction is Direction.LONG:
        gross = (exit_price - entry_price) * qty
    else:
        gross = (entry_price - exit_price) * qty
    return gross - abs(fee)


@dataclass
class _SymbolRuntime:
    ctx: Context
    merge_handle: asyncio.TimerHandle | None = None
    pending_entry_notional: dict[str, float] = field(default_factory=dict)


@dataclass
class _DustCleanupAttempt:
    count: int = 0
    last_ts: float = 0.0
    gave_up_logged: bool = False


class Orchestrator:
    def __init__(
        self,
        settings: Settings,
        adapter: ExchangeAdapter,
        signal: SignalEngine,
        risk: RiskManager,
        store: StateStore,
    ):
        self.settings = settings
        self.adapter = adapter
        self.signal = signal
        self.risk = risk
        self.store = store
        self.params = Params(
            entry_offset_bps=settings.bot.offsets.entry_offset_bps,
            tp_offset_bps=settings.bot.offsets.tp_offset_bps,
            merge_timer_seconds=settings.bot.merge_timer.seconds,
            notional_usd=settings.bot.sizing.notional_usd,
        )
        self._runtimes: dict[str, _SymbolRuntime] = {}
        self._link_factory = _link_factory()
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task] = []
        self._dust_cleanup_attempts: dict[str, _DustCleanupAttempt] = {}

    async def start(self) -> None:
        await self.adapter.start()
        self.risk.assert_can_start()
        log.info(
            "bot.starting", mode=self.settings.env.mode.value,
            symbols=self.settings.symbols.active,
            margin_per_order=self.settings.bot.sizing.margin_usd,
            leverage=self.settings.bot.sizing.leverage,
        )
        for sym in self.settings.symbols.active:
            restored = self.store.load(sym)
            self._runtimes[sym] = _SymbolRuntime(ctx=restored or Context(symbol=sym))
            if hasattr(self.adapter, "set_leverage_for"):
                await self.adapter.set_leverage_for(sym)  # type: ignore[attr-defined]
        # Reconcile state with exchange on boot.
        await self._reconcile_all()
        # Start consumer tasks.
        self._tasks.append(asyncio.create_task(self._kline_loop(), name="kline_loop"))
        self._tasks.append(asyncio.create_task(self._user_event_loop(), name="user_loop"))
        self._tasks.append(asyncio.create_task(self._reconcile_loop(), name="reconcile_loop"))
        self._tasks.append(asyncio.create_task(self._heartbeat_loop(), name="heartbeat"))
        log.info("bot.started")

    async def run_until_stop(self) -> None:
        await self._stop.wait()

    async def stop(self) -> None:
        self._stop.set()
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        await self.adapter.stop()
        log.info("bot.stopped")

    # ---- main loops ----

    async def _kline_loop(self) -> None:
        async for candle in self.adapter.stream_klines(self.settings.symbols.active, interval="1"):
            if self._stop.is_set():
                break
            try:
                await self._on_candle(candle)
            except Exception as e:
                log.exception("on_candle_error", symbol=candle.symbol, error=str(e))

    async def _user_event_loop(self) -> None:
        async for ev in self.adapter.stream_user_events():
            if self._stop.is_set():
                break
            try:
                await self._on_user_event(ev)
            except Exception as e:
                log.exception("on_user_event_error", error=str(e))

    # ---- handlers ----

    async def _on_candle(self, candle: Candle) -> None:
        rt = self._runtimes.get(candle.symbol)
        if rt is None:
            return
        sig = self.signal.on_candle(candle)
        sig_dir = sig.direction if sig else None
        notional_scale = sig.size_scale if sig else 1.0
        allow_new_position = sig.allow_new_position if sig else True
        allow_layering = sig.allow_layering if sig else True
        decision = sm.step(
            rt.ctx,
            CandleClose(
                timestamp=candle.timestamp,
                close_price=candle.close,
                signal_direction=sig_dir,
                notional_scale=notional_scale,
                allow_new_position=allow_new_position,
                allow_layering=allow_layering,
            ),
            self.params, link_id_factory=self._link_factory,
        )
        await self._apply(candle.symbol, rt, decision)

    async def _on_user_event(self, ev) -> None:
        if isinstance(ev, ExecutionEvent):
            rt = self._runtimes.get(ev.symbol)
            if rt is None:
                return
            purpose = _execution_purpose(ev, rt.ctx)
            if purpose is None:
                log.warning(
                    "execution_ignored_unknown_purpose",
                    symbol=ev.symbol,
                    link_id=ev.link_id,
                    side=ev.side.value,
                    qty=ev.qty,
                    price=ev.price,
                )
                await self._reconcile_all()
                return
            if purpose is OrderPurpose.ENTRY:
                log.info(
                    "entry_filled",
                    symbol=ev.symbol,
                    link_id=ev.link_id,
                    side=ev.side.value,
                    qty=ev.qty,
                    price=ev.price,
                    fee=ev.fee,
                )
                decision = sm.step(
                    rt.ctx,
                    EntryFilled(
                        link_id=ev.link_id,
                        qty=ev.qty,
                        price=ev.price,
                        timestamp=ev.timestamp,
                        side=ev.side,
                    ),
                    self.params, link_id_factory=self._link_factory,
                )
            else:
                prior_ctx = rt.ctx
                if (
                    prior_ctx.direction is not None
                    and prior_ctx.position_size > 0
                    and prior_ctx.bep > 0
                ):
                    qty_closed = min(ev.qty, prior_ctx.position_size)
                    if qty_closed > 0:
                        self.risk.on_trade_closed(
                            ev.symbol,
                            _realized_pnl(
                                prior_ctx.direction,
                                prior_ctx.bep,
                                ev.price,
                                qty_closed,
                                ev.fee,
                            ),
                            qty_closed * ev.price,
                        )
                log.info(
                    "tp_filled" if purpose is OrderPurpose.TP else "merge_filled",
                    symbol=ev.symbol,
                    link_id=ev.link_id,
                    side=ev.side.value,
                    purpose=purpose.value,
                    qty=ev.qty,
                    price=ev.price,
                    fee=ev.fee,
                )
                decision = sm.step(
                    rt.ctx,
                    TPFilled(link_id=ev.link_id, qty=ev.qty, price=ev.price, timestamp=ev.timestamp),
                    self.params, link_id_factory=self._link_factory,
                )
            await self._apply(ev.symbol, rt, decision)

        elif isinstance(ev, OrderEvent):
            if ev.status == "rejected":
                rt = self._runtimes.get(ev.symbol)
                if rt is None:
                    return
                parts = ev.link_id.split("-")
                purpose = OrderPurpose.ENTRY
                if len(parts) >= 3:
                    try:
                        purpose = OrderPurpose(parts[2])
                    except ValueError:
                        pass
                decision = sm.step(
                    rt.ctx,
                    OrderRejected(link_id=ev.link_id, purpose=purpose, timestamp=ev.timestamp),
                    self.params, link_id_factory=self._link_factory,
                )
                await self._apply(ev.symbol, rt, decision)

        elif isinstance(ev, PositionEvent):
            # Authoritative truth about size/BEP. We trust the SM's own bookkeeping
            # for transitions but log drifts.
            rt = self._runtimes.get(ev.symbol)
            if rt is None:
                return
            local = abs(rt.ctx.position_size)
            if abs(local - abs(ev.size)) > 1e-6:
                log.info(
                    "position_drift", symbol=ev.symbol,
                    local=local, exchange=abs(ev.size), bep_local=rt.ctx.bep, bep_exchange=ev.avg_price,
                )

    async def _apply(self, symbol: str, rt: _SymbolRuntime, decision) -> None:
        rt.ctx = decision.ctx
        for action in decision.actions:
            await self._execute(symbol, rt, action)
        self.store.save(rt.ctx)

    async def _execute(self, symbol: str, rt: _SymbolRuntime, action: Action) -> None:
        if isinstance(action, PlaceEntry):
            notional = action.qty * action.price
            ok, reason = self.risk.check_can_place_entry(symbol, notional)
            if not ok:
                log.info("entry_blocked", symbol=symbol, reason=reason)
                await self._handle_entry_rejected(symbol, rt, action.link_id, reason)
                return
            ack = await self.adapter.place_limit(symbol, action.direction.entry_side,
                                                 action.qty, action.price, action.link_id)
            if ack.accepted:
                self.risk.on_entry_placed(symbol, notional)
                rt.pending_entry_notional[action.link_id] = notional
            else:
                await self._handle_entry_rejected(symbol, rt, action.link_id, ack.reason)
                if _is_fatal_order_rejection(ack.reason):
                    self._halt_for_fatal_order_error(symbol, action.link_id, ack.reason)

        elif isinstance(action, PlaceTP):
            ack = await self.adapter.place_limit(symbol, action.direction.tp_side,
                                                 action.qty, action.price, action.link_id,
                                                 reduce_only=True, post_only=False)
            if not ack.accepted:
                log.warning("tp_place_rejected", symbol=symbol, link_id=action.link_id,
                            reason=ack.reason)
                if _is_fatal_order_rejection(ack.reason):
                    self._halt_for_fatal_order_error(symbol, action.link_id, ack.reason)
                else:
                    await self._feed_order_rejected(symbol, rt, action.link_id,
                                                    OrderPurpose.TP, ack.reason)

        elif isinstance(action, PlaceMergeTP):
            ack = await self.adapter.place_limit(symbol, action.direction.tp_side,
                                                 action.qty, action.price, action.link_id,
                                                 reduce_only=True, post_only=False)
            if not ack.accepted:
                log.warning("merge_tp_place_rejected", symbol=symbol, link_id=action.link_id,
                            reason=ack.reason)
                if _is_fatal_order_rejection(ack.reason):
                    self._halt_for_fatal_order_error(symbol, action.link_id, ack.reason)
                else:
                    # Feed the synchronous REST rejection into the SM so it can
                    # decide to park the symbol in DUST_STRANDED when the
                    # remainder is below exchange min notional/qty. Without
                    # this the reconcile loop would re-issue the same losing
                    # merge every few seconds forever.
                    await self._feed_order_rejected(symbol, rt, action.link_id,
                                                    OrderPurpose.MERGE, ack.reason)

        elif isinstance(action, CancelEntry):
            await self.adapter.cancel(symbol, action.link_id)
            released = rt.pending_entry_notional.pop(action.link_id, 0.0)
            if released:
                self.risk.on_entry_cancelled(symbol, released)

        elif isinstance(action, CancelAllTPs):
            orders = await self.adapter.get_open_orders(symbol)
            for o in orders:
                if o.purpose in (OrderPurpose.TP, OrderPurpose.MERGE):
                    await self.adapter.cancel(symbol, o.link_id)

        elif isinstance(action, StartMergeTimer):
            self._schedule_merge_timer(symbol, rt, action.deadline)

        elif isinstance(action, ClearMergeTimer):
            if rt.merge_handle is not None:
                rt.merge_handle.cancel()
                rt.merge_handle = None

    async def _handle_entry_rejected(
        self,
        symbol: str,
        rt: _SymbolRuntime,
        link_id: str,
        reason: str | None,
    ) -> None:
        log.warning("entry_rejected", symbol=symbol, link_id=link_id, reason=reason)
        decision = sm.step(
            rt.ctx,
            OrderRejected(link_id=link_id, purpose=OrderPurpose.ENTRY, timestamp=time.time(),
                          reason=reason),
            self.params,
            link_id_factory=self._link_factory,
        )
        rt.ctx = decision.ctx
        for action in decision.actions:
            await self._execute(symbol, rt, action)
        self.store.save(rt.ctx)

    async def _feed_order_rejected(
        self,
        symbol: str,
        rt: _SymbolRuntime,
        link_id: str,
        purpose: OrderPurpose,
        reason: str | None,
    ) -> None:
        prev_state = rt.ctx.state
        decision = sm.step(
            rt.ctx,
            OrderRejected(link_id=link_id, purpose=purpose, timestamp=time.time(), reason=reason),
            self.params,
            link_id_factory=self._link_factory,
        )
        rt.ctx = decision.ctx
        for action in decision.actions:
            await self._execute(symbol, rt, action)
        self.store.save(rt.ctx)
        if prev_state is not rt.ctx.state and rt.ctx.state is State.DUST_STRANDED:
            log.warning(
                "dust_stranded",
                symbol=symbol,
                direction=rt.ctx.direction.value if rt.ctx.direction else None,
                size=rt.ctx.position_size,
                bep=rt.ctx.bep,
                reason=reason,
            )

    def _halt_for_fatal_order_error(self, symbol: str, link_id: str, reason: str | None) -> None:
        log.error(
            "fatal_order_rejection_stopping_bot",
            symbol=symbol,
            link_id=link_id,
            reason=reason,
        )
        self._stop.set()
        for sym, runtime in self._runtimes.items():
            runtime.ctx = runtime.ctx.with_(halted=True)
            self.store.save(runtime.ctx)
            if runtime.merge_handle is not None:
                runtime.merge_handle.cancel()
                runtime.merge_handle = None

    def _schedule_merge_timer(self, symbol: str, rt: _SymbolRuntime, deadline: float) -> None:
        loop = asyncio.get_running_loop()
        delay = max(0.0, deadline - loop.time())
        # Convert wallclock-based deadline to monotonic loop time.
        # `deadline` from StartMergeTimer is wallclock seconds.
        import time as _t
        wall_now = _t.time()
        delay = max(0.0, deadline - wall_now)
        if rt.merge_handle is not None:
            rt.merge_handle.cancel()
        rt.merge_handle = loop.call_later(delay, lambda: asyncio.create_task(
            self._fire_merge(symbol)
        ))

    async def _fire_merge(self, symbol: str) -> None:
        rt = self._runtimes.get(symbol)
        if rt is None:
            return
        import time as _t
        decision = sm.step(rt.ctx, MergeTimerExpired(timestamp=_t.time()), self.params,
                           link_id_factory=self._link_factory)
        rt.merge_handle = None
        await self._apply(symbol, rt, decision)

    async def _reconcile_all(self) -> None:
        """Pull truth from the exchange and merge with local state.

        Runs on boot and periodically (covers WS gaps after reconnects).
        Exchange is authoritative: if the exchange reports flat but our SM
        thinks we have a position, force-reset to IDLE.
        """
        for sym in self.settings.symbols.active:
            rt = self._runtimes.get(sym)
            if rt is None:
                continue
            try:
                pos = await self.adapter.get_position(sym)
                local_size = rt.ctx.position_size
                exch_size = abs(pos.size)
                if pos.is_flat and rt.ctx.state is not State.IDLE and local_size > 0:
                    log.warning("reconcile.force_idle", symbol=sym, local_size=local_size)
                    rt.ctx = Context(symbol=sym)
                    self.risk.sync_open_notional(sym, 0.0)
                    self.store.save(rt.ctx)
                    self._dust_cleanup_attempts.pop(sym, None)
                    if rt.merge_handle is not None:
                        rt.merge_handle.cancel()
                        rt.merge_handle = None
                elif not pos.is_flat and pos.direction is not None and (
                    abs(local_size - exch_size) > 1e-6
                    or rt.ctx.direction is not pos.direction
                    or rt.ctx.state is State.IDLE
                    or abs(rt.ctx.bep - pos.avg_price) > 1e-6
                ):
                    log.info(
                        "reconcile.size_drift", symbol=sym,
                        local=local_size, exchange=exch_size,
                        bep_local=rt.ctx.bep, bep_exchange=pos.avg_price,
                    )
                    await self._adopt_exchange_position(sym, rt, pos.direction, exch_size, pos.avg_price)
                    if rt.ctx.state is State.DUST_STRANDED:
                        await self._maybe_cleanup_dust_position(sym, rt, pos)
                elif not pos.is_flat:
                    if rt.ctx.state is State.DUST_STRANDED:
                        await self._maybe_cleanup_dust_position(sym, rt, pos)
                    else:
                        await self._ensure_protective_exit_order(sym, rt)
            except Exception as e:
                log.warning("reconcile.failed", symbol=sym, error=str(e))

    async def _adopt_exchange_position(
        self,
        symbol: str,
        rt: _SymbolRuntime,
        direction: Direction,
        size: float,
        bep: float,
    ) -> None:
        """Adopt exchange position truth and recreate protective exit order."""
        now = time.time()
        preserve_merge = rt.ctx.state is State.MERGE_PENDING and rt.ctx.direction is direction
        preserve_dust = rt.ctx.state is State.DUST_STRANDED and rt.ctx.direction is direction
        if preserve_dust:
            state = State.DUST_STRANDED
        elif preserve_merge:
            state = State.MERGE_PENDING
        else:
            state = State.IN_POSITION_TP_PENDING
        rt.ctx = rt.ctx.with_(
            state=state,
            direction=direction,
            position_size=size,
            bep=bep,
            first_fill_ts=rt.ctx.first_fill_ts or now,
            pending_entry_link_id=None,
        )
        rt.pending_entry_notional.clear()
        self.risk.sync_open_notional(symbol, size * bep)
        self.store.save(rt.ctx)
        log.warning(
            "reconcile.adopt_exchange_position",
            symbol=symbol,
            state=state.value,
            direction=direction.value,
            size=size,
            bep=bep,
        )

        await self.adapter.cancel_all(symbol)
        if state is not State.DUST_STRANDED:
            await self._place_protective_exit_order(symbol, rt)

    async def _maybe_cleanup_dust_position(
        self,
        symbol: str,
        rt: _SymbolRuntime,
        pos: Position,
    ) -> None:
        cfg = self.settings.bot.dust_cleanup
        if not cfg.enabled or pos.is_flat:
            return
        direction = rt.ctx.direction or pos.direction
        if direction is None:
            return

        attempt = self._dust_cleanup_attempts.setdefault(symbol, _DustCleanupAttempt())
        if attempt.count >= cfg.max_attempts:
            if not attempt.gave_up_logged:
                log.warning(
                    "dust_cleanup.gave_up",
                    symbol=symbol,
                    attempts=attempt.count,
                    max_attempts=cfg.max_attempts,
                )
                attempt.gave_up_logged = True
            return

        now = time.time()
        if attempt.last_ts and now - attempt.last_ts < cfg.retry_seconds:
            return

        attempt.count += 1
        attempt.last_ts = now
        attempt.gave_up_logged = False
        link_id = self._link_factory(symbol, direction.tp_side, OrderPurpose.TP, now)
        log.warning(
            "dust_cleanup.submitting",
            symbol=symbol,
            side=direction.tp_side.value,
            size=abs(pos.size),
            bep=pos.avg_price,
            attempt=attempt.count,
            max_attempts=cfg.max_attempts,
            link_id=link_id,
        )

        await self.adapter.cancel_all(symbol)
        try:
            ack = await self.adapter.close_position_market(symbol, direction.tp_side, link_id)
        except NotImplementedError as e:
            log.warning("dust_cleanup.unsupported", symbol=symbol, error=str(e))
            return

        if ack.accepted:
            log.warning(
                "dust_cleanup.submitted",
                symbol=symbol,
                side=direction.tp_side.value,
                link_id=link_id,
                order_id=ack.order_id,
                attempt=attempt.count,
            )
        else:
            log.warning(
                "dust_cleanup.rejected",
                symbol=symbol,
                side=direction.tp_side.value,
                link_id=link_id,
                reason=ack.reason,
                attempt=attempt.count,
            )

    async def _ensure_protective_exit_order(self, symbol: str, rt: _SymbolRuntime) -> None:
        direction = rt.ctx.direction
        if direction is None or rt.ctx.position_size <= 0 or rt.ctx.bep <= 0:
            return
        if rt.ctx.state is State.DUST_STRANDED:
            # Position is below exchange min notional/qty; placing an exit
            # order is impossible. Wait for manual close instead of spamming.
            return
        orders = await self.adapter.get_open_orders(symbol)
        if any(o.purpose in (OrderPurpose.TP, OrderPurpose.MERGE) and o.side is direction.tp_side for o in orders):
            await self._ensure_merge_timer(symbol, rt)
            return
        log.warning(
            "reconcile.exit_order_missing",
            symbol=symbol,
            state=rt.ctx.state.value,
            direction=direction.value,
            size=rt.ctx.position_size,
            bep=rt.ctx.bep,
        )
        await self._place_protective_exit_order(symbol, rt)

    async def _place_protective_exit_order(self, symbol: str, rt: _SymbolRuntime) -> None:
        direction = rt.ctx.direction
        if direction is None or rt.ctx.position_size <= 0 or rt.ctx.bep <= 0:
            return
        state = State.MERGE_PENDING if rt.ctx.state is State.MERGE_PENDING else State.IN_POSITION_TP_PENDING
        if rt.ctx.state is not state:
            rt.ctx = rt.ctx.with_(state=state)
            self.store.save(rt.ctx)

        now = time.time()
        exit_price = _tp_price(rt.ctx.bep, direction, self.params.tp_offset_bps)
        purpose = OrderPurpose.MERGE if state is State.MERGE_PENDING else OrderPurpose.TP
        link_id = self._link_factory(symbol, direction.tp_side, purpose, now)
        if state is State.MERGE_PENDING:
            await self._execute(symbol, rt, PlaceMergeTP(direction, exit_price, rt.ctx.position_size, link_id))
        else:
            await self._execute(symbol, rt, PlaceTP(direction, exit_price, rt.ctx.position_size, link_id))
            await self._ensure_merge_timer(symbol, rt)

    async def _ensure_merge_timer(self, symbol: str, rt: _SymbolRuntime) -> None:
        if rt.ctx.state is not State.IN_POSITION_TP_PENDING or rt.merge_handle is not None:
            return
        now = time.time()
        deadline = (rt.ctx.first_fill_ts or now) + self.params.merge_timer_seconds
        if deadline <= now:
            decision = sm.step(
                rt.ctx,
                MergeTimerExpired(timestamp=now),
                self.params,
                link_id_factory=self._link_factory,
            )
            await self._apply(symbol, rt, decision)
            return
        self._schedule_merge_timer(symbol, rt, deadline)

    async def _reconcile_loop(self) -> None:
        """Periodic reconcile against the exchange. Catches drift after WS reconnects."""
        interval = max(5, self.settings.bot.loop.reconcile_every_seconds)
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
                return  # _stop fired
            except asyncio.TimeoutError:
                pass
            try:
                await self._reconcile_all()
            except Exception as e:
                log.exception("reconcile_loop_error", error=str(e))

    async def _heartbeat_loop(self) -> None:
        """Periodic heartbeat log so it's obvious from the logs if loops are alive."""
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=60.0)
                return
            except asyncio.TimeoutError:
                pass
            counts = {sym: rt.ctx.state.value for sym, rt in self._runtimes.items()}
            ws_status = self.adapter.ws_status() or {}
            log.info("heartbeat", states=counts, ws=ws_status)
            self._persist_ws_status(ws_status)

    def _persist_ws_status(self, ws_status: dict) -> None:
        if not ws_status:
            return
        from datetime import datetime, timezone
        try:
            out = self.store.root / "system" / "ws_status.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            payload = dict(ws_status)
            payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
            import json as _json
            tmp = out.with_suffix(out.suffix + ".tmp")
            tmp.write_text(_json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            tmp.replace(out)
        except OSError as e:
            log.warning("ws_status_persist_failed", error=str(e))
