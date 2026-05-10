"""Bollinger Bands mean-reversion signal.

LONG when close drops below the lower band, SHORT when close rises above the upper band.
Classic mean-reversion play; pairs naturally with merge-at-BEP since BEP recovery
expects price to oscillate.
"""

from __future__ import annotations

import math
from collections import deque

from bot.models import Candle, Direction, Signal
from bot.signals.base import SignalEngine, register


@register("bollinger_bands")
class BollingerBands(SignalEngine):
    def __init__(self, period: int = 20, num_std: float = 2.0):
        if period < 2:
            raise ValueError("period must be >= 2")
        if num_std <= 0:
            raise ValueError("num_std must be > 0")
        self.period = period
        self.num_std = num_std
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
        upper = mean + self.num_std * std
        lower = mean - self.num_std * std
        if candle.close < lower:
            return Signal(candle.symbol, Direction.LONG, candle.timestamp)
        if candle.close > upper:
            return Signal(candle.symbol, Direction.SHORT, candle.timestamp)
        return None
