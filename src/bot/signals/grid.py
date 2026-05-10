"""Grid signal — anchored mean-reversion at fixed price levels.

Anchor = SMA(anchor_period). Once price moves more than `entry_bps` away from
the anchor in either direction, fire a signal. Don't fire again at the same
level — only re-fire after price moves another `step_bps` further away.
Reset the level tracker when price returns to the neutral zone (within
entry_bps of anchor).

This is the closest fit to the classic "grid bot" pattern within the existing
SignalEngine surface — pairs naturally with merge-at-BEP since each step
deeper into the deviation layers another entry, and the auto-merge target
sits just inside the anchor-side of BEP.
"""

from __future__ import annotations

from collections import deque

from bot.models import Candle, Direction, Signal
from bot.signals.base import SignalEngine, register


class _GridState:
    __slots__ = ("closes", "last_long_price", "last_short_price")

    def __init__(self, period: int):
        self.closes: deque[float] = deque(maxlen=period)
        self.last_long_price: float | None = None
        self.last_short_price: float | None = None


@register("grid")
class GridSignal(SignalEngine):
    def __init__(
        self,
        anchor_period: int = 200,
        entry_bps: float = 50.0,
        step_bps: float = 30.0,
    ):
        if anchor_period < 2:
            raise ValueError("anchor_period must be >= 2")
        if entry_bps <= 0 or step_bps <= 0:
            raise ValueError("entry_bps and step_bps must be > 0")
        self.anchor_period = anchor_period
        self.entry_bps = entry_bps
        self.step_bps = step_bps
        self._state: dict[str, _GridState] = {}

    def warmup_bars(self) -> int:
        return self.anchor_period

    def on_candle(self, candle: Candle) -> Signal | None:
        st = self._state.setdefault(candle.symbol, _GridState(self.anchor_period))
        # Compute anchor from PRIOR closes (lagged by 1) so the current candle's
        # price doesn't dilute its own deviation measurement.
        if len(st.closes) < self.anchor_period:
            st.closes.append(candle.close)
            return None

        anchor = sum(st.closes) / len(st.closes)
        # Append AFTER computing the anchor; deque drops the oldest as needed.
        st.closes.append(candle.close)
        if anchor <= 0:
            return None
        deviation_bps = (candle.close - anchor) / anchor * 10_000.0

        if deviation_bps <= -self.entry_bps:
            # Below anchor — LONG zone.
            if st.last_long_price is None:
                st.last_long_price = candle.close
                return Signal(candle.symbol, Direction.LONG, candle.timestamp)
            # Re-fire only if price has dropped another `step_bps` from last fire.
            step_threshold = st.last_long_price * (1.0 - self.step_bps / 10_000.0)
            if candle.close <= step_threshold:
                st.last_long_price = candle.close
                return Signal(candle.symbol, Direction.LONG, candle.timestamp)
            return None

        if deviation_bps >= self.entry_bps:
            # Above anchor — SHORT zone.
            if st.last_short_price is None:
                st.last_short_price = candle.close
                return Signal(candle.symbol, Direction.SHORT, candle.timestamp)
            step_threshold = st.last_short_price * (1.0 + self.step_bps / 10_000.0)
            if candle.close >= step_threshold:
                st.last_short_price = candle.close
                return Signal(candle.symbol, Direction.SHORT, candle.timestamp)
            return None

        # In neutral zone — reset level trackers so a fresh excursion starts clean.
        st.last_long_price = None
        st.last_short_price = None
        return None
