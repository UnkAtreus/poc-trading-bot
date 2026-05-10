from __future__ import annotations

from datetime import datetime, timezone

import pytest

from bot.backtest.runner import BacktestResult, MonthlyEquityStats, TradeRecord
from bot.backtest.stability import StabilityGates, analyze_stability
from bot.models import Direction


def _ts(day: str) -> float:
    return datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()


def _trade(day: str, pnl: float) -> TradeRecord:
    ts = _ts(day)
    return TradeRecord(
        symbol="BTCUSDT",
        direction=Direction.LONG,
        entry_ts=ts - 60.0,
        exit_ts=ts,
        qty=1.0,
        avg_entry=100.0,
        exit_price=100.0 + pnl,
        realized_pnl=pnl,
        fees=0.0,
    )


def test_stability_passes_when_positive_months_and_drawdown_are_inside_gates():
    result = BacktestResult(
        initial_equity=10_000.0,
        trades=[
            _trade("2025-01-15", 100.0),
            _trade("2025-02-15", 80.0),
            _trade("2025-03-15", -10.0),
            _trade("2025-04-15", 90.0),
        ],
        monthly_equity={
            "2025-01": MonthlyEquityStats("2025-01", 10_100.0, 10_100.0, 200.0),
            "2025-02": MonthlyEquityStats("2025-02", 10_180.0, 10_180.0, 300.0),
            "2025-03": MonthlyEquityStats("2025-03", 10_170.0, 10_170.0, 500.0),
            "2025-04": MonthlyEquityStats("2025-04", 10_260.0, 10_260.0, 100.0),
        },
    )

    stats = analyze_stability(
        result,
        gates=StabilityGates(
            target_monthly_roi_pct=0.5,
            min_positive_month_pct=70.0,
            max_non_positive_stretch=1,
            max_worst_monthly_dd_pct=10.0,
        ),
    )

    assert stats.passes
    assert stats.months == 4
    assert stats.positive_month_pct == pytest.approx(75.0)
    assert stats.target_month_pct == pytest.approx(75.0)
    assert stats.longest_non_positive_stretch == 1
    assert stats.worst_monthly_dd_pct == pytest.approx(5.0)


def test_stability_fails_on_long_non_positive_stretch():
    result = BacktestResult(
        initial_equity=10_000.0,
        trades=[
            _trade("2025-01-15", 100.0),
            _trade("2025-02-15", -1.0),
            _trade("2025-03-15", 0.0),
            _trade("2025-04-15", -1.0),
            _trade("2025-05-15", 100.0),
        ],
    )

    stats = analyze_stability(
        result,
        gates=StabilityGates(max_non_positive_stretch=2),
    )

    assert not stats.passes
    assert stats.longest_non_positive_stretch == 3


def test_stability_fails_when_target_month_percentage_is_too_low():
    result = BacktestResult(
        initial_equity=10_000.0,
        trades=[
            _trade("2025-01-15", 10.0),
            _trade("2025-02-15", 10.0),
            _trade("2025-03-15", 10.0),
            _trade("2025-04-15", 10.0),
        ],
    )

    stats = analyze_stability(
        result,
        gates=StabilityGates(
            target_monthly_roi_pct=0.5,
            min_positive_month_pct=100.0,
            min_target_month_pct=50.0,
        ),
    )

    assert not stats.passes
    assert stats.positive_month_pct == pytest.approx(100.0)
    assert stats.target_month_pct == pytest.approx(0.0)
