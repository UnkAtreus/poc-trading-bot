"""Walk-forward backtest driver.

For each candle, in order:
  1. Resolve any open simulated orders against this candle's OHLC, emit fills
  2. Drain user events into the SM as EntryFilled/TPFilled/OrderRejected
  3. Check the merge timer (sim time = candle close)
  4. Run signal.on_candle() → Signal | None
  5. Feed CandleClose to the SM, execute resulting actions on the simulator

Output: a list of ExecutionEvent fills + a per-symbol ledger of realized PnL.
"""

from __future__ import annotations

import asyncio
import bisect
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

import ulid

from bot.config import Settings
from bot.exchange.simulator import Simulator
from bot.models import (
    Candle,
    Direction,
    ExecutionEvent,
    OrderEvent,
    OrderPurpose,
    PositionEvent,
    Side,
)
from bot.risk.liquidation import AccountRiskInput, MarginMode, PositionRisk, assess_account_risk
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


@dataclass
class TradeRecord:
    symbol: str
    direction: Direction
    entry_ts: float
    exit_ts: float
    qty: float
    avg_entry: float
    exit_price: float
    realized_pnl: float
    fees: float
    exit_reason: str = "tp"


@dataclass
class EquityPoint:
    timestamp: float
    equity: float
    realized_net: float
    unrealized_pnl: float
    drawdown: float


@dataclass
class MonthlyEquityStats:
    period: str
    peak_equity: float
    ending_equity: float
    max_drawdown_value: float = 0.0

    def update(self, equity: float) -> None:
        self.peak_equity = max(self.peak_equity, equity)
        self.max_drawdown_value = max(self.max_drawdown_value, self.peak_equity - equity)
        self.ending_equity = equity


@dataclass(frozen=True)
class LiquidationEvent:
    timestamp: float
    symbol: str | None
    reason: str
    margin_ratio: float
    min_liq_distance_pct: float
    equity: float
    maintenance_margin: float


@dataclass
class BacktestResult:
    fills: list[ExecutionEvent] = field(default_factory=list)
    trades: list[TradeRecord] = field(default_factory=list)
    final_state: dict[str, Context] = field(default_factory=dict)
    equity_curve: list[EquityPoint] = field(default_factory=list)
    initial_equity: float = 0.0
    max_drawdown_value: float = 0.0
    ending_equity_value: float = 0.0
    monthly_equity: dict[str, MonthlyEquityStats] = field(default_factory=dict)
    liquidated: bool = False
    near_liquidation: bool = False
    liquidation_events: list[LiquidationEvent] = field(default_factory=list)
    near_liquidation_events: list[LiquidationEvent] = field(default_factory=list)
    margin_ratio_max: float = 0.0
    min_liq_distance_pct: float = float("inf")
    worst_unrealized_loss: float = 0.0
    time_in_recovery: float = 0.0
    final_open_exposure: float = 0.0
    max_initial_margin: float = 0.0
    min_available_balance: float = float("inf")
    _fee_cursor: int = 0
    _fee_total_running: float = 0.0
    _trade_cursor: int = 0
    _gross_total_running: float = 0.0
    _last_risk_ts: float | None = None

    @property
    def total_pnl(self) -> float:
        return sum(t.realized_pnl for t in self.trades)

    @property
    def total_fees(self) -> float:
        # Source of truth is the fills list — every executed order has exactly
        # one fee. Don't sum trade.fees, which can be partial / cumulative.
        return sum(f.fee for f in self.fills)

    def fees_for_symbol(self, symbol: str) -> float:
        return sum(f.fee for f in self.fills if f.symbol == symbol)

    @property
    def net_pnl(self) -> float:
        return self.total_pnl - self.total_fees

    @property
    def wins(self) -> int:
        return sum(1 for t in self.trades if t.realized_pnl > 0)

    @property
    def losses(self) -> int:
        return sum(1 for t in self.trades if t.realized_pnl < 0)

    @property
    def stopped(self) -> int:
        return sum(1 for t in self.trades if t.exit_reason == "stop")

    @property
    def win_rate(self) -> float:
        total = self.wins + self.losses
        return self.wins / total if total else 0.0

    @property
    def max_drawdown(self) -> float:
        return self.max_drawdown_value

    @property
    def max_drawdown_pct(self) -> float:
        if self.initial_equity <= 0:
            return 0.0
        return self.max_drawdown / self.initial_equity

    @property
    def ending_equity(self) -> float:
        return self.ending_equity_value or (self.initial_equity + self.net_pnl)

    def monthly_max_drawdown(self, period: str) -> float:
        stats = self.monthly_equity.get(period)
        return stats.max_drawdown_value if stats is not None else 0.0

    def monthly_max_drawdown_pct(self, period: str) -> float:
        if self.initial_equity <= 0:
            return 0.0
        return self.monthly_max_drawdown(period) / self.initial_equity

    def realized_net_running(self) -> float:
        while self._fee_cursor < len(self.fills):
            self._fee_total_running += self.fills[self._fee_cursor].fee
            self._fee_cursor += 1
        while self._trade_cursor < len(self.trades):
            self._gross_total_running += self.trades[self._trade_cursor].realized_pnl
            self._trade_cursor += 1
        return self._gross_total_running - self._fee_total_running


