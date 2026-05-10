from __future__ import annotations

from bot.models import Candle, Direction
from bot.signals.base import build
from bot.signals.placeholder_rsi import PlaceholderRSI
from bot.signals.random_signal import RandomSignal


def _candle(close: float, ts: float = 0.0, symbol: str = "BTCUSDT") -> Candle:
    return Candle(symbol=symbol, timestamp=ts, open=close, high=close, low=close, close=close, volume=1.0)


def test_rsi_emits_short_on_uptrend():
    eng = PlaceholderRSI(period=14, oversold=30, overbought=70)
    # 30 strictly-up candles: RSI should saturate to 100 -> SHORT.
    sig = None
    for i, c in enumerate(range(100, 130)):
        sig = eng.on_candle(_candle(float(c), ts=float(i)))
    assert sig is not None
    assert sig.direction is Direction.SHORT


def test_rsi_emits_long_on_downtrend():
    eng = PlaceholderRSI(period=14, oversold=30, overbought=70)
    sig = None
    for i, c in enumerate(range(130, 100, -1)):
        sig = eng.on_candle(_candle(float(c), ts=float(i)))
    assert sig is not None
    assert sig.direction is Direction.LONG


def test_rsi_no_signal_in_warmup():
    eng = PlaceholderRSI(period=14)
    for i in range(eng.warmup_bars()):
        assert eng.on_candle(_candle(100.0 + i, ts=float(i))) is None


def test_random_signal_reproducible():
    a = RandomSignal(p_long=0.5, p_short=0.5, seed=123)
    b = RandomSignal(p_long=0.5, p_short=0.5, seed=123)
    seq_a = [a.on_candle(_candle(100.0, ts=float(i))) for i in range(20)]
    seq_b = [b.on_candle(_candle(100.0, ts=float(i))) for i in range(20)]
    assert [s.direction if s else None for s in seq_a] == [s.direction if s else None for s in seq_b]


def test_registry_build():
    eng = build("placeholder_rsi", {"period": 14, "oversold": 30, "overbought": 70})
    assert isinstance(eng, PlaceholderRSI)
    eng2 = build("random", {"p_long": 0.1, "p_short": 0.1, "seed": 1})
    assert isinstance(eng2, RandomSignal)
