from __future__ import annotations

import random

from bot.models import Candle, Direction, Signal
from bot.signals.base import SignalEngine, register


@register("random")
class RandomSignal(SignalEngine):
    """Plumbing-test signal: emits LONG/SHORT/None at fixed probabilities. Seeded for reproducibility."""

    def __init__(self, p_long: float = 0.05, p_short: float = 0.05, seed: int | None = 42):
        if p_long + p_short > 1.0:
            raise ValueError("p_long + p_short must be <= 1.0")
        self.p_long = p_long
        self.p_short = p_short
        self._rng = random.Random(seed)

    def warmup_bars(self) -> int:
        return 0

    def on_candle(self, candle: Candle) -> Signal | None:
        r = self._rng.random()
        if r < self.p_long:
            return Signal(candle.symbol, Direction.LONG, candle.timestamp)
        if r < self.p_long + self.p_short:
            return Signal(candle.symbol, Direction.SHORT, candle.timestamp)
        return None