@dataclass
class _PerSymbol:
    ctx: Context
    merge_deadline: float | None = None
    # Track open lots for FIFO-style realized PnL computation.
    open_lots: list[tuple[float, float, Direction]] = field(default_factory=list)  # (qty, price, direction)
    accumulated_fees: float = 0.0
    entry_ts_for_lot: float | None = None
    avg_entry_price: float = 0.0
    total_qty: float = 0.0
    # Risk-tracking: notional reserved for each pending entry, keyed by link_id.
    # On cancel we release; on fill we leave it (now backed by an open position).
    pending_entry_notional: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class BacktestStopConfig:
    bep_stop_bps: float | None = None
    max_symbol_loss_usd: float | None = None
    account_dd_stop_pct: float | None = None
    max_hold_seconds: float | None = None
    monthly_profit_lock_pct: float | None = None
    monthly_dd_stop_pct: float | None = None


def _link_factory():
    def f(symbol: str, side: Side, purpose: OrderPurpose, ts: float) -> str:
        return f"{symbol}-{side.value}-{purpose.value}-{ulid.new()}"
    return f


async def run_backtest(
    settings: Settings,
    candles_by_symbol: dict[str, list[Candle]],
    signal: SignalEngine,
    risk: "RiskManager | None" = None,
    initial_equity: float = 0.0,
    stops: BacktestStopConfig | None = None,
) -> BacktestResult:
    """Run a backtest. Candles must be sorted ascending by timestamp per symbol.
    All symbols are walked in lockstep by global timestamp.

    If `risk` is provided, entries are gated through it (per-symbol and account-wide
    notional caps, cooldowns, daily loss limit). Without it, the strategy's
    layering is unbounded — useful for understanding raw signal behavior, but
    not how the live bot would actually run.
    """
    sim = Simulator(maker_bps=settings.bot.fees.maker_bps, taker_bps=settings.bot.fees.taker_bps)
    # If a RiskManager was passed in, retarget its clock to simulation time so
    # cooldowns and daily-loss rolls happen in sim seconds, not wall seconds.
    sim_clock = {"now": 0.0}
    if risk is not None:
        risk.clock = lambda: sim_clock["now"]
    params = Params(
        entry_offset_bps=settings.bot.offsets.entry_offset_bps,
        tp_offset_bps=settings.bot.offsets.tp_offset_bps,
        merge_timer_seconds=settings.bot.merge_timer.seconds,
        notional_usd=settings.bot.sizing.notional_usd,
    )
    state = {sym: _PerSymbol(ctx=Context(symbol=sym)) for sym in candles_by_symbol}

    # Build a global event stream of (ts, symbol) tuples for lockstep walk.
    timeline: list[tuple[float, str, Candle]] = []
    for sym, lst in candles_by_symbol.items():
        for c in lst:
            timeline.append((c.timestamp, sym, c))
    timeline.sort(key=lambda x: x[0])

    result = BacktestResult(initial_equity=initial_equity)
    factory = _link_factory()
    last_close: dict[str, float] = {}
    last_candle: dict[str, Candle] = {}
    peak_equity = initial_equity
    account_halted = False
    monthly_period: str | None = None
    monthly_start_realized = 0.0
    monthly_peak_equity = initial_equity
    monthly_entry_locked = False
    monthly_dd_stopped = False

    for ts, symbol, candle in timeline:
        last_close[symbol] = candle.close
        last_candle[symbol] = candle
        # Update sim clock first so any risk check this iteration uses sim time.
        sim_clock["now"] = candle.timestamp
        period = datetime.fromtimestamp(candle.timestamp, tz=timezone.utc).strftime("%Y-%m")
        if period != monthly_period:
            monthly_period = period
            monthly_start_realized = result.realized_net_running()
            monthly_peak_equity = _current_equity(result, state, last_close)
            monthly_entry_locked = False
            monthly_dd_stopped = False
        ps = state[symbol]
        # 1. Resolve open orders against this candle (also enqueues user events).
        await sim.feed_candle(candle)
        try:
            sim._kline_q.get_nowait()  # noqa: SLF001
        except asyncio.QueueEmpty:
            pass

        # 2. Drain user events and apply to SM.
        await _drain_events(sim, ps, params, factory, result, symbol, settings, risk)

        # 3. Merge timer check (sim time).
        if ps.merge_deadline is not None and candle.timestamp >= ps.merge_deadline:
            decision = sm.step(ps.ctx, MergeTimerExpired(timestamp=candle.timestamp), params,
                               link_id_factory=factory)
            ps.ctx = decision.ctx
            await _execute_actions(sim, decision.actions, symbol, ps, risk)

        stop_hit = await _apply_symbol_stops(
            sim, ps, candle, result, symbol, settings, risk, stops
        )
        if stop_hit:
            result.fills = sim.fills

        if (
            stops is not None
            and stops.account_dd_stop_pct is not None
            and initial_equity > 0
            and not account_halted
        ):
            equity = _current_equity(result, state, last_close)
            peak_equity = max(peak_equity, equity)
            if peak_equity - equity >= initial_equity * (stops.account_dd_stop_pct / 100.0):
                account_halted = True
                for close_symbol, close_ps in state.items():
                    mark = last_close.get(close_symbol)
                    if mark is None:
                        continue
                    await _force_close_symbol(
                        sim, close_ps, close_symbol, mark, candle.timestamp, result,
                        settings, risk, reason="stop"
                    )
                result.fills = sim.fills

        if stops is not None and initial_equity > 0:
            equity = _current_equity(result, state, last_close)
            monthly_peak_equity = max(monthly_peak_equity, equity)
            if (
                stops.monthly_dd_stop_pct is not None
                and not monthly_dd_stopped
                and monthly_peak_equity - equity >= initial_equity * (stops.monthly_dd_stop_pct / 100.0)
            ):
                monthly_dd_stopped = True
                monthly_entry_locked = True
                for close_symbol, close_ps in state.items():
                    mark = last_close.get(close_symbol)
                    if mark is None:
                        continue
                    await _force_close_symbol(
                        sim, close_ps, close_symbol, mark, candle.timestamp, result,
                        settings, risk, reason="stop"
                    )
                result.fills = sim.fills
                equity = _current_equity(result, state, last_close)
                monthly_peak_equity = max(monthly_peak_equity, equity)
            if stops.monthly_profit_lock_pct is not None and not monthly_entry_locked:
                realized_this_month = result.realized_net_running() - monthly_start_realized
                if realized_this_month >= initial_equity * (stops.monthly_profit_lock_pct / 100.0):
                    monthly_entry_locked = True

        # 4. Signal evaluation.
        raw_sig = None if account_halted else signal.on_candle(candle)
        sig = None if monthly_entry_locked else raw_sig
        sig_dir = sig.direction if sig else None

        # 5. Candle close to SM.
        decision = sm.step(
            ps.ctx,
            CandleClose(timestamp=candle.timestamp, close_price=candle.close, signal_direction=sig_dir),
            params,
            link_id_factory=factory,
        )
        ps.ctx = decision.ctx
        await _execute_actions(sim, decision.actions, symbol, ps, risk)
        result.fills = sim.fills
        peak_equity = _record_equity_point(result, state, last_close, candle.timestamp, peak_equity)
        if _record_account_risk(result, state, last_close, last_candle, candle.timestamp, settings):
            account_halted = True

    # Close out final result.
    result.final_state = {s: ps.ctx for s, ps in state.items()}
    result.fills = sim.fills
    if result.min_liq_distance_pct == float("inf"):
        result.min_liq_distance_pct = 0.0
    if result.min_available_balance == float("inf"):
        result.min_available_balance = result.initial_equity
    return result


