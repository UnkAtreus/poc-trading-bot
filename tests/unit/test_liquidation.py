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
from bot.risk.liquidation import AccountRiskInput, MarginMode, PositionRisk, assess_account_risk, liquidation_price
from bot.signals.base import SignalEngine


def _settings() -> Settings:
    return Settings(
        env=EnvSettings(mode=Mode.BACKTEST),
        bot=BotConfig(
            sizing=Sizing(margin_usd=1000, leverage=10),
            offsets=Offsets(entry_offset_bps=0, tp_offset_bps=100),
            merge_timer=MergeTimer(seconds=1800, policy="first_fill"),
            fees=Fees(maker_bps=0.0, taker_bps=5.5),
            risk=RiskConfig(
                max_notional_per_symbol_usd=20_000,
                max_notional_account_usd=20_000,
                max_consecutive_losses=5,
                cooldown_minutes=60,
                daily_loss_limit_usd=1000,
            ),
            signal=SignalConfig(engine="placeholder_rsi", params={}),
            loop=LoopConfig(reconcile_every_seconds=30),
        ),
        symbols=SymbolsConfig(active=["BTCUSDT"], overrides={}),
    )


class _ForceFirstLong(SignalEngine):
    def __init__(self):
        self._fired = False

    def warmup_bars(self) -> int:
        return 0

    def on_candle(self, candle):
        if self._fired:
            return None
        self._fired = True
        return Signal(candle.symbol, Direction.LONG, candle.timestamp)


def test_isolated_long_liquidation_price_moves_above_bankruptcy_price():
    liq = liquidation_price(
        direction=Direction.LONG,
        avg_entry=100.0,
        leverage=10,
        maintenance_margin_rate=0.005,
    )
    assert liq == pytest.approx(90.4522613)


def test_cross_account_flags_near_liquidation_on_negative_available_balance():
    snapshot = assess_account_risk(
        AccountRiskInput(
            initial_equity=1000.0,
            realized_net=0.0,
            positions=(PositionRisk("BTCUSDT", Direction.LONG, qty=10, avg_entry=100, mark=100),),
            pending_entry_notional=20_000.0,
            leverage=10,
            maintenance_margin_rate=0.005,
            margin_mode=MarginMode.CROSS,
        ),
        near_liq_buffer_pct=1.0,
    )
    assert snapshot.near_liquidation
    assert snapshot.available_balance < 0


@pytest.mark.asyncio
async def test_backtest_flags_liquidation_even_without_realized_loss():
    candles = [
        Candle("BTCUSDT", 60.0, 100.0, 100.0, 100.0, 100.0, 1.0),
        Candle("BTCUSDT", 120.0, 100.0, 100.0, 50.0, 80.0, 1.0),
    ]
    result = await run_backtest(
        _settings(),
        {"BTCUSDT": candles},
        _ForceFirstLong(),
        initial_equity=1000.0,
    )
    assert result.liquidated
    assert result.liquidation_events
    assert result.worst_unrealized_loss < 0
