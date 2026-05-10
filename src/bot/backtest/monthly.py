"""Month-by-month backtest reporting.

Aggregates an existing BacktestResult into per-month rows. A "month" is the
UTC calendar month of the trade's exit timestamp (when the realized PnL
booked).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

from bot.backtest.runner import BacktestResult


@dataclass
class MonthlyRow:
    period: str  # "YYYY-MM"
    trades: int
    wins: int
    losses: int
    gross_pnl: float
    fees: float
    max_drawdown_value: float = 0.0

    @property
    def net_pnl(self) -> float:
        return self.gross_pnl - self.fees

    @property
    def win_rate(self) -> float:
        n = self.wins + self.losses
        return self.wins / n if n else 0.0


def by_month(result: BacktestResult) -> list[MonthlyRow]:
    """Group trades by exit month (UTC) and bucket fills by execution month."""
    trades_by_month: dict[str, list] = defaultdict(list)
    for t in result.trades:
        ym = datetime.fromtimestamp(t.exit_ts, tz=timezone.utc).strftime("%Y-%m")
        trades_by_month[ym].append(t)

    fees_by_month: dict[str, float] = defaultdict(float)
    for f in result.fills:
        ym = datetime.fromtimestamp(f.timestamp, tz=timezone.utc).strftime("%Y-%m")
        fees_by_month[ym] += f.fee

    months = sorted(
        set(trades_by_month.keys())
        | set(fees_by_month.keys())
        | set(result.monthly_equity.keys())
    )
    rows: list[MonthlyRow] = []
    for m in months:
        ts = trades_by_month.get(m, [])
        gross = sum(t.realized_pnl for t in ts)
        wins = sum(1 for t in ts if t.realized_pnl > 0)
        losses = sum(1 for t in ts if t.realized_pnl < 0)
        rows.append(MonthlyRow(
            period=m, trades=len(ts), wins=wins, losses=losses,
            gross_pnl=gross, fees=fees_by_month.get(m, 0.0),
            max_drawdown_value=result.monthly_max_drawdown(m),
        ))
    return rows


def render_monthly(rows: list[MonthlyRow], *, initial_equity: float = 0.0) -> str:
    if not rows:
        return "(no trades)"
    lines: list[str] = []
    width = 116 if initial_equity > 0 else 80
    lines.append("=" * width)
    lines.append("MONTHLY BREAKDOWN")
    lines.append("=" * width)
    if initial_equity > 0:
        lines.append(
            f"{'period':<10}{'trades':>8}{'win%':>7}{'gross':>12}{'fees':>10}"
            f"{'net':>12}{'roi%':>8}{'maxDD':>12}{'dd%':>8}"
        )
    else:
        lines.append(f"{'period':<10}{'trades':>8}{'win%':>7}{'gross':>12}{'fees':>10}{'net':>12}")
    lines.append("-" * width)
    total_gross = 0.0
    total_fees = 0.0
    total_trades = 0
    total_wins = 0
    total_losses = 0
    max_drawdown = 0.0
    for r in rows:
        if initial_equity > 0:
            roi = r.net_pnl / initial_equity * 100.0
            dd_pct = r.max_drawdown_value / initial_equity * 100.0
            lines.append(
                f"{r.period:<10}{r.trades:>8}{r.win_rate * 100:>6.1f}%"
                f"{r.gross_pnl:>12.2f}{r.fees:>10.2f}{r.net_pnl:>12.2f}"
                f"{roi:>8.2f}{r.max_drawdown_value:>12.2f}{dd_pct:>8.2f}"
            )
        else:
            lines.append(
                f"{r.period:<10}{r.trades:>8}{r.win_rate * 100:>6.1f}%"
                f"{r.gross_pnl:>12.2f}{r.fees:>10.2f}{r.net_pnl:>12.2f}"
            )
        total_gross += r.gross_pnl
        total_fees += r.fees
        total_trades += r.trades
        total_wins += r.wins
        total_losses += r.losses
        max_drawdown = max(max_drawdown, r.max_drawdown_value)
    lines.append("-" * width)
    n_closed = total_wins + total_losses
    win_rate = total_wins / n_closed if n_closed else 0.0
    total_net = total_gross - total_fees
    if initial_equity > 0:
        lines.append(
            f"{'TOTAL':<10}{total_trades:>8}{win_rate * 100:>6.1f}%"
            f"{total_gross:>12.2f}{total_fees:>10.2f}{total_net:>12.2f}"
            f"{total_net / initial_equity * 100:>8.2f}"
            f"{max_drawdown:>12.2f}{max_drawdown / initial_equity * 100:>8.2f}"
        )
    else:
        lines.append(
            f"{'TOTAL':<10}{total_trades:>8}{win_rate * 100:>6.1f}%"
            f"{total_gross:>12.2f}{total_fees:>10.2f}{total_net:>12.2f}"
        )
    return "\n".join(lines)
