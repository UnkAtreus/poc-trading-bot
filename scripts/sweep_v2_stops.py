from __future__ import annotations

import argparse
import asyncio
import copy
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from bot.backtest.downloader import df_to_candles, load_or_fetch
from bot.backtest.monthly import by_month
from bot.backtest.runner import BacktestStopConfig, run_backtest
from bot.config import load_settings
from bot.logger import configure as configure_logging
from bot.risk.manager import RiskManager
from bot.signals.base import build as build_signal


SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "BNBUSDT",
    "LTCUSDT",
    "HYPEUSDT",
    "XAUTUSDT",
]
SIGNAL_NAME = "trend_filter"
SIGNAL_PARAMS = {
    "inner": "grid",
    "inner_anchor_period": 100,
    "inner_entry_bps": 30,
    "inner_step_bps": 15,
    "max_trend_bps": 15,
}


@dataclass(frozen=True)
class StopCase:
    name: str
    stops: BacktestStopConfig | None


def _parse_iso_to_ms(s: str) -> int:
    dt = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _cases() -> list[StopCase]:
    cases = [StopCase("baseline_no_stop", None)]
    cases.extend(
        StopCase(f"bep_stop_{bps}bps", BacktestStopConfig(bep_stop_bps=bps))
        for bps in (300, 500, 1000)
    )
    cases.extend(
        StopCase(f"symbol_loss_{usd}usd", BacktestStopConfig(max_symbol_loss_usd=usd))
        for usd in (1000, 1500, 2000)
    )
    cases.extend(
        StopCase(f"account_dd_{pct}pct", BacktestStopConfig(account_dd_stop_pct=pct))
        for pct in (10, 15, 20)
    )
    cases.extend(
        StopCase(
            f"max_hold_{hours}h",
            BacktestStopConfig(max_hold_seconds=hours * 3600.0),
        )
        for hours in (24, 48, 72)
    )
    cases.extend(
        [
            StopCase(
                "symbol_loss_1500usd_account_dd_20pct",
                BacktestStopConfig(max_symbol_loss_usd=1500, account_dd_stop_pct=20),
            ),
            StopCase(
                "bep_stop_1000bps_account_dd_20pct",
                BacktestStopConfig(bep_stop_bps=1000, account_dd_stop_pct=20),
            ),
            StopCase(
                "max_hold_72h_account_dd_20pct",
                BacktestStopConfig(max_hold_seconds=72 * 3600.0, account_dd_stop_pct=20),
            ),
            StopCase(
                "bep_stop_1000bps_symbol_loss_2000usd",
                BacktestStopConfig(bep_stop_bps=1000, max_symbol_loss_usd=2000),
            ),
        ]
    )
    return cases


