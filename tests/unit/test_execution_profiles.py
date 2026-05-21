from __future__ import annotations

from argparse import Namespace

from bot.backtest.execution import BacktestExecutionConfig, EXECUTION_PROFILE_LATENCIES
from bot.main import _execution_config_from_args


def test_conservative_profile_matches_original_realistic_defaults():
    cfg = BacktestExecutionConfig.from_profile("conservative")

    assert cfg.latency_seconds == 1.0
    assert cfg.cancel_delay_seconds == 3.0
    assert cfg.slippage_bps == 2.0
    assert cfg.pass_through_bps == 1.0
    assert cfg.full_fill_bps == 5.0
    assert cfg.min_partial_fill_pct == 25.0
    assert EXECUTION_PROFILE_LATENCIES["conservative"] == "1,3,5"


def test_mainnet_like_profile_uses_measured_latency_defaults():
    cfg = BacktestExecutionConfig.from_profile("mainnet-like")

    assert cfg.latency_seconds == 0.30
    assert cfg.cancel_delay_seconds == 0.50
    assert cfg.slippage_bps == 1.0
    assert cfg.pass_through_bps == 0.2
    assert cfg.full_fill_bps == 1.0
    assert cfg.min_partial_fill_pct == 50.0
    assert EXECUTION_PROFILE_LATENCIES["mainnet-like"] == "0.15,0.3,0.5"


def test_execution_profile_manual_overrides_win():
    args = Namespace(
        execution_model="realistic",
        execution_profile="mainnet-like",
        latency_seconds=0.2,
        cancel_delay_seconds=None,
        slippage_bps=0.0,
        pass_through_bps=None,
        full_fill_bps=None,
        min_partial_fill_pct=None,
    )

    cfg = _execution_config_from_args(args)

    assert cfg.latency_seconds == 0.2
    assert cfg.cancel_delay_seconds == 0.50
    assert cfg.slippage_bps == 0.0
    assert cfg.pass_through_bps == 0.2
