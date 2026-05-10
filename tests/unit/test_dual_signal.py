from bot.models import Candle, Direction
from bot.signals.dual_signal import DualSignal


def candle(i: int) -> Candle:
    return Candle("BTCUSDT", float(i), 100.0, 100.0, 100.0, 100.0, 1.0)


def test_dual_signal_agree_requires_same_direction():
    sig = DualSignal(
        left="random",
        right="random",
        mode="agree",
        left_p_long=1.0,
        left_p_short=0.0,
        right_p_long=1.0,
        right_p_short=0.0,
    )

    out = sig.on_candle(candle(1))
    assert out is not None
    assert out.direction is Direction.LONG


def test_dual_signal_agree_suppresses_conflict():
    sig = DualSignal(
        left="random",
        right="random",
        mode="agree",
        left_p_long=1.0,
        left_p_short=0.0,
        right_p_long=0.0,
        right_p_short=1.0,
    )

    assert sig.on_candle(candle(1)) is None


def test_dual_signal_either_allows_single_side():
    sig = DualSignal(
        left="random",
        right="random",
        mode="either",
        left_p_long=0.0,
        left_p_short=0.0,
        right_p_long=1.0,
        right_p_short=0.0,
    )

    out = sig.on_candle(candle(1))
    assert out is not None
    assert out.direction is Direction.LONG