def _current_equity(
    result: BacktestResult,
    state: dict[str, _PerSymbol],
    last_close: dict[str, float],
) -> float:
    realized_net = result.realized_net_running()
    unrealized = _current_unrealized(state, last_close)
    return result.initial_equity + realized_net + unrealized


def _current_unrealized(
    state: dict[str, _PerSymbol],
    last_close: dict[str, float],
) -> float:
    unrealized = 0.0
    for sym, ps in state.items():
        if ps.total_qty <= 0 or ps.avg_entry_price <= 0:
            continue
        mark = last_close.get(sym)
        if mark is None:
            continue
        unrealized += _symbol_unrealized(ps, mark)
    return unrealized


def _symbol_unrealized(ps: _PerSymbol, mark: float) -> float:
    if ps.ctx.direction is Direction.LONG:
        return (mark - ps.avg_entry_price) * ps.total_qty
    if ps.ctx.direction is Direction.SHORT:
        return (ps.avg_entry_price - mark) * ps.total_qty
    return 0.0


async def _apply_symbol_stops(
    sim: Simulator,
    ps: _PerSymbol,
    candle: Candle,
    result: BacktestResult,
    symbol: str,
    settings: Settings,
    risk: "RiskManager | None",
    stops: BacktestStopConfig | None,
) -> bool:
    if stops is None or ps.total_qty <= 0 or ps.avg_entry_price <= 0 or ps.ctx.direction is None:
        return False

    if stops.bep_stop_bps is not None:
        if ps.ctx.direction is Direction.LONG:
            stop_price = ps.avg_entry_price * (1.0 - stops.bep_stop_bps / 10_000.0)
            if candle.low <= stop_price:
                await _force_close_symbol(
                    sim, ps, symbol, stop_price, candle.timestamp, result, settings, risk,
                    reason="stop",
                )
                return True
        else:
            stop_price = ps.avg_entry_price * (1.0 + stops.bep_stop_bps / 10_000.0)
            if candle.high >= stop_price:
                await _force_close_symbol(
                    sim, ps, symbol, stop_price, candle.timestamp, result, settings, risk,
                    reason="stop",
                )
                return True

    if stops.max_symbol_loss_usd is not None:
        if _symbol_unrealized(ps, candle.close) <= -stops.max_symbol_loss_usd:
            await _force_close_symbol(
                sim, ps, symbol, candle.close, candle.timestamp, result, settings, risk,
                reason="stop",
            )
            return True

    if stops.max_hold_seconds is not None and ps.entry_ts_for_lot is not None:
        if candle.timestamp - ps.entry_ts_for_lot >= stops.max_hold_seconds:
            await _force_close_symbol(
                sim, ps, symbol, candle.close, candle.timestamp, result, settings, risk,
                reason="stop",
            )
            return True

    return False


