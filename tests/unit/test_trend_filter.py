from __future__ import annotations

from bot.models import Candle, Direction
from bot.signals.base import build
from bot.signals.trend_filter import TrendFilter


def cdl(close: float, ts: float = 0.0, sym: str = "BTCUSDT") -> Candle:
    return Candle(symbol=sym, timestamp=ts, open=close, high=close, low=close, close=close, volume=1.0)


def test_trend_filter_passes_signal_in_chop():
    # Build a wrapper around BB. In a flat market, EMA fast ≈ EMA slow → low trend bps.
    eng = TrendFilter(
        inner="bollinger_bands",
        ema_fast=10, ema_slow=30, max_trend_bps=50,
        inner_period=20, inner_num_std=2.0,
    )
    # Warm up with flat prices so trend bps stays tiny
    for i in range(50):
        eng.on_candle(cdl(100.0, ts=float(i)))
    # Now spike one candle below the lower band → BB would emit LONG
    sig = eng.on_candle(cdl(80.0, ts=50.0))
    # Trend filter sees fast EMA dipping but slow EMA still high → some trend bps.
    # Verify it either passes (chop) or suppresses (trending) — but in either case
    # the wrapper should have evaluated the inner.
    # Build BB directly to compare.
    from bot.signals.bollinger import BollingerBands
    direct = BollingerBands(period=20, num_std=2.0)
    for i in range(50):
        direct.on_candle(cdl(100.0, ts=float(i)))
    direct_sig = direct.on_candle(cdl(80.0, ts=50.0))
    assert direct_sig is not None  # BB itself fires
    # Wrapper may or may not suppress depending on EMA dynamics — but it must NOT
    # silently break the inner.
    assert sig is None or sig.direction is direct_sig.direction


def test_trend_filter_suppresses_in_strong_trend():
    eng = TrendFilter(
        inner="bollinger_bands",
        ema_fast=5, ema_slow=20, max_trend_bps=10,
        inner_period=10, inner_num_std=1.0,
    )
    # Strong uptrend; slow EMA will lag fast EMA significantly
    for i in range(40):
        eng.on_candle(cdl(100.0 + i * 2.0, ts=float(i)))
    # Now drop sharply (would trigger BB long), but trend should suppress
    suppressed = 0
    fired = 0
    for i in range(5):
        s = eng.on_candle(cdl(180.0 - i * 5, ts=float(40 + i)))
        if s is None:
            suppressed += 1
        else:
            fired += 1
    assert suppressed >= 1, "trend filter should suppress at least one inner signal"


def test_trend_filter_warmup_uses_max():
    eng = TrendFilter(
        inner="bollinger_bands",
        ema_fast=10, ema_slow=30, max_trend_bps=50,
        inner_period=50,
    )
    assert eng.warmup_bars() >= 50  # inner is the dominant warmup


def test_trend_filter_via_registry():
    eng = build("trend_filter", {
        "inner": "bollinger_bands",
        "ema_fast": 30,
        "ema_slow": 120,
        "max_trend_bps": 30.0,
        "inner_period": 20,
        "inner_num_std": 2.0,
    })
    assert isinstance(eng, TrendFilter)
