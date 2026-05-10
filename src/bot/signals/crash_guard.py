"""Crash guard wrapper.

Suppresses LONG signals when BTC is in a sharp downside regime. The wrapped
signal still receives every candle so its internal state stays warm.
"""

from __future__ import annotations

from collections import deque

from bot.models import Candle, Direction, Signal
from bot.signals.base import SignalEngine, register


@register("crash_guard")
class CrashGuard(SignalEngine):
    def __init__(
        self,
        inner: str = "trend_filter",
        btc_symbol: str = "BTCUSDT",
        btc_ema_period: int = 200,
        btc_return_bars: int = 1440,
        btc_drop_bps: float = 500.0,
        block_shorts: bool = False,
        **inner_kwargs,
    ):
        from bot.signals.base import build  # avoid cycle at import time

        if btc_ema_period < 1:
            raise ValueError("btc_ema_period must be >= 1")
        if btc_return_bars < 1:
            raise ValueError("btc_return_bars must be >= 1")
        if btc_drop_bps <= 0:
            raise ValueError("btc_drop_bps must be > 0")
        self.btc_symbol = btc_symbol
        self.btc_ema_period = btc_ema_period
        self.btc_return_bars = btc_return_bars
        self.btc_drop_bps = btc_drop_bps
        self.block_shorts = block_shorts
        self._alpha = 2.0 / (btc_ema_period + 1)
        self._btc_ema: float | None = None
        self._btc_closes: deque[float] = deque(maxlen=btc_return_bars + 1)
        self._crash_active = False

        inner_params: dict = {}
        for k, v in inner_kwargs.items():
            if k.startswith("inner_"):
                inner_params[k[len("inner_"):]] = v
        self._inner = build(inner, inner_params)

    def warmup_bars(self) -> int:
        return max(self.btc_ema_period, self.btc_return_bars, self._inner.warmup_bars())

    def on_candle(self, candle: Candle) -> Signal | None:
        if candle.symbol == self.btc_symbol:
            self._update_btc_state(candle.close)

        sig = self._inner.on_candle(candle)
        if sig is None:
            return None
        if self._crash_active:
            if sig.direction is Direction.LONG:
                return None
            if self.block_shorts:
                return None
        return sig

    def _update_btc_state(self, close: float) -> None:
        if self._btc_ema is None:
            self._btc_ema = close
        else:
            self._btc_ema = self._alpha * close + (1 - self._alpha) * self._btc_ema
        self._btc_closes.append(close)
        if len(self._btc_closes) <= self.btc_return_bars:
            self._crash_active = False
            return
        old = self._btc_closes[0]
        if old <= 0 or self._btc_ema <= 0:
            self._crash_active = False
            return
        return_bps = (close / old - 1.0) * 10_000.0
        below_ema = close < self._btc_ema
        self._crash_active = below_ema and return_bps <= -self.btc_drop_bps
