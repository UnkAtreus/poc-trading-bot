"""Backtest fill engine implementing ExchangeAdapter.

Drives candles through the same orchestrator code path as the live bot.
The simulator is deterministic and synchronous-feeling: it queues orders
and resolves them against the next candle's OHLC.

Naive fill rules (no slippage, no partial fills):
- Buy LIMIT @ P fills if candle.low  <= P
- Sell LIMIT @ P fills if candle.high >= P
- If both could fill in the same candle, resolve in OHLC order using the
  up-bar / down-bar heuristic (close>=open => O,H,L,C; else O,L,H,C).

Realistic mode keeps the same candle-only data source but adds conservative
execution penalties: order activation latency, delayed cancellation, minimum
notional/qty rejection, adverse slippage, pass-through-only fills, and partial
fills when price barely crosses the limit.

Known limitation (TODO): when a layered ENTRY and an OLD TP would both fill
in the same candle, the SM's CancelAllTPs cannot fire mid-candle. Live
trading doesn't have this race because orders sequence in milliseconds.
This makes a small subset of backtest results pessimistic. Mitigation:
test against history with sparser signal cadence (placeholder_random with
low p_long/p_short).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from decimal import Decimal

from bot.backtest.execution import BacktestExecutionConfig, ExecutionStats
from bot.exchange.base import ExchangeAdapter, UserEvent
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


@dataclass
class _SimOrder:
    link_id: str
    symbol: str
    side: Side
    qty: float
    price: float
    purpose: OrderPurpose = OrderPurpose.ENTRY  # not actually used by sim, but useful for fees
    reduce_only: bool = False
    active_after_ts: float = 0.0
    cancel_requested_ts: float | None = None
    cancel_effective_ts: float | None = None


@dataclass
class _SimPosition:
    size: float = 0.0  # signed
    avg_price: float = 0.0


class Simulator(ExchangeAdapter):
    """Deterministic in-process simulator. Drive it with `feed_candle(candle)`."""

    def __init__(
        self,
        instruments: dict[str, Instrument] | None = None,
        maker_bps: float = -1.0,
        taker_bps: float = 5.5,
        execution: BacktestExecutionConfig | None = None,
    ):
        self._instruments = instruments or {}
        self._open: dict[str, list[_SimOrder]] = {}  # symbol -> orders
        self._positions: dict[str, _SimPosition] = {}
        self._user_q: asyncio.Queue[UserEvent] = asyncio.Queue()
        self._kline_q: asyncio.Queue[Candle] = asyncio.Queue()
        self._maker_bps = maker_bps
        self._taker_bps = taker_bps
        self._fills: list[ExecutionEvent] = []  # for reporting / tests
        self._execution = execution or BacktestExecutionConfig.naive()
        self._stats = ExecutionStats()
        self._now = 0.0
        self._last_candle_ts: dict[str, float] = {}

    # ---- ExchangeAdapter ----

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def get_instrument(self, symbol: str) -> Instrument:
        if symbol not in self._instruments:
            # Default sane instrument for tests.
            self._instruments[symbol] = Instrument(
                symbol=symbol,
                tick_size=Decimal("0.01"),
                qty_step=Decimal("0.0001"),
                min_notional=Decimal("5"),
                min_qty=Decimal("0.0001"),
            )
        return self._instruments[symbol]

    async def place_limit(
        self,
        symbol,
        side,
        qty,
        price,
        link_id,
        *,
        reduce_only: bool = False,
        post_only: bool = True,
    ) -> OrderAck:
        self._stats.placed_orders += 1
        reason = await self._rejection_reason(symbol, qty, price)
        if reason is not None:
            self._stats.record_rejection(reason)
            await self._user_q.put(OrderEvent(
                link_id=link_id,
                symbol=symbol,
                status="rejected",
                timestamp=self._now,
                reason=reason,
            ))
            return OrderAck(link_id=link_id, order_id="", accepted=False, reason=reason)

        self._stats.accepted_orders += 1
        self._open.setdefault(symbol, []).append(
            _SimOrder(
                link_id=link_id,
                symbol=symbol,
                side=side,
                qty=qty,
                price=price,
                purpose=self._purpose_from_link(link_id),
                reduce_only=reduce_only,
                active_after_ts=self._now + self._execution.latency_seconds,
            )
        )
        # Fire an "accepted" order event.
        await self._user_q.put(OrderEvent(
            link_id=link_id, symbol=symbol, status="accepted", timestamp=self._now
        ))
        return OrderAck(link_id=link_id, order_id=link_id, accepted=True)

    async def force_market_fill(self, symbol: str, side: Side, qty: float, price: float,
                                link_id: str, timestamp: float) -> ExecutionEvent:
        """Inject a taker fill for backtest-only forced exits."""
        order = _SimOrder(
            link_id=link_id,
            symbol=symbol,
            side=side,
            qty=qty,
            price=self._execution_price(side, price),
            purpose=self._purpose_from_link(link_id),
        )
        self._record_slippage(side, qty, price, order.price)
        notional = qty * order.price
        fee = notional * (self._taker_bps / 10_000.0)
        self._apply_position(order)
        ev = ExecutionEvent(
            link_id=link_id,
            symbol=symbol,
            side=side,
            qty=qty,
            price=order.price,
            timestamp=timestamp,
            fee=fee,
            is_maker=False,
        )
        self._fills.append(ev)
        return ev

    async def cancel(self, symbol: str, link_id: str) -> None:
        orders = self._open.get(symbol, [])
        if self._execution.is_realistic:
            for order in orders:
                if order.link_id == link_id and order.cancel_effective_ts is None:
                    order.cancel_requested_ts = self._now
                    order.cancel_effective_ts = self._now + self._execution.cancel_delay_seconds
                    self._stats.cancel_requested += 1
            await self._apply_due_cancels(symbol, self._now)
            return

        kept = [o for o in orders if o.link_id != link_id]
        if len(kept) != len(orders):
            self._stats.cancel_requested += len(orders) - len(kept)
            self._stats.cancel_effective += len(orders) - len(kept)
            await self._user_q.put(OrderEvent(
                link_id=link_id, symbol=symbol, status="cancelled", timestamp=self._now
            ))
        self._open[symbol] = kept

    async def cancel_all(self, symbol: str) -> None:
        if self._execution.is_realistic:
            for order in self._open.get(symbol, []):
                if order.cancel_effective_ts is None:
                    order.cancel_requested_ts = self._now
                    order.cancel_effective_ts = self._now + self._execution.cancel_delay_seconds
                    self._stats.cancel_requested += 1
            await self._apply_due_cancels(symbol, self._now)
            return

        count = len(self._open.get(symbol, []))
        for o in self._open.get(symbol, []):
            await self._user_q.put(OrderEvent(
                link_id=o.link_id, symbol=symbol, status="cancelled", timestamp=self._now
            ))
        self._stats.cancel_requested += count
        self._stats.cancel_effective += count
        self._open[symbol] = []

    async def get_position(self, symbol: str) -> Position:
        p = self._positions.get(symbol, _SimPosition())
        return Position(symbol=symbol, size=p.size, avg_price=p.avg_price)

    async def get_open_orders(self, symbol: str) -> list[Order]:
        return [
            Order(link_id=o.link_id, symbol=o.symbol, side=o.side, purpose=o.purpose,
                  qty=o.qty, price=o.price)
            for o in self._open.get(symbol, [])
        ]

    async def stream_klines(self, symbols, interval="1") -> AsyncIterator[Candle]:
        while True:
            yield await self._kline_q.get()

    async def stream_user_events(self) -> AsyncIterator[UserEvent]:
        while True:
            yield await self._user_q.get()

    # ---- Driver API used by the backtest runner ----

    async def feed_candle(self, candle: Candle) -> None:
        """Resolve open orders against this candle's OHLC, then forward the candle."""
        if self._execution.is_realistic:
            await self._resolve_fills_realistic(candle)
        else:
            await self._resolve_fills_naive(candle)
        self._last_candle_ts[candle.symbol] = candle.timestamp
        self._now = candle.timestamp
        await self._kline_q.put(candle)

    @property
    def fills(self) -> list[ExecutionEvent]:
        return list(self._fills)

    @property
    def execution_stats(self) -> ExecutionStats:
        return self._stats

    # ---- Internals ----

    @staticmethod
    def _purpose_from_link(link_id: str) -> OrderPurpose:
        # Format: {symbol}-{side}-{purpose}-{...}. Best-effort parse.
        parts = link_id.split("-")
        if len(parts) >= 3:
            try:
                return OrderPurpose(parts[2])
            except ValueError:
                pass
        return OrderPurpose.ENTRY

    async def _resolve_fills_naive(self, candle: Candle) -> None:
        orders = self._open.get(candle.symbol, [])
        if not orders:
            return
        # Determine traversal of the candle's price path.
        path = self._price_path(candle)
        remaining: list[_SimOrder] = list(orders)
        filled: list[_SimOrder] = []
        for px in path:
            still: list[_SimOrder] = []
            for o in remaining:
                if (o.side is Side.BUY and px <= o.price) or (
                    o.side is Side.SELL and px >= o.price
                ):
                    filled.append(o)
                else:
                    still.append(o)
            remaining = still
            if not remaining:
                break
        self._open[candle.symbol] = remaining
        for o in filled:
            self._stats.full_fills += 1
            await self._fill(o, o.qty, o.price, candle.timestamp)

    async def _resolve_fills_realistic(self, candle: Candle) -> None:
        if not self._open.get(candle.symbol):
            return

        for px, ts in self._timed_price_path(candle):
            await self._apply_due_cancels(candle.symbol, ts)
            orders = self._open.get(candle.symbol, [])
            if not orders:
                return

            remaining: list[_SimOrder] = []
            for order in orders:
                if ts < order.active_after_ts:
                    remaining.append(order)
                    continue
                fill_qty = self._realistic_fill_qty(order, px)
                if fill_qty <= 0:
                    remaining.append(order)
                    continue

                fill_price = self._execution_price(order.side, order.price)
                self._record_slippage(order.side, fill_qty, order.price, fill_price)
                if order.cancel_requested_ts is not None:
                    self._stats.cancel_race_fills += 1

                if fill_qty >= order.qty - 1e-12:
                    self._stats.full_fills += 1
                    await self._fill(order, order.qty, fill_price, ts)
                    continue

                order.qty -= fill_qty
                self._stats.partial_fills += 1
                await self._fill(order, fill_qty, fill_price, ts)
                remaining.append(order)

            self._open[candle.symbol] = remaining
        await self._apply_due_cancels(candle.symbol, candle.timestamp)

    @staticmethod
    def _price_path(c: Candle) -> tuple[float, ...]:
        if c.close >= c.open:
            return (c.open, c.high, c.low, c.close)
        return (c.open, c.low, c.high, c.close)

    def _timed_price_path(self, c: Candle) -> tuple[tuple[float, float], ...]:
        previous_ts = self._last_candle_ts.get(c.symbol)
        duration = c.timestamp - previous_ts if previous_ts is not None else 60.0
        if duration <= 0:
            duration = 60.0
        start = c.timestamp - duration
        prices = self._price_path(c)
        return (
            (prices[0], start),
            (prices[1], start + duration / 3.0),
            (prices[2], start + duration * 2.0 / 3.0),
            (prices[3], c.timestamp),
        )

    def _realistic_fill_qty(self, order: _SimOrder, path_price: float) -> float:
        if order.price <= 0:
            return 0.0
        if order.side is Side.BUY:
            penetration_bps = (order.price - path_price) / order.price * 10_000.0
        else:
            penetration_bps = (path_price - order.price) / order.price * 10_000.0
        cfg = self._execution
        if penetration_bps + 1e-12 < cfg.pass_through_bps:
            return 0.0
        if cfg.full_fill_bps <= cfg.pass_through_bps or penetration_bps >= cfg.full_fill_bps:
            return order.qty
        span = cfg.full_fill_bps - cfg.pass_through_bps
        progress = max(0.0, min(1.0, (penetration_bps - cfg.pass_through_bps) / span))
        min_ratio = cfg.min_partial_fill_pct / 100.0
        ratio = min_ratio + (1.0 - min_ratio) * progress
        return max(0.0, min(order.qty, order.qty * ratio))

    async def _apply_due_cancels(self, symbol: str, ts: float) -> None:
        orders = self._open.get(symbol, [])
        if not orders:
            return
        kept: list[_SimOrder] = []
        for order in orders:
            if order.cancel_effective_ts is not None and order.cancel_effective_ts <= ts:
                self._stats.cancel_effective += 1
                await self._user_q.put(OrderEvent(
                    link_id=order.link_id,
                    symbol=symbol,
                    status="cancelled",
                    timestamp=order.cancel_effective_ts,
                ))
            else:
                kept.append(order)
        self._open[symbol] = kept

    async def _rejection_reason(self, symbol: str, qty: float, price: float) -> str | None:
        if not self._execution.is_realistic:
            return None
        inst = await self.get_instrument(symbol)
        qty_dec = Decimal(str(qty))
        price_dec = Decimal(str(price))
        if qty_dec < inst.min_qty:
            return f"qty_below_min({qty_dec} < {inst.min_qty})"
        notional = qty_dec * price_dec
        if notional < inst.min_notional:
            return f"notional_below_min({notional} < {inst.min_notional})"
        return None

    def _execution_price(self, side: Side, price: float) -> float:
        if not self._execution.is_realistic or self._execution.slippage_bps <= 0:
            return price
        delta = price * (self._execution.slippage_bps / 10_000.0)
        return price + delta if side is Side.BUY else price - delta

    def _record_slippage(self, side: Side, qty: float, base_price: float, fill_price: float) -> None:
        if not self._execution.is_realistic:
            return
        adverse = fill_price - base_price if side is Side.BUY else base_price - fill_price
        self._stats.slippage_cost += max(0.0, adverse) * qty

    async def _fill(self, order: _SimOrder, qty: float, price: float, ts: float) -> None:
        # Maker since we use limit @ post-only; charge maker fee.
        notional = qty * price
        fee = notional * (self._maker_bps / 10_000.0)
        fill_order = _SimOrder(
            link_id=order.link_id,
            symbol=order.symbol,
            side=order.side,
            qty=qty,
            price=price,
            purpose=order.purpose,
            reduce_only=order.reduce_only,
        )
        self._apply_position(fill_order)
        ev = ExecutionEvent(
            link_id=order.link_id,
            symbol=order.symbol,
            side=order.side,
            qty=qty,
            price=price,
            timestamp=ts,
            fee=fee,
            is_maker=True,
        )
        self._fills.append(ev)
        await self._user_q.put(ev)
        # Position event reflecting new BEP / size.
        p = self._positions[order.symbol]
        await self._user_q.put(PositionEvent(
            symbol=order.symbol, size=p.size, avg_price=p.avg_price, timestamp=ts
        ))

    def _apply_position(self, order: _SimOrder) -> None:
        p = self._positions.setdefault(order.symbol, _SimPosition())
        signed_qty = order.qty if order.side is Side.BUY else -order.qty
        new_size = p.size + signed_qty

        # If reducing or flipping, BEP follows standard avg-price math.
        if p.size == 0 or (p.size > 0 and signed_qty > 0) or (p.size < 0 and signed_qty < 0):
            # Adding to position
            total_abs = abs(p.size) + abs(signed_qty)
            if total_abs == 0:
                p.avg_price = 0.0
            else:
                p.avg_price = (
                    p.avg_price * abs(p.size) + order.price * abs(signed_qty)
                ) / total_abs
        else:
            # Reducing or flipping
            if (p.size > 0 and new_size >= 0) or (p.size < 0 and new_size <= 0):
                # Pure reduction; avg unchanged
                if new_size == 0:
                    p.avg_price = 0.0
            else:
                # Flipped sign; avg becomes the fill price for the residual
                p.avg_price = order.price

        p.size = new_size
