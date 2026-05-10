"""EMA crossover — trend-following.

LONG on fast-EMA crossing above slow-EMA.
SHORT on fast-EMA crossing below slow-EMA.

Included for comparison. **Warning:** trend signals tend to lose under
merge-at-BEP because the strategy has no stop-loss; once the trend turns,
the position fades into BEP recovery and accumulates losses if the trend
doesn't reverse cleanly. The mean-reversion signals (Bollinger / z-score /
grid) usually beat this on the same data.
"""

from __future__ import annotations

from bot.models import Candle, Direction, Signal
from bot.signals.base import SignalEngine, register


class _EMAState:
    __slots__ = ("fast", "slow", "warmup_left", "prev_above")

    def __init__(self, warmup: int):
        self.fast: float | None = None
        self.slow: float | None = None
        self.warmup_left: int = warmup
        self.prev_above: bool | None = None


@register("ema_crossover")
class EMACrossover(SignalEngine):
    def __init__(self, fast: int = 9, slow: int = 21):
        if fast < 1 or slow < 1:
            raise ValueError("fast and slow must be >= 1")
        if fast >= slow:
            raise ValueError("fast must be < slow")
        self.fast = fast
        self.slow = slow
        self._alpha_fast = 2.0 / (fast + 1)
        self._alpha_slow = 2.0 / (slow + 1)
        self._state: dict[str, _EMAState] = {}

    def warmup_bars(self) -> int:
        return self.slow + 1

    def on_candle(self, candle: Candle) -> Signal | None:
        st = self._state.setdefault(candle.symbol, _EMAState(self.warmup_bars()))
        if st.fast is None:
            st.fast = candle.close
            st.slow = candle.close
        else:
            st.fast = self._alpha_fast * candle.close + (1 - self._alpha_fast) * st.fast
            st.slow = self._alpha_slow * candle.close + (1 - self._alpha_slow) * st.slow

        if st.warmup_left > 0:
            st.warmup_left -= 1
            st.prev_above = st.fast > st.slow
            return None

        now_above = st.fast > st.slow
        sig: Signal | None = None
        if st.prev_above is not None:
            if not st.prev_above and now_above:
                sig = Signal(candle.symbol, Direction.LONG, candle.timestamp)
            elif st.prev_above and not now_above:
                sig = Signal(candle.symbol, Direction.SHORT, candle.timestamp)
        st.prev_above = now_above
        return sig
