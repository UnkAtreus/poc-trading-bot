from bot.models import Candle, Direction
from bot.signals.crash_guard import CrashGuard


def c(symbol: str, i: int, close: float) -> Candle:
    return Candle(
        symbol=symbol,
        timestamp=float(i),
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1.0,
    )


def test_crash_guard_suppresses_longs_when_btc_drops():
    sig = CrashGuard(
        inner="random",
        inner_p_long=1.0,
        inner_p_short=0.0,
        inner_seed=1,
        btc_ema_period=2,
        btc_return_bars=2,
        btc_drop_bps=500,
    )

    sig.on_candle(c("BTCUSDT", 1, 100.0))
    sig.on_candle(c("BTCUSDT", 2, 99.0))
    sig.on_candle(c("BTCUSDT", 3, 90.0))

    assert sig.on_candle(c("ETHUSDT", 4, 100.0)) is None


def test_crash_guard_allows_shorts_when_configured():
    sig = CrashGuard(
        inner="random",
        inner_p_long=0.0,
        inner_p_short=1.0,
        inner_seed=1,
        btc_ema_period=2,
        btc_return_bars=2,
        btc_drop_bps=500,
    )

    sig.on_candle(c("BTCUSDT", 1, 100.0))
    sig.on_candle(c("BTCUSDT", 2, 99.0))
    sig.on_candle(c("BTCUSDT", 3, 90.0))

    out = sig.on_candle(c("ETHUSDT", 4, 100.0))
    assert out is not None
    assert out.direction is Direction.SHORT