async def _force_close_symbol(
    sim: Simulator,
    ps: _PerSymbol,
    symbol: str,
    price: float,
    timestamp: float,
    result: BacktestResult,
    settings: Settings,
    risk: "RiskManager | None",
    *,
    reason: str,
) -> None:
    if ps.total_qty <= 0 or ps.ctx.direction is None:
        return
    await sim.cancel_all(symbol)
    if risk is not None:
        for notional in ps.pending_entry_notional.values():
            risk.on_entry_cancelled(symbol, notional)
    ps.pending_entry_notional.clear()
    side = ps.ctx.direction.tp_side
    ev = await sim.force_market_fill(
        symbol=symbol,
        side=side,
        qty=ps.total_qty,
        price=price,
        link_id=f"{symbol}-{side.value}-{reason}-{ulid.new()}",
        timestamp=timestamp,
    )
    trade = _record_exit(ps, ev, result, reason=reason)
    if risk is not None and trade is not None:
        risk.on_trade_closed(symbol, trade.realized_pnl, trade.qty * trade.exit_price)
    ps.ctx = Context(symbol=symbol, halted=ps.ctx.halted)
    ps.merge_deadline = None


def _record_equity_point(
    result: BacktestResult,
    state: dict[str, _PerSymbol],
    last_close: dict[str, float],
    timestamp: float,
    peak_equity: float,
) -> float:
    realized_net = result.realized_net_running()
    unrealized = 0.0
    for sym, ps in state.items():
        if ps.total_qty <= 0 or ps.avg_entry_price <= 0:
            continue
        mark = last_close.get(sym)
        if mark is None:
            continue
        if ps.ctx.direction is Direction.LONG:
            unrealized += (mark - ps.avg_entry_price) * ps.total_qty
        elif ps.ctx.direction is Direction.SHORT:
            unrealized += (ps.avg_entry_price - mark) * ps.total_qty
    equity = result.initial_equity + realized_net + unrealized
    peak_equity = max(peak_equity, equity)
    drawdown = peak_equity - equity
    result.max_drawdown_value = max(result.max_drawdown_value, drawdown)
    result.ending_equity_value = equity
    period = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m")
    monthly = result.monthly_equity.get(period)
    if monthly is None:
        result.monthly_equity[period] = MonthlyEquityStats(
            period=period,
            peak_equity=equity,
            ending_equity=equity,
        )
    else:
        monthly.update(equity)
    return peak_equity


