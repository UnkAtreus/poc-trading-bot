from __future__ import annotations

import argparse
import asyncio
import copy
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bot.backtest.downloader import df_to_candles, load_or_fetch
from bot.backtest.runner import run_backtest
from bot.backtest.stability import StabilityGates, analyze_stability
from bot.config import load_settings
from bot.logger import configure as configure_logging
from bot.risk.manager import RiskManager
from bot.signals.base import build as build_signal


@dataclass(frozen=True)
class RunRow:
    start: str
    end: str
    bars: int
    trades: int
    wins: int
    losses: int
    win_rate_pct: float
    net_pnl: float
    roi_pct: float
    max_dd: float
    max_dd_pct: float
    liquidated: bool
    near_liquidation: bool
    min_liq_distance_pct: float
    worst_unrealized_loss: float
    final_open_exposure: float
    months: int
    positive_month_pct: float
    target_month_pct: float
    avg_monthly_roi_pct: float
    median_monthly_roi_pct: float
    worst_monthly_roi_pct: float
    worst_monthly_dd_pct: float
    longest_non_positive_stretch: int
    stability_score: float
    launch_pass: bool


def _parse_day(day: str) -> datetime:
    return datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _even_start_dates(start: datetime, latest_start: datetime, count: int) -> list[datetime]:
    if count <= 1:
        return [start]
    span_seconds = (latest_start - start).total_seconds()
    return [
        start + timedelta(seconds=round(span_seconds * i / (count - 1)))
        for i in range(count)
    ]


async def _load_full_candles(
    symbols: list[str],
    start: datetime,
    end: datetime,
    *,
    workers: int,
) -> dict[str, list]:
    sem = asyncio.Semaphore(max(1, workers))
    start_ms = _to_ms(start)
    end_ms = _to_ms(end)

    async def load_one(symbol: str):
        async with sem:
            df = await asyncio.to_thread(load_or_fetch, symbol, start_ms, end_ms, "data/klines")
            if df.empty:
                return None
            return symbol, df_to_candles(df, symbol)

    loaded = await asyncio.gather(*(load_one(symbol) for symbol in symbols))
    return dict(item for item in loaded if item is not None)


def _slice_from(candles_by_symbol: dict[str, list], start_ts: float) -> dict[str, list]:
    out: dict[str, list] = {}
    for symbol, candles in candles_by_symbol.items():
        # Avoid importing bisect key support assumptions across Python versions.
        lo = 0
        hi = len(candles)
        while lo < hi:
            mid = (lo + hi) // 2
            if candles[mid].timestamp < start_ts:
                lo = mid + 1
            else:
                hi = mid
        rows = candles[lo:]
        if rows:
            out[symbol] = rows
    return out


def _passes_launch_gates(result, stability, *, max_drawdown_pct: float, max_open_exposure: float) -> bool:
    return (
        not result.liquidated
        and not result.near_liquidation
        and result.max_drawdown_pct * 100.0 <= max_drawdown_pct
        and result.final_open_exposure <= max_open_exposure
        and stability.passes
    )


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--earliest-start", default="2021-01-01")
    parser.add_argument("--latest-start", default="2026-01-01")
    parser.add_argument("--end", default="2026-05-09")
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT")
    parser.add_argument("--initial-equity", type=float, default=30_000.0)
    parser.add_argument("--kline-workers", type=int, default=4)
    parser.add_argument("--target-monthly-roi-pct", type=float, default=0.5)
    parser.add_argument("--min-positive-month-pct", type=float, default=70.0)
    parser.add_argument("--min-target-month-pct", type=float, default=50.0)
    parser.add_argument("--max-non-positive-stretch", type=int, default=2)
    parser.add_argument("--max-worst-monthly-dd-pct", type=float, default=10.0)
    parser.add_argument("--max-drawdown-pct", type=float, default=25.0)
    parser.add_argument("--max-open-exposure", type=float, default=5_000.0)
    parser.add_argument("--output-csv", default="logs/start_date_sensitivity_500_core6.csv")
    parser.add_argument("--output-report", default="reports/start_date_sensitivity_500_core6.md")
    args = parser.parse_args()

    configure_logging("WARNING")
    settings = load_settings()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    earliest = _parse_day(args.earliest_start)
    latest = _parse_day(args.latest_start)
    end = _parse_day(args.end)
    starts = _even_start_dates(earliest, latest, args.count)
    gates = StabilityGates(
        target_monthly_roi_pct=args.target_monthly_roi_pct,
        min_positive_month_pct=args.min_positive_month_pct,
        min_target_month_pct=args.min_target_month_pct,
        max_non_positive_stretch=args.max_non_positive_stretch,
        max_worst_monthly_dd_pct=args.max_worst_monthly_dd_pct,
    )

    print(f"loading candles {args.earliest_start} -> {args.end} symbols={','.join(symbols)}", flush=True)
    full_candles = await _load_full_candles(symbols, earliest, end, workers=args.kline_workers)
    if not full_candles:
        raise SystemExit("no candle data loaded")

    rows: list[RunRow] = []
    for idx, start in enumerate(starts, start=1):
        start_day = start.strftime("%Y-%m-%d")
        sliced = _slice_from(full_candles, start.timestamp())
        bars = sum(len(v) for v in sliced.values())
        print(f"[{idx}/{len(starts)}] {start_day} bars={bars}", flush=True)
        scenario_settings = copy.deepcopy(settings)
        signal = build_signal(
            scenario_settings.bot.signal.engine,
            dict(scenario_settings.bot.signal.params),
        )
        risk = RiskManager(settings=scenario_settings, state_dir=Path("data/state"))
        result = await run_backtest(
            scenario_settings,
            sliced,
            signal,
            risk=risk,
            initial_equity=args.initial_equity,
        )
        stability = analyze_stability(result, gates=gates, initial_equity=args.initial_equity)
        rows.append(RunRow(
            start=start_day,
            end=args.end,
            bars=bars,
            trades=len(result.trades),
            wins=result.wins,
            losses=result.losses,
            win_rate_pct=result.win_rate * 100.0,
            net_pnl=result.net_pnl,
            roi_pct=result.net_pnl / args.initial_equity * 100.0,
            max_dd=result.max_drawdown,
            max_dd_pct=result.max_drawdown_pct * 100.0,
            liquidated=result.liquidated,
            near_liquidation=result.near_liquidation,
            min_liq_distance_pct=result.min_liq_distance_pct,
            worst_unrealized_loss=result.worst_unrealized_loss,
            final_open_exposure=result.final_open_exposure,
            months=stability.months,
            positive_month_pct=stability.positive_month_pct,
            target_month_pct=stability.target_month_pct,
            avg_monthly_roi_pct=stability.avg_monthly_roi_pct,
            median_monthly_roi_pct=stability.median_monthly_roi_pct,
            worst_monthly_roi_pct=stability.worst_monthly_roi_pct,
            worst_monthly_dd_pct=stability.worst_monthly_dd_pct,
            longest_non_positive_stretch=stability.longest_non_positive_stretch,
            stability_score=stability.score,
            launch_pass=_passes_launch_gates(
                result,
                stability,
                max_drawdown_pct=args.max_drawdown_pct,
                max_open_exposure=args.max_open_exposure,
            ),
        ))

    csv_path = Path(args.output_csv)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(RunRow.__dataclass_fields__.keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)

    report_path = Path(args.output_report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_render_report(rows, args, csv_path), encoding="utf-8")
    print(f"wrote {csv_path}")
    print(f"wrote {report_path}")
    return 0


