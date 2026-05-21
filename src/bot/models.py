from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Literal


class Side(str, Enum):
    BUY = "Buy"
    SELL = "Sell"

    @property
    def opposite(self) -> "Side":
        return Side.SELL if self is Side.BUY else Side.BUY


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"

    @property
    def entry_side(self) -> Side:
        return Side.BUY if self is Direction.LONG else Side.SELL

    @property
    def tp_side(self) -> Side:
        return Side.SELL if self is Direction.LONG else Side.BUY


class OrderPurpose(str, Enum):
    ENTRY = "entry"
    TP = "tp"
    MERGE = "merge"


@dataclass(frozen=True)
class Candle:
    symbol: str
    timestamp: float  # candle close time, unix seconds
    open: float
    high: float
    low: float
    close: float
    volume: float
    confirm: bool = True


@dataclass(frozen=True)
class Signal:
    symbol: str
    direction: Direction
    timestamp: float
    size_scale: float = 1.0
    allow_new_position: bool = True
    allow_layering: bool = True


@dataclass(frozen=True)
class Instrument:
    symbol: str
    tick_size: Decimal
    qty_step: Decimal
    min_notional: Decimal
    min_qty: Decimal


@dataclass(frozen=True)
class Order:
    link_id: str
    symbol: str
    side: Side
    purpose: OrderPurpose
    qty: float
    price: float


@dataclass(frozen=True)
class OrderAck:
    link_id: str
    order_id: str
    accepted: bool
    reason: str | None = None


@dataclass(frozen=True)
class Fill:
    link_id: str
    symbol: str
    side: Side
    qty: float
    price: float
    timestamp: float
    fee: float = 0.0
    is_maker: bool = True


@dataclass(frozen=True)
class Position:
    symbol: str
    size: float  # signed: + long, - short
    avg_price: float  # BEP

    @property
    def is_flat(self) -> bool:
        return self.size == 0.0

    @property
    def direction(self) -> Direction | None:
        if self.size > 0:
            return Direction.LONG
        if self.size < 0:
            return Direction.SHORT
        return None


# Exchange event union — produced by streams, consumed by orchestrator.

@dataclass(frozen=True)
class OrderEvent:
    link_id: str
    symbol: str
    status: Literal["accepted", "rejected", "cancelled", "filled", "partial"]
    timestamp: float
    reason: str | None = None


@dataclass(frozen=True)
class ExecutionEvent:
    link_id: str
    symbol: str
    side: Side
    qty: float
    price: float
    timestamp: float
    fee: float = 0.0
    is_maker: bool = True


@dataclass(frozen=True)
class PositionEvent:
    symbol: str
    size: float
    avg_price: float
    timestamp: float
