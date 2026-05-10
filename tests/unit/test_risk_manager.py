from __future__ import annotations

import pytest

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
from bot.risk.manager import RiskManager


def make_settings(**env_overrides) -> Settings:
    env_overrides.setdefault("mode", Mode.TESTNET)
    env = EnvSettings(**env_overrides)
    return Settings(
        env=env,
        bot=BotConfig(
            sizing=Sizing(margin_usd=20, leverage=10),
            offsets=Offsets(entry_offset_bps=5, tp_offset_bps=10),
            merge_timer=MergeTimer(seconds=1800, policy="first_fill"),
            fees=Fees(maker_bps=-1.0, taker_bps=5.5),
            risk=RiskConfig(
                max_notional_per_symbol_usd=600,
                max_notional_account_usd=2000,
                max_consecutive_losses=3,
                cooldown_minutes=60,
                daily_loss_limit_usd=100,
            ),
            signal=SignalConfig(engine="placeholder_rsi", params={}),
            loop=LoopConfig(reconcile_every_seconds=30),
        ),
        symbols=SymbolsConfig(
            active=["BTCUSDT", "HYPEUSDT"],
            overrides={"HYPEUSDT": {"max_notional_per_symbol_usd": 300}},
        ),
    )


def test_per_symbol_cap_blocks_layered_entries(tmp_path):
    rm = RiskManager(settings=make_settings(), state_dir=tmp_path)
    ok, _ = rm.check_can_place_entry("BTCUSDT", 200.0)
    assert ok
    rm.on_entry_placed("BTCUSDT", 200.0)
    rm.on_entry_placed("BTCUSDT", 200.0)
    rm.on_entry_placed("BTCUSDT", 200.0)
    ok, reason = rm.check_can_place_entry("BTCUSDT", 200.0)
    assert not ok
    assert "per_symbol_cap" in reason


def test_per_symbol_override_used_for_hype(tmp_path):
    rm = RiskManager(settings=make_settings(), state_dir=tmp_path)
    rm.on_entry_placed("HYPEUSDT", 200.0)
    ok, reason = rm.check_can_place_entry("HYPEUSDT", 200.0)
    assert not ok  # 200+200=400 > 300


def test_account_cap_blocks_when_total_exceeds(tmp_path):
    rm = RiskManager(settings=make_settings(), state_dir=tmp_path)
    # Pretend lots of symbols have used capacity.
    for sym in ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]:
        rm.on_entry_placed(sym, 200.0)
    ok, reason = rm.check_can_place_entry("BTCUSDT", 200.0)
    assert not ok
    assert reason == "account_cap"


def test_kill_switch_file_blocks(tmp_path):
    rm = RiskManager(settings=make_settings(), state_dir=tmp_path)
    (tmp_path / "KILL").touch()
    ok, reason = rm.check_can_place_entry("BTCUSDT", 200.0)
    assert not ok
    assert reason == "kill_switch"


def test_kill_switch_env_blocks(tmp_path):
    rm = RiskManager(settings=make_settings(bot_kill="1"), state_dir=tmp_path)
    ok, reason = rm.check_can_place_entry("BTCUSDT", 200.0)
    assert not ok
    assert reason == "kill_switch"


def test_consecutive_losses_trigger_cooldown(tmp_path):
    rm = RiskManager(settings=make_settings(), state_dir=tmp_path)
    for _ in range(3):
        rm.on_trade_closed("BTCUSDT", pnl=-1.0, notional_closed=0.0)
    ok, reason = rm.check_can_place_entry("BTCUSDT", 200.0)
    assert not ok
    assert "cooldown" in reason


def test_winning_trade_resets_streak(tmp_path):
    rm = RiskManager(settings=make_settings(), state_dir=tmp_path)
    rm.on_trade_closed("BTCUSDT", pnl=-1.0, notional_closed=0.0)
    rm.on_trade_closed("BTCUSDT", pnl=-1.0, notional_closed=0.0)
    rm.on_trade_closed("BTCUSDT", pnl=+1.0, notional_closed=0.0)
    rm.on_trade_closed("BTCUSDT", pnl=-1.0, notional_closed=0.0)
    ok, _ = rm.check_can_place_entry("BTCUSDT", 200.0)
    assert ok


def test_daily_loss_limit_blocks(tmp_path):
    rm = RiskManager(settings=make_settings(), state_dir=tmp_path)
    rm.on_trade_closed("BTCUSDT", pnl=-101.0, notional_closed=0.0)
    ok, reason = rm.check_can_place_entry("BTCUSDT", 200.0)
    assert not ok
    assert reason == "daily_loss_limit"


def test_mainnet_without_confirm_refuses_to_start(tmp_path):
    # Construct via direct kwargs, bypassing the env validator (we want to test the runtime guard too).
    with pytest.raises(ValueError):
        EnvSettings(mode=Mode.MAINNET, mainnet_confirm="")


def test_mainnet_with_confirm_starts_ok(tmp_path):
    rm = RiskManager(
        settings=make_settings(mode=Mode.MAINNET, mainnet_confirm="YES_I_MEAN_IT"),
        state_dir=tmp_path,
    )
    rm.assert_can_start()
