from __future__ import annotations

from bot.signals.labels import signal_full_label, signal_short_label


def test_signal_short_label_compacts_trend_grid():
    params = {
        "inner": "grid",
        "inner_anchor_period": 200,
        "inner_entry_bps": 30,
        "inner_step_bps": 15,
        "max_trend_bps": 30,
    }

    assert signal_short_label("trend_filter", params) == "trend_grid_a200_e30_s15_t30"
    assert signal_full_label("trend_filter", params) == (
        "trend_filter:inner=grid:inner_anchor_period=200:"
        "inner_entry_bps=30:inner_step_bps=15:max_trend_bps=30"
    )


def test_signal_short_label_compacts_regime_gate_trend_grid():
    params = {
        "inner": "trend_filter",
        "inner_inner": "grid",
        "inner_inner_anchor_period": 200,
        "inner_inner_entry_bps": 50,
        "inner_inner_step_bps": 25,
        "inner_max_trend_bps": 20,
        "max_ema_spread_bps": 15,
        "max_adx": 20,
        "unsafe_action": "reduce",
        "unsafe_size_scale": 0.5,
    }
    assert (
        signal_short_label("regime_gate", params)
        == "rg_trend_grid_a200_e50_s25_t20_ema15_adx20_reduce0_5"
    )


def test_signal_short_label_compacts_common_engines():
    assert signal_short_label("grid", {"inner_entry_bps": 40}) == "grid_e40"
    assert signal_short_label("bollinger_bands", {"period": 20, "num_std": 2.0}) == "bb_p20_std2"
    assert signal_short_label("zscore", {"period": 50, "threshold": 2.0}) == "z_p50_th2"