def _record_account_risk(
    result: BacktestResult,
    state: dict[str, _PerSymbol],
    last_close: dict[str, float],
    last_candle: dict[str, Candle],
    timestamp: float,
    settings: Settings,
) -> bool:
    if not settings.bot.liquidation.enabled or result.initial_equity <= 0:
        return False

    positions: list[PositionRisk] = []
    pending_notional = 0.0
    for sym, ps in state.items():
        pending_notional += sum(ps.pending_entry_notional.values())
        if ps.total_qty <= 0 or ps.avg_entry_price <= 0 or ps.ctx.direction is None:
            continue
        mark = last_close.get(sym)
        if mark is None:
            continue
        candle = last_candle.get(sym)
        adverse = mark
        if candle is not None:
            adverse = candle.low if ps.ctx.direction is Direction.LONG else candle.high
        positions.append(PositionRisk(
            symbol=sym,
            direction=ps.ctx.direction,
            qty=ps.total_qty,
            avg_entry=ps.avg_entry_price,
            mark=mark,
            adverse_mark=adverse,
        ))

    inp = AccountRiskInput(
        initial_equity=result.initial_equity,
        realized_net=result.realized_net_running(),
        positions=tuple(positions),
        pending_entry_notional=pending_notional,
        leverage=settings.bot.sizing.leverage,
        maintenance_margin_rate=settings.bot.liquidation.maintenance_margin_rate,
        taker_exit_bps=settings.bot.liquidation.taker_exit_bps
        if settings.bot.liquidation.taker_exit_bps is not None
        else settings.bot.fees.taker_bps,
        funding_stress_bps=settings.bot.liquidation.funding_stress_bps,
        margin_mode=MarginMode(settings.bot.account.margin_mode),
    )
    snap = assess_account_risk(
        inp,
        near_liq_buffer_pct=settings.bot.liquidation.near_liq_buffer_pct,
    )
    result.margin_ratio_max = max(result.margin_ratio_max, snap.margin_ratio)
    if positions:
        result.min_liq_distance_pct = min(result.min_liq_distance_pct, snap.min_liq_distance_pct)
    result.worst_unrealized_loss = min(result.worst_unrealized_loss, snap.worst_unrealized_loss)
    result.final_open_exposure = snap.final_open_exposure
    result.max_initial_margin = max(result.max_initial_margin, snap.initial_margin)
    result.min_available_balance = min(result.min_available_balance, snap.available_balance)

    if result._last_risk_ts is not None and snap.worst_unrealized_loss < 0:
        result.time_in_recovery += max(0.0, timestamp - result._last_risk_ts)
    result._last_risk_ts = timestamp

    if snap.near_liquidation:
        result.near_liquidation = True
        result.near_liquidation_events.append(LiquidationEvent(
            timestamp=timestamp,
            symbol=_worst_position_symbol(snap.positions),
            reason="near_liquidation",
            margin_ratio=snap.margin_ratio,
            min_liq_distance_pct=snap.min_liq_distance_pct,
            equity=snap.equity,
            maintenance_margin=snap.maintenance_margin,
        ))
    if snap.liquidated:
        result.liquidated = True
        result.liquidation_events.append(LiquidationEvent(
            timestamp=timestamp,
            symbol=_worst_position_symbol(snap.positions),
            reason="liquidated",
            margin_ratio=snap.margin_ratio,
            min_liq_distance_pct=snap.min_liq_distance_pct,
            equity=snap.adverse_equity,
            maintenance_margin=snap.maintenance_margin,
        ))
        return True
    return False


