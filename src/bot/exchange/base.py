from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Union

from bot.models import (
    Candle,
    ExecutionEvent,
    Instrument,
    Order,
    OrderAck,
    OrderEvent,
    Position,
    PositionEvent,
    Side,
)

UserEvent = Union[OrderEvent, ExecutionEvent, PositionEvent]


class ExchangeAdapter(ABC):
    """The only surface strategy code touches. Live, testnet, simulator implement this."""

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def get_instrument(self, symbol: str) -> Instrument: ...

    @abstractmethod
    async def place_limit(
        self,
        symbol: str,
        side: Side,
        qty: float,
        price: float,
        link_id: str,
        *,
        reduce_only: bool = False,
        post_only: bool = True,
    ) -> OrderAck: ...

    async def close_position_market(
        self,
        symbol: str,
        side: Side,
        link_id: str,
    ) -> OrderAck:
        raise NotImplementedError("close_position_market is not implemented by this adapter")

    @abstractmethod
    async def cancel(self, symbol: str, link_id: str) -> None: ...

    @abstractmethod
    async def cancel_all(self, symbol: str) -> None: ...

    @abstractmethod
    async def get_position(self, symbol: str) -> Position: ...

    @abstractmethod
    async def get_open_orders(self, symbol: str) -> list[Order]: ...

    @abstractmethod
    def stream_klines(self, symbols: list[str], interval: str = "1") -> AsyncIterator[Candle]: ...

    @abstractmethod
    def stream_user_events(self) -> AsyncIterator[UserEvent]: ...

    def ws_status(self) -> dict:
        """Optional: return WebSocket connection health. Empty when N/A (e.g. simulator)."""
        return {}
