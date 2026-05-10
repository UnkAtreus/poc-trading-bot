"""Z-score mean-reversion signal.

z = (close - SMA(period)) / stddev(period)

LONG when z < -threshold (price unusually low).
SHORT when z > +threshold (price unusually high).

A more flexible cousin of Bollinger Bands — same idea, but you tune the
lookback and the threshold separately.
"""

from __future__ import annotations

import math
from collections import deque

from bot.models import Candle, Direction, Signal
from bot.signals.base import SignalEngine, register


@register("zscore")
class ZScore(SignalEngine):
    def __init__(self, period: int = 50, threshold: float = 2.0):
        if period < 2:
            raise ValueError("period must be >= 2")
        if threshold <= 0:
            raise ValueError("threshold must be > 0")
        self.period = period
        self.threshold = threshold
        self._closes: dict[str, deque[float]] = {}

    def warmup_bars(self) -> int:
        return self.period

    def on_candle(self, candle: Candle) -> Signal | None:
        st = self._closes.setdefault(candle.symbol, deque(maxlen=self.period))
        st.append(candle.close)
        if len(st) < self.period:
            return None
        n = len(st)
        mean = sum(st) / n
        var = sum((x - mean) * (x - mean) for x in st) / n
        std = math.sqrt(var)
        if std == 0:
            return None
        z = (candle.close - mean) / std
        if z < -self.threshold:
            return Signal(candle.symbol, Direction.LONG, candle.timestamp)
        if z > self.threshold:
            return Signal(candle.symbol, Direction.SHORT, candle.timestamp)
        return None
