from __future__ import annotations

from bot.models import Candle, Direction
from bot.signals.base import build
from bot.signals.regime_gate import RegimeGate


def cdl(close: float, ts: float = 0.0, sym: str = "BTCUSDT") -> Candle:
    return Candle(symbol=sym, timestamp=ts, open=close, high=close, low=close, close=close, volume=1.0)


def test_regime_gate_pauses_inner_signal_when_ema_spread_is_unsafe():
    eng = RegimeGate(
        inner="grid",
        scope="symbol",
        ema_fast=2,
        ema_slow=5,
        max_ema_spread_bps=1.0,
        use_adx=False,
        unsafe_action="pause",
        inner_anchor_period=5,
        inner_entry_bps=10.0,
        inner_step_bps=5.0,
    )
    for i in range(6):
        assert eng.on_candle(cdl(100.0, ts=float(i))) is None

    # The grid would fire SHORT after this jump, but the EMA-spread gate blocks it.
    assert eng.on_candle(cdl(105.0, ts=6.0)) is None


def test_regime_gate_reduces_inner_signal_size_when_configured():
    eng = RegimeGate(
        inner="grid",
        scope="symbol",
        ema_fast=2,
        ema_slow=5,
        max_ema_spread_bps=1.0,
        use_adx=False,
        unsafe_action="reduce",
        unsafe_size_scale=0.25,
        inner_anchor_period=5,
        inner_entry_bps=10.0,
        inner_step_bps=5.0,
    )
    for i in range(6):
        eng.on_candle(cdl(100.0, ts=float(i)))

    sig = eng.on_candle(cdl(105.0, ts=6.0))
    assert sig is not None
    assert sig.direction is Direction.SHORT
    assert sig.size_scale == 0.25


def test_regime_gate_can_block_new_positions_only():
    eng = RegimeGate(
        inner="grid",
        scope="symbol",
        ema_fast=2,
        ema_slow=5,
        max_ema_spread_bps=1.0,
        use_adx=False,
        unsafe_action="block_new",
        inner_anchor_period=5,
        inner_entry_bps=10.0,
        inner_step_bps=5.0,
    )
    for i in range(6):
        eng.on_candle(cdl(100.0, ts=float(i)))

    sig = eng.on_candle(cdl(105.0, ts=6.0))
    assert sig is not None
    assert sig.direction is Direction.SHORT
    assert sig.allow_new_position is False
    assert sig.allow_layering is True


def test_regime_gate_via_registry():
    eng = build(
        "regime_gate",
        {
            "inner": "grid",
            "scope": "symbol",
            "inner_anchor_period": 5,
            "inner_entry_bps": 10.0,
            "inner_step_bps": 5.0,
        },
    )
    assert isinstance(eng, RegimeGate)
