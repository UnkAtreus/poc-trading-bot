"""Backtest fill engine implementing ExchangeAdapter.

Drives candles through the same orchestrator code path as the live bot.
The simulator is deterministic and synchronous-feeling: it queues orders
and resolves them against the next candle's OHLC.

Fill rules (no slippage, no partial fills):
- Buy LIMIT @ P fills if candle.low  <= P
- Sell LIMIT @ P fills if candle.high >= P
- If both could fill in the same candle, resolve in OHLC order using the
  up-bar / down-bar heuristic (close>=open => O,H,L,C; else O,L,H,C).

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
from dataclasses import dataclass, field
from decimal import Decimal

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


@dataclass
class _SimPosition:
    size: float = 0.0  # signed
    avg_price: float = 0.0


class Simulator(ExchangeAdapter):
    """Deterministic in-process simulator. Drive it with `feed_candle(candle)`."""

    def __init__(self, instruments: dict[str, Instrument] | None = None,
                 maker_bps: float = -1.0, taker_bps: float = 5.5):
        self._instruments = instruments or {}
        self._open: dict[str, list[_SimOrder]] = {}  # symbol -> orders
        self._positions: dict[str, _SimPosition] = {}
        self._user_q: asyncio.Queue[UserEvent] = asyncio.Queue()
        self._kline_q: asyncio.Queue[Candle] = asyncio.Queue()
        self._maker_bps = maker_bps
        self._taker_bps = taker_bps
        self._fills: list[ExecutionEvent] = []  # for reporting / tests

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
        self._open.setdefault(symbol, []).append(
            _SimOrder(link_id=link_id, symbol=symbol, side=side, qty=qty, price=price,
                      purpose=self._purpose_from_link(link_id))
        )
        # Fire an "accepted" order event.
        await self._user_q.put(OrderEvent(
            link_id=link_id, symbol=symbol, status="accepted", timestamp=0.0
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
            price=price,
            purpose=self._purpose_from_link(link_id),
        )
        notional = qty * price
        fee = notional * (self._taker_bps / 10_000.0)
        self._apply_position(order)
        ev = ExecutionEvent(
            link_id=link_id,
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            timestamp=timestamp,
            fee=fee,
            is_maker=False,
        )
        self._fills.append(ev)
        return ev

    async def cancel(self, symbol: str, link_id: str) -> None:
        orders = self._open.get(symbol, [])
        kept = [o for o in orders if o.link_id != link_id]
        if len(kept) != len(orders):
            await self._user_q.put(OrderEvent(
                link_id=link_id, symbol=symbol, status="cancelled", timestamp=0.0
            ))
        self._open[symbol] = kept

    async def cancel_all(self, symbol: str) -> None:
        for o in self._open.get(symbol, []):
            await self._user_q.put(OrderEvent(
                link_id=o.link_id, symbol=symbol, status="cancelled", timestamp=0.0
            ))
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
        await self._resolve_fills(candle)
        await self._kline_q.put(candle)

    @property
    def fills(self) -> list[ExecutionEvent]:
        return list(self._fills)

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

    async def _resolve_fills(self, candle: Candle) -> None:
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
            await self._fill(o, candle.timestamp)

    @staticmethod
    def _price_path(c: Candle) -> tuple[float, ...]:
        if c.close >= c.open:
            return (c.open, c.high, c.low, c.close)
        return (c.open, c.low, c.high, c.close)

    async def _fill(self, order: _SimOrder, ts: float) -> None:
        # Maker since we use limit @ post-only; charge maker fee.
        notional = order.qty * order.price
        fee = notional * (self._maker_bps / 10_000.0)
        self._apply_position(order)
        ev = ExecutionEvent(
            link_id=order.link_id,
            symbol=order.symbol,
            side=order.side,
            qty=order.qty,
            price=order.price,
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
