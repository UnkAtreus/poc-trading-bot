from __future__ import annotations

from bot.models import Candle, Direction
from bot.signals.base import build
from bot.signals.bollinger import BollingerBands
from bot.signals.ema_cross import EMACrossover
from bot.signals.grid import GridSignal
from bot.signals.zscore import ZScore


def cdl(close: float, ts: float = 0.0, sym: str = "BTCUSDT") -> Candle:
    return Candle(symbol=sym, timestamp=ts, open=close, high=close, low=close, close=close, volume=1.0)


# ---------- Bollinger Bands ----------

def test_bollinger_no_signal_in_warmup():
    eng = BollingerBands(period=20, num_std=2.0)
    for i in range(20):
        assert eng.on_candle(cdl(100.0, ts=float(i))) is None


def test_bollinger_emits_long_below_lower_band():
    eng = BollingerBands(period=20, num_std=2.0)
    for i, p in enumerate([100.0] * 19 + [101.0]):  # establish baseline
        eng.on_candle(cdl(p, ts=float(i)))
    # Now drop way below the band
    sig = eng.on_candle(cdl(50.0, ts=20.0))
    assert sig is not None
    assert sig.direction is Direction.LONG


def test_bollinger_emits_short_above_upper_band():
    eng = BollingerBands(period=20, num_std=2.0)
    for i, p in enumerate([100.0] * 19 + [99.0]):
        eng.on_candle(cdl(p, ts=float(i)))
    sig = eng.on_candle(cdl(150.0, ts=20.0))
    assert sig is not None
    assert sig.direction is Direction.SHORT


def test_bollinger_no_signal_in_band():
    eng = BollingerBands(period=20, num_std=2.0)
    sig = None
    for i in range(40):
        sig = eng.on_candle(cdl(100.0 + (i % 2) * 0.1, ts=float(i)))  # tiny noise
    assert sig is None


# ---------- Z-score ----------

def test_zscore_long_when_far_below_mean():
    eng = ZScore(period=30, threshold=2.0)
    for i in range(30):
        eng.on_candle(cdl(100.0 + (i % 2), ts=float(i)))  # mean ~100.5, small std
    sig = eng.on_candle(cdl(50.0, ts=30.0))
    assert sig is not None
    assert sig.direction is Direction.LONG


def test_zscore_short_when_far_above_mean():
    eng = ZScore(period=30, threshold=2.0)
    for i in range(30):
        eng.on_candle(cdl(100.0 + (i % 2), ts=float(i)))
    sig = eng.on_candle(cdl(150.0, ts=30.0))
    assert sig is not None
    assert sig.direction is Direction.SHORT


def test_zscore_no_signal_under_threshold():
    eng = ZScore(period=30, threshold=2.0)
    sig = None
    for i in range(60):
        sig = eng.on_candle(cdl(100.0 + (i % 3) * 0.5, ts=float(i)))
    assert sig is None


# ---------- Grid ----------

def test_grid_no_signal_inside_neutral_zone():
    eng = GridSignal(anchor_period=20, entry_bps=50.0, step_bps=30.0)
    sig = None
    for i in range(40):
        sig = eng.on_candle(cdl(100.0, ts=float(i)))
    assert sig is None


def test_grid_long_below_entry_threshold():
    eng = GridSignal(anchor_period=20, entry_bps=50.0, step_bps=30.0)
    # Anchor builds at 100
    for i in range(20):
        eng.on_candle(cdl(100.0, ts=float(i)))
    # 100 bps below anchor (1% drop)
    sig = eng.on_candle(cdl(99.0, ts=20.0))
    assert sig is not None
    assert sig.direction is Direction.LONG


def test_grid_short_above_entry_threshold():
    eng = GridSignal(anchor_period=20, entry_bps=50.0, step_bps=30.0)
    for i in range(20):
        eng.on_candle(cdl(100.0, ts=float(i)))
    sig = eng.on_candle(cdl(101.0, ts=20.0))
    assert sig is not None
    assert sig.direction is Direction.SHORT


def test_grid_re_fires_on_step():
    eng = GridSignal(anchor_period=20, entry_bps=50.0, step_bps=30.0)
    for i in range(20):
        eng.on_candle(cdl(100.0, ts=float(i)))
    s1 = eng.on_candle(cdl(99.5, ts=20.0))  # entry
    s2 = eng.on_candle(cdl(99.4, ts=21.0))  # too close to last fire
    s3 = eng.on_candle(cdl(99.0, ts=22.0))  # ~50bps below last fire — re-fires
    assert s1 is not None and s1.direction is Direction.LONG
    assert s2 is None
    assert s3 is not None and s3.direction is Direction.LONG


def test_grid_resets_on_neutral_return():
    eng = GridSignal(anchor_period=20, entry_bps=50.0, step_bps=30.0)
    for i in range(20):
        eng.on_candle(cdl(100.0, ts=float(i)))
    eng.on_candle(cdl(99.0, ts=20.0))      # LONG fires
    eng.on_candle(cdl(100.0, ts=21.0))     # neutral — resets
    s = eng.on_candle(cdl(99.0, ts=22.0))   # LONG should fire again, not be skipped
    assert s is not None
    assert s.direction is Direction.LONG


# ---------- EMA crossover ----------

def test_ema_crossover_emits_long_on_uptrend_then_recovery():
    eng = EMACrossover(fast=3, slow=8)
    # downtrend then uptrend → cross above
    prices = [100.0 - i for i in range(10)] + [90.0 + i for i in range(10)]
    sig = None
    for i, p in enumerate(prices):
        s = eng.on_candle(cdl(p, ts=float(i)))
        if s is not None:
            sig = s
    assert sig is not None
    assert sig.direction is Direction.LONG


def test_ema_crossover_emits_short_on_downtrend_after_uptrend():
    eng = EMACrossover(fast=3, slow=8)
    prices = [100.0 + i for i in range(10)] + [110.0 - i for i in range(10)]
    sig = None
    for i, p in enumerate(prices):
        s = eng.on_candle(cdl(p, ts=float(i)))
        if s is not None:
            sig = s
    assert sig is not None
    assert sig.direction is Direction.SHORT


# ---------- Registry ----------

def test_registry_builds_all_new_engines():
    assert isinstance(build("bollinger_bands", {"period": 20, "num_std": 2.0}), BollingerBands)
    assert isinstance(build("zscore", {"period": 30, "threshold": 2.0}), ZScore)
    assert isinstance(build("grid", {"anchor_period": 50, "entry_bps": 50.0, "step_bps": 30.0}), GridSignal)
    assert isinstance(build("ema_crossover", {"fast": 9, "slow": 21}), EMACrossover)
