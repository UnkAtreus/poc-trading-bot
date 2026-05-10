"""Monthly stability scoring for backtest results."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from bot.backtest.monthly import by_month
from bot.backtest.runner import BacktestResult


@dataclass(frozen=True)
class StabilityGates:
    target_monthly_roi_pct: float = 0.5
    min_positive_month_pct: float = 70.0
    min_target_month_pct: float = 50.0
    max_non_positive_stretch: int = 2
    max_worst_monthly_dd_pct: float = 10.0


@dataclass(frozen=True)
class MonthlyStability:
    months: int
    positive_months: int
    target_months: int
    positive_month_pct: float
    target_month_pct: float
    longest_non_positive_stretch: int
    avg_monthly_roi_pct: float
    median_monthly_roi_pct: float
    worst_monthly_roi_pct: float
    worst_monthly_loss_usd: float
    worst_monthly_dd_pct: float
    score: float
    passes: bool


def analyze_stability(
    result: BacktestResult,
    *,
    gates: StabilityGates,
    initial_equity: float | None = None,
) -> MonthlyStability:
    equity = initial_equity if initial_equity is not None else result.initial_equity
    rows = by_month(result)
    if equity <= 0 or not rows:
        return MonthlyStability(
            months=0,
            positive_months=0,
            target_months=0,
            positive_month_pct=0.0,
            target_month_pct=0.0,
            longest_non_positive_stretch=0,
            avg_monthly_roi_pct=0.0,
            median_monthly_roi_pct=0.0,
            worst_monthly_roi_pct=0.0,
            worst_monthly_loss_usd=0.0,
            worst_monthly_dd_pct=0.0,
            score=-1_000_000.0,
            passes=False,
        )

    roi_values = [r.net_pnl / equity * 100.0 for r in rows]
    positive_months = sum(1 for roi in roi_values if roi > 0)
    target_months = sum(1 for roi in roi_values if roi >= gates.target_monthly_roi_pct)
    worst_monthly_dd_pct = max(r.max_drawdown_value / equity * 100.0 for r in rows)
    longest_stretch = _longest_non_positive_stretch(roi_values)
    positive_month_pct = positive_months / len(rows) * 100.0
    target_month_pct = target_months / len(rows) * 100.0
    worst_roi = min(roi_values)
    worst_loss = min(0.0, min(r.net_pnl for r in rows))

    passes = (
        positive_month_pct >= gates.min_positive_month_pct
        and target_month_pct >= gates.min_target_month_pct
        and longest_stretch <= gates.max_non_positive_stretch
        and worst_monthly_dd_pct <= gates.max_worst_monthly_dd_pct
    )
    score = _score(
        avg_roi=sum(roi_values) / len(roi_values),
        median_roi=median(roi_values),
        target_month_pct=target_month_pct,
        positive_month_pct=positive_month_pct,
        worst_roi=worst_roi,
        worst_monthly_dd_pct=worst_monthly_dd_pct,
        longest_stretch=longest_stretch,
    )
    return MonthlyStability(
        months=len(rows),
        positive_months=positive_months,
        target_months=target_months,
        positive_month_pct=positive_month_pct,
        target_month_pct=target_month_pct,
        longest_non_positive_stretch=longest_stretch,
        avg_monthly_roi_pct=sum(roi_values) / len(roi_values),
        median_monthly_roi_pct=median(roi_values),
        worst_monthly_roi_pct=worst_roi,
        worst_monthly_loss_usd=worst_loss,
        worst_monthly_dd_pct=worst_monthly_dd_pct,
        score=score,
        passes=passes,
    )


def _longest_non_positive_stretch(roi_values: list[float]) -> int:
    longest = 0
    current = 0
    for roi in roi_values:
        if roi <= 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _score(
    *,
    avg_roi: float,
    median_roi: float,
    target_month_pct: float,
    positive_month_pct: float,
    worst_roi: float,
    worst_monthly_dd_pct: float,
    longest_stretch: int,
) -> float:
    return (
        avg_roi * 3.0
        + median_roi * 4.0
        + target_month_pct * 0.08
        + positive_month_pct * 0.05
        + worst_roi * 2.0
        - worst_monthly_dd_pct * 0.5
        - longest_stretch * 2.0
    )