def _worst_position_symbol(positions) -> str | None:
    if not positions:
        return None
    return min(positions, key=lambda p: p.distance_pct).symbol


async def _drain_events(
    sim: Simulator, ps: _PerSymbol, params: Params, factory, result: BacktestResult,
    symbol: str, settings: Settings, risk: "RiskManager | None" = None,
) -> None:
    while not sim._user_q.empty():  # noqa: SLF001
        ev = sim._user_q.get_nowait()  # noqa: SLF001
        if isinstance(ev, ExecutionEvent) and ev.symbol == symbol:
            # Determine purpose from link_id (entry/tp/merge).
            parts = ev.link_id.split("-")
            purpose = parts[2] if len(parts) >= 3 else "entry"
            if purpose == "entry":
                _record_entry(ps, ev)
                # Order has filled; it's no longer "pending" — but the notional
                # is now backed by an open position, so leave it counted in the cap.
                ps.pending_entry_notional.pop(ev.link_id, None)
                decision = sm.step(
                    ps.ctx,
                    EntryFilled(link_id=ev.link_id, qty=ev.qty, price=ev.price, timestamp=ev.timestamp),
                    params, link_id_factory=factory,
                )
            else:
                # TP or merge close — record realized PnL.
                trade = _record_exit(ps, ev, result, reason="tp")
                if risk is not None and trade is not None:
                    notional_closed = trade.qty * trade.exit_price
                    risk.on_trade_closed(symbol, trade.realized_pnl, notional_closed)
                decision = sm.step(
                    ps.ctx,
                    TPFilled(link_id=ev.link_id, qty=ev.qty, price=ev.price, timestamp=ev.timestamp),
                    params, link_id_factory=factory,
                )
            ps.ctx = decision.ctx
            await _execute_actions(sim, decision.actions, symbol, ps, risk)
        elif isinstance(ev, OrderEvent):
            # Risk-blocked entries surface as synthetic rejections; roll the SM back.
            if ev.status == "rejected":
                parts = ev.link_id.split("-")
                purpose = OrderPurpose.ENTRY
                if len(parts) >= 3:
                    try:
                        purpose = OrderPurpose(parts[2])
                    except ValueError:
                        pass
                decision = sm.step(
                    ps.ctx,
                    OrderRejected(link_id=ev.link_id, purpose=purpose, timestamp=ev.timestamp),
                    params, link_id_factory=factory,
                )
                ps.ctx = decision.ctx
                await _execute_actions(sim, decision.actions, symbol, ps, risk)
        elif isinstance(ev, PositionEvent):
            pass


