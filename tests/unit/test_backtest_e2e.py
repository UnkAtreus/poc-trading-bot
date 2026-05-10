"""End-to-end backtest sanity test using forced signals."""

from __future__ import annotations

import pytest

from bot.backtest.runner import run_backtest
from bot.config import (
    BotConfig,
    EnvSettings,
    Fees,
    LoopConfig,
    MergeTimer,
    Mode,
    Offsets,
    RiskConfig,
    Settings,
    SignalConfig,
    Sizing,
    SymbolsConfig,
)
from bot.models import Candle, Direction, Signal
from bot.signals.base import SignalEngine


def _settings() -> Settings:
    return Settings(
        env=EnvSettings(mode=Mode.BACKTEST),
        bot=BotConfig(
            sizing=Sizing(margin_usd=20, leverage=10),
            offsets=Offsets(entry_offset_bps=5, tp_offset_bps=10),
            merge_timer=MergeTimer(seconds=1800, policy="first_fill"),
            fees=Fees(maker_bps=-1.0, taker_bps=5.5),
            risk=RiskConfig(
                max_notional_per_symbol_usd=600,
                max_notional_account_usd=2000,
                max_consecutive_losses=5,
                cooldown_minutes=60,
                daily_loss_limit_usd=100,
            ),
            signal=SignalConfig(engine="placeholder_rsi", params={"period": 14}),
            loop=LoopConfig(reconcile_every_seconds=30),
        ),
        symbols=SymbolsConfig(active=["BTCUSDT"], overrides={}),
    )


class _ForceFirstLong(SignalEngine):
    """Emit LONG once on the first candle, then nothing."""
    def __init__(self):
        self._fired = False

    def warmup_bars(self) -> int:
        return 0

    def on_candle(self, candle):
        if not self._fired:
            self._fired = True
            return Signal(candle.symbol, Direction.LONG, candle.timestamp)
        return None


@pytest.mark.asyncio
async def test_long_entry_fills_then_tp_fills():
    candles = [
        # candle 0: signal LONG fires; close=100 -> entry @ 99.95 placed for next candle
        Candle("BTCUSDT", 60.0, 100.0, 100.5, 99.5, 100.0, 1.0),
        # candle 1: low=99.0 -> entry fills at 99.95; TP placed at 99.95*1.001 = 100.04995
        Candle("BTCUSDT", 120.0, 100.0, 100.2, 99.0, 100.0, 1.0),
        # candle 2: high=100.2 < 100.04995? no, 100.2 > 100.05 -> TP fills
        Candle("BTCUSDT", 180.0, 100.0, 100.2, 99.8, 100.1, 1.0),
    ]
    result = await run_backtest(_settings(), {"BTCUSDT": candles}, _ForceFirstLong())
    # Expect 1 entry fill + 1 TP fill recorded as one trade.
    assert len(result.trades) == 1
    t = result.trades[0]
    assert t.direction is Direction.LONG
    assert t.realized_pnl > 0
    assert result.final_state["BTCUSDT"].position_size == 0.0


@pytest.mark.asyncio
async def test_unfilled_entry_is_cancelled_on_next_candle():
    candles = [
        # candle 0: signal LONG fires; close=100 -> entry @ 99.95 for next candle
        Candle("BTCUSDT", 60.0, 100.0, 100.5, 99.97, 100.0, 1.0),
        # candle 1: low=99.96 -> entry NOT filled (99.96 > 99.95), no signal -> entry cancelled, IDLE
        Candle("BTCUSDT", 120.0, 100.0, 100.5, 99.96, 100.3, 1.0),
    ]
    result = await run_backtest(_settings(), {"BTCUSDT": candles}, _ForceFirstLong())
    assert result.trades == []
    assert result.final_state["BTCUSDT"].state.value == "IDLE"
