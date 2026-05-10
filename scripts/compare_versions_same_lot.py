from __future__ import annotations

import argparse
import asyncio
import copy
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from bot.backtest.downloader import df_to_candles, load_or_fetch
from bot.backtest.runner import run_backtest
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


@dataclass(frozen=True)
class Window:
    name: str
    start: str
    end: str


@dataclass(frozen=True)
class Version:
    name: str
    signal_name: str
    signal_params: dict
    margin_usd: float
    account_cap: float
    symbol_cap: float


def _parse_iso_to_ms(s: str) -> int:
    dt = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _windows() -> list[Window]:
    return [
        Window("2026_ytd", "2026-01-01", "2026-05-03"),
        Window("2025", "2025-01-01", "2026-01-01"),
        Window("2024_2025_continuous", "2024-01-01", "2026-01-01"),
    ]


def _versions() -> list[Version]:
    v1_signal = {
        "inner": "grid",
        "inner_anchor_period": 200,
        "inner_entry_bps": 30,
        "inner_step_bps": 15,
        "max_trend_bps": 30,
    }
    v2_signal = {
        "inner": "grid",
        "inner_anchor_period": 100,
        "inner_entry_bps": 30,
        "inner_step_bps": 15,
        "max_trend_bps": 15,
    }
    v3_signal = {
        "inner": "trend_filter",
        "inner_inner": "grid",
        "inner_inner_anchor_period": 100,
        "inner_inner_entry_bps": 30,
        "inner_inner_step_bps": 15,
        "inner_max_trend_bps": 15,
        "btc_ema_period": 200,
        "btc_return_bars": 1440,
        "btc_drop_bps": 500,
    }
    return [
        Version("v1_same_lot", "trend_filter", v1_signal, 114, 50_000, 10_000),
        Version("v2_baseline", "trend_filter", v2_signal, 114, 50_000, 10_000),
        Version("v3_crash_balanced", "crash_guard", v3_signal, 114, 20_000, 4_560),
    ]


async def _load_window(window: Window) -> dict[str, list]:
    start_ms = _parse_iso_to_ms(window.start)
    end_ms = _parse_iso_to_ms(window.end)
    candles = {}
    for symbol in SYMBOLS:
        df = await asyncio.to_thread(load_or_fetch, symbol, start_ms, end_ms, "data/klines")
        if not df.empty:
            candles[symbol] = df_to_candles(df, symbol)
    return candles


def _apply_version(settings, version: Version) -> None:
    settings.bot.sizing.margin_usd = version.margin_usd
    settings.bot.sizing.leverage = 10
    settings.bot.offsets.tp_offset_bps = 100
    settings.bot.risk.max_notional_account_usd = version.account_cap
    settings.bot.risk.max_notional_per_symbol_usd = version.symbol_cap
    settings.bot.risk.daily_loss_limit_usd = 5_000
    settings.bot.risk.max_consecutive_losses = 5
    settings.bot.risk.cooldown_minutes = 60


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--initial-equity", type=float, default=30_000)
    args = parser.parse_args()

    configure_logging("WARNING")
    base_settings = load_settings()
    rows: list[dict] = []
    for window in _windows():
        print(f"loading {window.name}", flush=True)
        candles = await _load_window(window)
        for version in _versions():
            print(f"running {version.name}_{window.name}", flush=True)
            settings = copy.deepcopy(base_settings)
            _apply_version(settings, version)
            signal = build_signal(version.signal_name, dict(version.signal_params))
            risk = RiskManager(settings=settings, state_dir=Path("data/state"))
            result = await run_backtest(
                settings,
                candles,
                signal,
                risk=risk,
                initial_equity=args.initial_equity,
            )
            open_symbols = sum(
                1
                for ctx in result.final_state.values()
                if ctx.state.value != "IDLE" and ctx.position_size > 0
            )
            rows.append(
                {
                    "version": version.name,
                    "window": window.name,
                    "start": window.start,
                    "end": window.end,
                    "margin_usd": version.margin_usd,
                    "account_cap": version.account_cap,
                    "symbol_cap": version.symbol_cap,
                    "net_pnl": result.net_pnl,
                    "roi_pct": result.net_pnl / args.initial_equity * 100.0,
                    "max_dd": result.max_drawdown,
                    "max_dd_pct": result.max_drawdown_pct * 100.0,
                    "trades": len(result.trades),
                    "wins": result.wins,
                    "losses": result.losses,
                    "win_rate_pct": result.win_rate * 100.0,
                    "open_symbols": open_symbols,
                }
            )

    logs_dir = Path("logs")
    reports_dir = Path("reports")
    logs_dir.mkdir(exist_ok=True)
    reports_dir.mkdir(exist_ok=True)
    csv_path = logs_dir / "version_compare_same_lot_matrix.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    def fmt(r: dict) -> str:
        return (
            f"| {r['version']} | {r['window']} | {float(r['net_pnl']):,.2f} | "
            f"{float(r['roi_pct']):.2f}% | {float(r['max_dd_pct']):.2f}% | "
            f"{int(r['trades'])} | {float(r['win_rate_pct']):.2f}% | "
            f"{int(r['open_symbols'])} |"
        )

    rows_by_window = {w.name: [r for r in rows if r["window"] == w.name] for w in _windows()}
    md: list[str] = [
        "# Version Comparison - Same Lot Size",
        "",
        "- v1 is tested with the same lot size as v2: 114 USDT margin, 10x leverage, 1,140 USDT notional/order.",
        "- v2 baseline uses the original v2 signal and 50,000 / 10,000 notional caps.",
        "- v3 crash balanced uses v2 signal plus crash guard and 20,000 / 4,560 notional caps.",
        f"- Raw CSV: `{csv_path}`",
        "",
    ]
    for window_name, window_rows in rows_by_window.items():
        ranked = sorted(window_rows, key=lambda r: (-float(r["roi_pct"]), float(r["max_dd_pct"])))
        md.extend(
            [
                f"## {window_name}",
                "",
                "| Version | Window | Net PnL | ROI | Max DD % | Trades | Win rate | Open symbols |",
                "|---|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        md.extend(fmt(r) for r in ranked)
        md.append("")

    continuous_rows = rows_by_window["2024_2025_continuous"]
    best_profit = max(rows_by_window["2026_ytd"], key=lambda r: float(r["roi_pct"]))
    best_cont_dd = min(continuous_rows, key=lambda r: float(r["max_dd_pct"]))
    md.extend(
        [
            "## Recommendation Logic",
            "",
            f"- Best 2026 YTD profit: `{best_profit['version']}`.",
            f"- Lowest continuous 2024-2025 DD: `{best_cont_dd['version']}`.",
            "- If liquidation/carryover safety is priority, choose the lowest continuous DD.",
            "- If short-term 2026 YTD profit is priority, choose the best 2026 YTD profit.",
        ]
    )
    report_path = reports_dir / "version_compare_same_lot_matrix.md"
    report_path.write_text("\n".join(md) + "\n")
    print(f"wrote {csv_path}")
    print(f"wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