def _apply_v2_overrides(settings) -> None:
    settings.bot.offsets.tp_offset_bps = 100
    settings.bot.sizing.margin_usd = 114
    settings.bot.sizing.leverage = 10
    settings.bot.risk.max_notional_account_usd = 50_000
    settings.bot.risk.max_notional_per_symbol_usd = 10_000
    settings.bot.risk.daily_loss_limit_usd = 5_000


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2026-01-01")
    parser.add_argument("--initial-equity", type=float, default=30_000)
    parser.add_argument("--out-prefix", default="v2_stop_sweep_2024_2025_equity30000")
    args = parser.parse_args()

    configure_logging("WARNING")
    base_settings = load_settings()
    _apply_v2_overrides(base_settings)

    start_ms = _parse_iso_to_ms(args.start)
    end_ms = _parse_iso_to_ms(args.end)
    candles = {}
    for symbol in SYMBOLS:
        df = await asyncio.to_thread(load_or_fetch, symbol, start_ms, end_ms, "data/klines")
        if not df.empty:
            candles[symbol] = df_to_candles(df, symbol)

    rows: list[dict[str, str | float | int]] = []
    detail_lines: list[str] = []
    for case in _cases():
        settings = copy.deepcopy(base_settings)
        signal = build_signal(SIGNAL_NAME, dict(SIGNAL_PARAMS))
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
        worst_monthly_dd = max((m.max_drawdown_value for m in monthly), default=0.0)
        roi = result.net_pnl / args.initial_equity * 100.0
        dd_pct = result.max_drawdown_pct * 100.0
        open_count = sum(
            1 for ctx in result.final_state.values()
            if ctx.state.value != "IDLE" and ctx.position_size > 0
        )
        meets_target = roi >= 36.0
        score = (roi / dd_pct) if dd_pct > 0 else 0.0
        row = {
            "case": case.name,
            "trades": len(result.trades),
            "wins": result.wins,
            "losses": result.losses,
            "stop_exits": result.stopped,
            "win_rate_pct": result.win_rate * 100.0,
            "net_pnl": result.net_pnl,
            "roi_pct": roi,
            "max_dd": result.max_drawdown,
            "max_dd_pct": dd_pct,
            "worst_monthly_dd": worst_monthly_dd,
            "worst_monthly_dd_pct": worst_monthly_dd / args.initial_equity * 100.0,
            "open_symbols": open_count,
            "meets_1_5pct_month_target": "yes" if meets_target else "no",
            "roi_to_dd": score,
        }
        rows.append(row)
        detail_lines.append(
            f"{case.name}: net={result.net_pnl:.2f} roi={roi:.2f}% "
            f"dd={dd_pct:.2f}% trades={len(result.trades)} "
            f"losses={result.losses} stops={result.stopped} open={open_count}"
        )

    logs_dir = Path("logs")
    reports_dir = Path("reports")
    logs_dir.mkdir(exist_ok=True)
    reports_dir.mkdir(exist_ok=True)

    csv_path = logs_dir / f"{args.out_prefix}.csv"
    txt_path = logs_dir / f"{args.out_prefix}.txt"
    md_path = reports_dir / f"{args.out_prefix}.md"

    fieldnames = list(rows[0].keys())
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with txt_path.open("w") as f:
        f.write("\n".join(detail_lines))
        f.write("\n")

    target_rows = [r for r in rows if r["meets_1_5pct_month_target"] == "yes"]
    if target_rows:
        best = min(target_rows, key=lambda r: (float(r["max_dd_pct"]), -float(r["roi_pct"])))
    else:
        best = max(rows, key=lambda r: float(r["roi_to_dd"]))
    by_dd = sorted(rows, key=lambda r: (float(r["max_dd_pct"]), -float(r["roi_pct"])))
    by_roi = sorted(rows, key=lambda r: -float(r["roi_pct"]))

    def fmt_row(r) -> str:
        return (
            f"| {r['case']} | {float(r['net_pnl']):,.2f} | {float(r['roi_pct']):.2f}% | "
            f"{float(r['max_dd_pct']):.2f}% | {float(r['worst_monthly_dd_pct']):.2f}% | "
            f"{int(r['trades'])} | {float(r['win_rate_pct']):.2f}% | {int(r['stop_exits'])} | "
            f"{int(r['open_symbols'])} | {r['meets_1_5pct_month_target']} |"
        )

    md: list[str] = [
        "# V2 Stop-Loss Sweep",
        "",
        f"- Date range: `{args.start}` to `{args.end}`",
        f"- Initial equity: `{args.initial_equity:,.0f} USDT`",
        "- Target marker: `36% ROI` over two years, equal to 1.5% average per month.",
        f"- Best by target-first risk rule: `{best['case']}`",
        f"- Raw CSV: `{csv_path}`",
        f"- Raw text: `{txt_path}`",
        "",
        "## Best Candidate",
        "",
        "| Case | Net PnL | ROI | Account max DD | Worst monthly DD | Trades | Win rate | Stop exits | Open symbols | Target? |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        fmt_row(best),
        "",
        "## Lowest Drawdown",
        "",
        "| Case | Net PnL | ROI | Account max DD | Worst monthly DD | Trades | Win rate | Stop exits | Open symbols | Target? |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    md.extend(fmt_row(r) for r in by_dd[:8])
    md.extend([
        "",
        "## Highest ROI",
        "",
        "| Case | Net PnL | ROI | Account max DD | Worst monthly DD | Trades | Win rate | Stop exits | Open symbols | Target? |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    md.extend(fmt_row(r) for r in by_roi[:8])
    md.extend([
        "",
        "## All Cases",
        "",
        "| Case | Net PnL | ROI | Account max DD | Worst monthly DD | Trades | Win rate | Stop exits | Open symbols | Target? |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    md.extend(fmt_row(r) for r in rows)
    md.append("")
    with md_path.open("w") as f:
        f.write("\n".join(md))

    print(f"wrote {csv_path}")
    print(f"wrote {txt_path}")
    print(f"wrote {md_path}")
    print(f"best={best['case']} roi={float(best['roi_pct']):.2f}% dd={float(best['max_dd_pct']):.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
