from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from bot.models import Candle, Direction, Signal
from bot.signals.base import SignalEngine, register


@dataclass
class _SymbolState:
    closes: deque[float]
    avg_gain: float | None = None
    avg_loss: float | None = None
    prev_close: float | None = None


@register("placeholder_rsi")
class PlaceholderRSI(SignalEngine):
    """Wilder-style RSI(period). Emits LONG when RSI<oversold, SHORT when >overbought."""

    def __init__(self, period: int = 14, oversold: float = 30.0, overbought: float = 70.0):
        if period < 2:
            raise ValueError("period must be >= 2")
        if not (0 < oversold < overbought < 100):
            raise ValueError("0 < oversold < overbought < 100 required")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self._states: dict[str, _SymbolState] = {}

    def warmup_bars(self) -> int:
        # period+1 candles needed before we can seed and start firing.
        return self.period + 1

    def on_candle(self, candle: Candle) -> Signal | None:
        st = self._states.get(candle.symbol)
        if st is None:
            st = _SymbolState(closes=deque(maxlen=self.period + 1))
            self._states[candle.symbol] = st

        if st.prev_close is None:
            st.prev_close = candle.close
            st.closes.append(candle.close)
            return None

        change = candle.close - st.prev_close
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        st.prev_close = candle.close
        st.closes.append(candle.close)

        if st.avg_gain is None:
            # Need `period` deltas before seeding.
            if len(st.closes) <= self.period:
                return None
            # Seed with simple average of first `period` deltas; do NOT emit
            # on the seeding bar — wait one more candle before firing.
            closes = list(st.closes)
            gains, losses = [], []
            for i in range(1, len(closes)):
                d = closes[i] - closes[i - 1]
                gains.append(max(d, 0.0))
                losses.append(max(-d, 0.0))
            st.avg_gain = sum(gains) / self.period
            st.avg_loss = sum(losses) / self.period
            return None
        else:
            st.avg_gain = (st.avg_gain * (self.period - 1) + gain) / self.period
            st.avg_loss = (st.avg_loss * (self.period - 1) + loss) / self.period

        if st.avg_loss == 0:
            rsi = 100.0
        else:
            rs = st.avg_gain / st.avg_loss
            rsi = 100.0 - 100.0 / (1.0 + rs)

        if rsi < self.oversold:
            return Signal(candle.symbol, Direction.LONG, candle.timestamp)
        if rsi > self.overbought:
            return Signal(candle.symbol, Direction.SHORT, candle.timestamp)
        return None
