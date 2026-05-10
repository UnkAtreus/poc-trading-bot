from __future__ import annotations

import argparse
import asyncio
import copy
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from bot.backtest.downloader import df_to_candles, load_or_fetch
from bot.backtest.monthly import MonthlyRow, by_month
from bot.backtest.runner import BacktestStopConfig, run_backtest
from bot.config import load_settings
from bot.logger import configure as configure_logging
from bot.risk.manager import RiskManager
from bot.signals.base import build as build_signal


DEFAULT_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "BNBUSDT",
    "LTCUSDT",
]

V3_SIGNAL = {
    "inner": "trend_filter",
    "btc_ema_period": 200,
    "btc_return_bars": 1440,
    "btc_drop_bps": 500,
    "inner_inner": "grid",
    "inner_inner_anchor_period": 100,
    "inner_inner_entry_bps": 30,
    "inner_inner_step_bps": 15,
    "inner_max_trend_bps": 15,
}


@dataclass(frozen=True)
class StableCase:
    name: str
    tp_bps: float
    margin_usd: float
    account_cap: float
    symbol_cap: float
    stops: BacktestStopConfig | None


def _parse_iso_to_ms(s: str) -> int:
    dt = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _cases() -> list[StableCase]:
    return [
        StableCase("v3_baseline", 100, 114, 20_000, 4_560, None),
        StableCase(
            "v4_tp100_hold30d_lock1p5_dd10",
            100,
            114,
            20_000,
            4_560,
            BacktestStopConfig(
                max_hold_seconds=30 * 24 * 3600,
                monthly_profit_lock_pct=1.5,
                monthly_dd_stop_pct=10,
            ),
        ),
        StableCase(
            "v4_tp50_hold30d_lock1p5_dd10",
            50,
            114,
            20_000,
            4_560,
            BacktestStopConfig(
                max_hold_seconds=30 * 24 * 3600,
                monthly_profit_lock_pct=1.5,
                monthly_dd_stop_pct=10,
            ),
        ),
        StableCase(
            "v4_tp100_hold60d_lock1p5",
            100,
            114,
            20_000,
            4_560,
            BacktestStopConfig(
                max_hold_seconds=60 * 24 * 3600,
                monthly_profit_lock_pct=1.5,
            ),
        ),
        StableCase(
            "v4_tp50_hold60d_lock1p5",
            50,
            114,
            20_000,
            4_560,
            BacktestStopConfig(
                max_hold_seconds=60 * 24 * 3600,
                monthly_profit_lock_pct=1.5,
            ),
        ),
        StableCase(
            "v4_tp50_hold30d_lock1p5",
            50,
            114,
            20_000,
            4_560,
            BacktestStopConfig(
                max_hold_seconds=30 * 24 * 3600,
                monthly_profit_lock_pct=1.5,
            ),
        ),
        StableCase(
            "v4_tp50_hold14d_lock1p5_dd8",
            50,
            114,
            20_000,
            4_560,
            BacktestStopConfig(
                max_hold_seconds=14 * 24 * 3600,
                monthly_profit_lock_pct=1.5,
                monthly_dd_stop_pct=8,
            ),
        ),
        StableCase(
            "v4_tp30_hold14d_lock1p5_dd8",
            30,
            114,
            20_000,
            4_560,
            BacktestStopConfig(
                max_hold_seconds=14 * 24 * 3600,
                monthly_profit_lock_pct=1.5,
                monthly_dd_stop_pct=8,
            ),
        ),
        StableCase(
            "v4_tp30_hold7d_lock1p5_dd8",
            30,
            114,
            20_000,
            4_560,
            BacktestStopConfig(
                max_hold_seconds=7 * 24 * 3600,
                monthly_profit_lock_pct=1.5,
                monthly_dd_stop_pct=8,
            ),
        ),
    ]


def _apply_case(settings, case: StableCase) -> None:
    settings.bot.offsets.tp_offset_bps = case.tp_bps
    settings.bot.sizing.margin_usd = case.margin_usd
    settings.bot.sizing.leverage = 10
    settings.bot.risk.max_notional_account_usd = case.account_cap
    settings.bot.risk.max_notional_per_symbol_usd = case.symbol_cap
    settings.bot.risk.daily_loss_limit_usd = 5_000


