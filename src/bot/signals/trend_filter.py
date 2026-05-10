"""Trend-filter wrapper.

Wraps another SignalEngine. Only forwards the inner signal when the market is
"choppy enough" — measured as `|EMA_fast - EMA_slow| / EMA_slow * 10000 bps`.

When the trend strength is BELOW `max_trend_bps`, the inner signal passes through.
Above that threshold, the wrapper suppresses signals (regardless of inner output).

This is the natural defense for the merge-at-BEP architecture: the architecture
is a passive martingale that bleeds in strong trends. Suppressing entries during
trends keeps powder dry until the market re-enters its normal chop regime.

Examples (CLI):
    --signals "trend_filter:inner=bollinger_bands:max_trend_bps=30"
    --signals "trend_filter:inner=zscore:ema_fast=30:ema_slow=120:max_trend_bps=25"
"""

from __future__ import annotations

from bot.models import Candle, Signal
from bot.signals.base import SignalEngine, register


class _Trend:
    __slots__ = ("fast", "slow")

    def __init__(self):
        self.fast: float | None = None
        self.slow: float | None = None


@register("trend_filter")
class TrendFilter(SignalEngine):
    def __init__(
        self,
        inner: str = "bollinger_bands",
        ema_fast: int = 30,
        ema_slow: int = 120,
        max_trend_bps: float = 30.0,
        # Inner-signal params can be passed as flat keys with a `inner_` prefix.
        # E.g. inner_period=20, inner_num_std=2.0 → forwarded as period=20, num_std=2.0.
        **inner_kwargs,
    ):
        from bot.signals.base import build  # avoid cycle at import time

        if ema_fast < 1 or ema_slow < 1 or ema_fast >= ema_slow:
            raise ValueError("require ema_fast >= 1 and ema_fast < ema_slow")
        if max_trend_bps <= 0:
            raise ValueError("max_trend_bps must be > 0")
        self.ema_fast_period = ema_fast
        self.ema_slow_period = ema_slow
        self.max_trend_bps = max_trend_bps
        self._alpha_fast = 2.0 / (ema_fast + 1)
        self._alpha_slow = 2.0 / (ema_slow + 1)
        self._trend: dict[str, _Trend] = {}

        # Inner params come in with the `inner_` prefix to avoid name collisions.
        inner_params: dict = {}
        for k, v in inner_kwargs.items():
            if k.startswith("inner_"):
                inner_params[k[len("inner_"):]] = v
        self._inner = build(inner, inner_params)

    def warmup_bars(self) -> int:
        # Enough bars to seed both EMAs and the inner signal.
        return max(self.ema_slow_period + 1, self._inner.warmup_bars())

    def on_candle(self, candle: Candle) -> Signal | None:
        st = self._trend.setdefault(candle.symbol, _Trend())
        if st.fast is None:
            st.fast = candle.close
            st.slow = candle.close
        else:
            st.fast = self._alpha_fast * candle.close + (1 - self._alpha_fast) * st.fast
            st.slow = self._alpha_slow * candle.close + (1 - self._alpha_slow) * st.slow

        # Always feed the inner so its internal state stays warm.
        sig = self._inner.on_candle(candle)
        if sig is None:
            return None

        if st.slow == 0:
            return None
        trend_bps = abs(st.fast - st.slow) / st.slow * 10_000.0
        if trend_bps > self.max_trend_bps:
            return None  # suppressed: market is trending too hard
        return sig