def _render_report(rows: list[RunRow], args, csv_path: Path) -> str:
    passed = [r for r in rows if r.launch_pass]
    by_score = sorted(rows, key=lambda r: (-r.stability_score, r.max_dd_pct, r.final_open_exposure))
    worst_dd = max(rows, key=lambda r: r.max_dd_pct)
    worst_open = max(rows, key=lambda r: r.final_open_exposure)
    worst_stretch = max(rows, key=lambda r: r.longest_non_positive_stretch)
    median_roi = sorted(r.roi_pct for r in rows)[len(rows) // 2]

    def line(r: RunRow) -> str:
        return (
            f"| {r.start} | {r.launch_pass} | {r.net_pnl:,.2f} | {r.roi_pct:.2f}% | "
            f"{r.max_dd_pct:.2f}% | {r.final_open_exposure:,.2f} | "
            f"{r.positive_month_pct:.1f}% | {r.target_month_pct:.1f}% | "
            f"{r.longest_non_positive_stretch} | {r.worst_monthly_dd_pct:.2f}% |"
        )

    md = [
        "# 500 Start-Date Sensitivity Report",
        "",
        f"- Start-date range: `{args.earliest_start}` to `{args.latest_start}`",
        f"- End date: `{args.end}`",
        f"- Test count: `{len(rows)}`",
        f"- Symbols: `{args.symbols}`",
        f"- Raw CSV: `{csv_path}`",
        "",
        "## Summary",
        "",
        f"- Launch-pass starts: `{len(passed)} / {len(rows)}`",
        f"- Median ROI across starts: `{median_roi:.2f}%`",
        f"- Worst max DD start: `{worst_dd.start}` at `{worst_dd.max_dd_pct:.2f}%`",
        f"- Worst open exposure start: `{worst_open.start}` at `{worst_open.final_open_exposure:,.2f} USDT`",
        f"- Worst zero/non-positive stretch start: `{worst_stretch.start}` at `{worst_stretch.longest_non_positive_stretch}` months",
        "",
        "## Top 20 By Stability Score",
        "",
        "| Start | Launch pass | Net PnL | ROI | Max DD | Open exposure | Positive months | Target months | Zero stretch | Worst monthly DD |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    md.extend(line(r) for r in by_score[:20])
    md.extend([
        "",
        "## Worst 20 By Max Drawdown",
        "",
        "| Start | Launch pass | Net PnL | ROI | Max DD | Open exposure | Positive months | Target months | Zero stretch | Worst monthly DD |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    md.extend(line(r) for r in sorted(rows, key=lambda r: -r.max_dd_pct)[:20])
    md.extend([
        "",
        "## Decision Rule",
        "",
        "A strategy is not start-date robust unless every tested start date passes the launch gate.",
        "If any row fails because of liquidation, near-liquidation, high drawdown, high open exposure, or unstable monthly profit, reduce lot size or route that market condition to `no_trade`.",
        "",
    ])
    return "\n".join(md)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