def _longest_zero_trade_stretch(rows: list[MonthlyRow]) -> tuple[int, str]:
    best_len = 0
    best_start = ""
    best_end = ""
    cur_len = 0
    cur_start = ""
    cur_end = ""
    for row in rows:
        if row.trades == 0:
            if cur_len == 0:
                cur_start = row.period
            cur_len += 1
            cur_end = row.period
            if cur_len > best_len:
                best_len = cur_len
                best_start = cur_start
                best_end = cur_end
        else:
            cur_len = 0
            cur_start = ""
            cur_end = ""
    if best_len == 0:
        return 0, ""
    return best_len, best_start if best_start == best_end else f"{best_start}..{best_end}"


def _open_symbols(result) -> int:
    return sum(
        1
        for ctx in result.final_state.values()
        if ctx.state.value != "IDLE" and ctx.position_size > 0
    )


def _metrics(case: StableCase, result, monthly: list[MonthlyRow], initial_equity: float) -> dict:
    months = len(monthly)
    net_by_month = [row.net_pnl for row in monthly]
    positive_months = sum(1 for pnl in net_by_month if pnl > 0)
    target_1pct_months = sum(1 for pnl in net_by_month if pnl >= initial_equity * 0.01)
    target_1p5pct_months = sum(1 for pnl in net_by_month if pnl >= initial_equity * 0.015)
    zero_months = sum(1 for row in monthly if row.trades == 0)
    longest_zero, longest_zero_period = _longest_zero_trade_stretch(monthly)
    worst_monthly_dd = max((row.max_drawdown_value for row in monthly), default=0.0)
    avg_monthly_roi = (sum(net_by_month) / months / initial_equity * 100.0) if months else 0.0
    positive_month_pct = positive_months / months * 100.0 if months else 0.0
    target_1pct_month_pct = target_1pct_months / months * 100.0 if months else 0.0
    target_1p5pct_month_pct = target_1p5pct_months / months * 100.0 if months else 0.0
    worst_monthly_dd_pct = worst_monthly_dd / initial_equity * 100.0 if initial_equity else 0.0
    roi_pct = result.net_pnl / initial_equity * 100.0 if initial_equity else 0.0
    stable_candidate = (
        avg_monthly_roi >= 1.0
        and positive_month_pct >= 70.0
        and longest_zero <= 1
        and worst_monthly_dd_pct <= 10.0
        and result.max_drawdown_pct * 100.0 <= 25.0
    )
    score = (
        avg_monthly_roi * 10.0
        + positive_month_pct / 10.0
        + target_1pct_month_pct / 10.0
        - longest_zero * 2.0
        - worst_monthly_dd_pct
        - result.max_drawdown_pct * 100.0 / 2.0
    )
    return {
        "case": case.name,
        "tp_bps": case.tp_bps,
        "margin_usd": case.margin_usd,
        "account_cap": case.account_cap,
        "symbol_cap": case.symbol_cap,
        "net_pnl": result.net_pnl,
        "roi_pct": roi_pct,
        "avg_monthly_roi_pct": avg_monthly_roi,
        "positive_month_pct": positive_month_pct,
        "target_1pct_month_pct": target_1pct_month_pct,
        "target_1p5pct_month_pct": target_1p5pct_month_pct,
        "zero_months": zero_months,
        "longest_zero_months": longest_zero,
        "longest_zero_period": longest_zero_period,
        "max_dd": result.max_drawdown,
        "max_dd_pct": result.max_drawdown_pct * 100.0,
        "worst_monthly_dd": worst_monthly_dd,
        "worst_monthly_dd_pct": worst_monthly_dd_pct,
        "trades": len(result.trades),
        "wins": result.wins,
        "losses": result.losses,
        "stop_exits": result.stopped,
        "win_rate_pct": result.win_rate * 100.0,
        "open_symbols": _open_symbols(result),
        "stable_candidate": "yes" if stable_candidate else "no",
        "score": score,
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2022-01-01")
    parser.add_argument("--end", default="2024-01-01")
    parser.add_argument("--initial-equity", type=float, default=30_000)
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--out-prefix", default="")
    parser.add_argument("--case-filter", default="", help="Comma-separated substrings; only matching cases run")
    args = parser.parse_args()

    configure_logging("WARNING")
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    out_prefix = args.out_prefix or f"v4_stable_income_sweep_{args.start}_{args.end}".replace("-", "")
    start_ms = _parse_iso_to_ms(args.start)
    end_ms = _parse_iso_to_ms(args.end)

    candles = {}
    for symbol in symbols:
        df = await asyncio.to_thread(load_or_fetch, symbol, start_ms, end_ms, "data/klines")
        if not df.empty:
            candles[symbol] = df_to_candles(df, symbol)

    base_settings = load_settings()
    rows: list[dict] = []
    monthly_tables: dict[str, list[MonthlyRow]] = {}
    cases = _cases()
    if args.case_filter:
        needles = [s.strip() for s in args.case_filter.split(",") if s.strip()]
        cases = [case for case in cases if any(needle in case.name for needle in needles)]
    if not cases:
        raise SystemExit("no cases matched --case-filter")

    for case in cases:
        print(f"running {case.name}", flush=True)
        settings = copy.deepcopy(base_settings)
        _apply_case(settings, case)
        signal = build_signal("crash_guard", dict(V3_SIGNAL))
        risk = RiskManager(settings=settings, state_dir=Path("data/state"))
        result = await run_backtest(
            settings,
            candles,
            signal,
            risk=risk,
            initial_equity=args.initial_equity,
            stops=case.stops,
        )
        monthly = by_month(result)
        monthly_tables[case.name] = monthly
        rows.append(_metrics(case, result, monthly, args.initial_equity))

    logs_dir = Path("logs")
    reports_dir = Path("reports")
    logs_dir.mkdir(exist_ok=True)
    reports_dir.mkdir(exist_ok=True)
    csv_path = logs_dir / f"{out_prefix}.csv"
    monthly_csv_path = logs_dir / f"{out_prefix}_monthly.csv"
    report_path = reports_dir / f"{out_prefix}.md"

    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    with monthly_csv_path.open("w", newline="") as f:
        fieldnames = ["case", "period", "trades", "net_pnl", "roi_pct", "max_dd", "dd_pct"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for case_name, monthly in monthly_tables.items():
            for row in monthly:
                writer.writerow(
                    {
                        "case": case_name,
                        "period": row.period,
                        "trades": row.trades,
                        "net_pnl": row.net_pnl,
                        "roi_pct": row.net_pnl / args.initial_equity * 100.0,
                        "max_dd": row.max_drawdown_value,
                        "dd_pct": row.max_drawdown_value / args.initial_equity * 100.0,
                    }
                )

    ranked = sorted(rows, key=lambda r: (r["stable_candidate"] != "yes", -float(r["score"])))
    best = ranked[0]

    def fmt(row: dict) -> str:
        return (
            f"| {row['case']} | {float(row['net_pnl']):,.2f} | "
            f"{float(row['roi_pct']):.2f}% | {float(row['avg_monthly_roi_pct']):.2f}% | "
            f"{float(row['positive_month_pct']):.1f}% | {float(row['target_1pct_month_pct']):.1f}% | "
            f"{int(row['longest_zero_months'])} | {float(row['max_dd_pct']):.2f}% | "
            f"{float(row['worst_monthly_dd_pct']):.2f}% | {int(row['trades'])} | "
            f"{int(row['stop_exits'])} | {int(row['open_symbols'])} | {row['stable_candidate']} |"
        )

    md = [
        "# V4 Stable Income Sweep",
        "",
        f"- Window: `{args.start}` to `{args.end}`",
        f"- Symbols: `{','.join(candles)}`",
        f"- Initial equity: `{args.initial_equity:,.0f} USDT`",
        "- Base signal: v3 crash balanced.",
        "- Stable candidate rule: avg monthly ROI >= 1.0%, positive months >= 70%, longest zero stretch <= 1 month, worst monthly DD <= 10%, account max DD <= 25%.",
        f"- Summary CSV: `{csv_path}`",
        f"- Monthly CSV: `{monthly_csv_path}`",
        "",
        "## Best Ranked",
        "",
        "| Case | Net PnL | ROI | Avg monthly ROI | Positive months | Months >=1% | Longest zero | Max DD | Worst monthly DD | Trades | Stops | Open | Stable? |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        fmt(best),
        "",
        "## All Cases",
        "",
        "| Case | Net PnL | ROI | Avg monthly ROI | Positive months | Months >=1% | Longest zero | Max DD | Worst monthly DD | Trades | Stops | Open | Stable? |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    md.extend(fmt(row) for row in ranked)
    md.extend(
        [
            "",
            "## Read",
            "",
            "This is a backtest-only v4 stability experiment. The monthly profit lock blocks new entries after the realized monthly target is reached, the monthly DD stop closes open positions and blocks new entries for the rest of that UTC month, and max-hold closes stale positions. These controls are not live orchestration yet.",
        ]
    )
    report_path.write_text("\n".join(md) + "\n")
    print(f"wrote {csv_path}")
    print(f"wrote {monthly_csv_path}")
    print(f"wrote {report_path}")
    print(f"best={best['case']} stable={best['stable_candidate']} score={float(best['score']):.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