async def _execute_actions(
    sim: Simulator, actions: tuple, symbol: str, ps: _PerSymbol,
    risk: "RiskManager | None" = None,
) -> None:
    for a in actions:
        if isinstance(a, PlaceEntry):
            notional = a.qty * a.price
            if risk is not None:
                ok, reason = risk.check_can_place_entry(symbol, notional)
                if not ok:
                    # Block the entry; SM still thinks pending_entry_link_id is set,
                    # so simulate a synthetic rejection by clearing it on next cancel.
                    # Simpler: just skip placement; the SM will cancel the link on next
                    # CandleClose (entry-pending → cancel + re-evaluate). But our SM
                    # already moved to ENTRY_PENDING / IN_POSITION_TP_PENDING with the
                    # link_id set, so the absence of the order means the SM will
                    # eventually re-issue or cancel it. For correctness, emit a
                    # rejection back through the user_q so the SM rolls back cleanly.
                    await sim._user_q.put(  # noqa: SLF001
                        OrderEvent(link_id=a.link_id, symbol=symbol, status="rejected",
                                   timestamp=0.0, reason=reason)
                    )
                    continue
            ack = await sim.place_limit(symbol, a.direction.entry_side, a.qty, a.price, a.link_id)
            if risk is not None and ack.accepted:
                risk.on_entry_placed(symbol, notional)
                ps.pending_entry_notional[a.link_id] = notional
        elif isinstance(a, PlaceTP):
            await sim.place_limit(symbol, a.direction.tp_side, a.qty, a.price, a.link_id)
        elif isinstance(a, PlaceMergeTP):
            await sim.place_limit(symbol, a.direction.tp_side, a.qty, a.price, a.link_id)
        elif isinstance(a, CancelEntry):
            await sim.cancel(symbol, a.link_id)
            if risk is not None:
                released = ps.pending_entry_notional.pop(a.link_id, 0.0)
                if released:
                    risk.on_entry_cancelled(symbol, released)
        elif isinstance(a, CancelAllTPs):
            orders = await sim.get_open_orders(symbol)
            for o in orders:
                if o.purpose in (OrderPurpose.TP, OrderPurpose.MERGE):
                    await sim.cancel(symbol, o.link_id)
        elif isinstance(a, StartMergeTimer):
            ps.merge_deadline = a.deadline
        elif isinstance(a, ClearMergeTimer):
            ps.merge_deadline = None


def _record_entry(ps: _PerSymbol, ev: ExecutionEvent) -> None:
    direction = Direction.LONG if ev.side is Side.BUY else Direction.SHORT
    new_total = ps.total_qty + ev.qty
    if new_total > 0:
        ps.avg_entry_price = (ps.avg_entry_price * ps.total_qty + ev.price * ev.qty) / new_total
    ps.total_qty = new_total
    if ps.entry_ts_for_lot is None:
        ps.entry_ts_for_lot = ev.timestamp
    # Keep signed: positive = cost, negative = rebate.
    ps.accumulated_fees += ev.fee


def _record_exit(
    ps: _PerSymbol,
    ev: ExecutionEvent,
    result: BacktestResult,
    *,
    reason: str,
) -> "TradeRecord | None":
    if ps.total_qty == 0:
        return None
    qty_closed = min(ev.qty, ps.total_qty)
    direction = Direction.SHORT if ev.side is Side.BUY else Direction.LONG
    if direction is Direction.LONG:
        pnl = (ev.price - ps.avg_entry_price) * qty_closed
    else:
        pnl = (ps.avg_entry_price - ev.price) * qty_closed
    # Prorate accumulated entry fees to the qty being closed; keep the rest
    # for the residual position. Then add this close's own fee.
    proration = qty_closed / ps.total_qty if ps.total_qty > 0 else 1.0
    entry_fee_share = ps.accumulated_fees * proration
    fees = entry_fee_share + ev.fee
    ps.accumulated_fees -= entry_fee_share
    trade = TradeRecord(
        symbol=ev.symbol,
        direction=direction,
        entry_ts=ps.entry_ts_for_lot or ev.timestamp,
        exit_ts=ev.timestamp,
        qty=qty_closed,
        avg_entry=ps.avg_entry_price,
        exit_price=ev.price,
        realized_pnl=pnl,
        fees=fees,
        exit_reason=reason,
    )
    result.trades.append(trade)
    ps.total_qty -= qty_closed
    if ps.total_qty == 0:
        ps.avg_entry_price = 0.0
        ps.entry_ts_for_lot = None
        ps.accumulated_fees = 0.0
    return trade
