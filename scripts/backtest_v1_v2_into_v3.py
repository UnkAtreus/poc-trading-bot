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
class Variant:
    name: str
    signal_name: str
    signal_params: dict
    margin_usd: float


@dataclass(frozen=True)
class Window:
    name: str
    start: str
    end: str


def _parse_iso_to_ms(s: str) -> int:
    dt = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _crash_guard(inner_params: dict) -> dict:
    return {
        "inner": "trend_filter",
        "btc_ema_period": 200,
        "btc_return_bars": 1440,
        "btc_drop_bps": 500,
        **{f"inner_{k}": v for k, v in inner_params.items()},
    }


def _v1_inner() -> dict:
    return {
        "inner": "grid",
        "inner_anchor_period": 200,
        "inner_entry_bps": 30,
        "inner_step_bps": 15,
        "max_trend_bps": 30,
    }


def _v2_inner() -> dict:
    return {
        "inner": "grid",
        "inner_anchor_period": 100,
        "inner_entry_bps": 30,
        "inner_step_bps": 15,
        "max_trend_bps": 15,
    }


def _dual_params(mode: str) -> dict:
    return {
        "inner": "dual_signal",
        "btc_ema_period": 200,
        "btc_return_bars": 1440,
        "btc_drop_bps": 500,
        "inner_left": "trend_filter",
        "inner_left_inner": "grid",
        "inner_left_inner_anchor_period": 200,
        "inner_left_inner_entry_bps": 30,
        "inner_left_inner_step_bps": 15,
        "inner_left_max_trend_bps": 30,
        "inner_right": "trend_filter",
        "inner_right_inner": "grid",
        "inner_right_inner_anchor_period": 100,
        "inner_right_inner_entry_bps": 30,
        "inner_right_inner_step_bps": 15,
        "inner_right_max_trend_bps": 15,
        "inner_mode": mode,
        "inner_conflict": "none",
    }


def _variants() -> list[Variant]:
    return [
        Variant("v1_into_v3", "crash_guard", _crash_guard(_v1_inner()), 66),
        Variant("v2_into_v3", "crash_guard", _crash_guard(_v2_inner()), 114),
        Variant("v1v2_agree_into_v3", "crash_guard", _dual_params("agree"), 114),
        Variant("v1v2_either_into_v3", "crash_guard", _dual_params("either"), 114),
    ]


def _windows() -> list[Window]:
    return [
        Window("2026_ytd", "2026-01-01", "2026-05-03"),
        Window("2025", "2025-01-01", "2026-01-01"),
        Window("2024_2025_continuous", "2024-01-01", "2026-01-01"),
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


def _apply_v3_settings(settings, margin_usd: float) -> None:
    settings.bot.sizing.margin_usd = margin_usd
    settings.bot.sizing.leverage = 10
    settings.bot.offsets.tp_offset_bps = 100
    settings.bot.risk.max_notional_account_usd = 20_000
    settings.bot.risk.max_notional_per_symbol_usd = 4_560
    settings.bot.risk.daily_loss_limit_usd = 5_000


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
        for variant in _variants():
            label = f"{variant.name}_{window.name}"
            print(f"running {label}", flush=True)
            settings = copy.deepcopy(base_settings)
            _apply_v3_settings(settings, variant.margin_usd)
            signal = build_signal(variant.signal_name, dict(variant.signal_params))
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
                    "variant": variant.name,
                    "window": window.name,
                    "start": window.start,
                    "end": window.end,
                    "margin_usd": variant.margin_usd,
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
    csv_path = logs_dir / "v1_v2_into_v3_backtest_matrix.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    def fmt(r: dict) -> str:
        return (
            f"| {r['variant']} | {r['window']} | {float(r['net_pnl']):,.2f} | "
            f"{float(r['roi_pct']):.2f}% | {float(r['max_dd_pct']):.2f}% | "
            f"{int(r['trades'])} | {float(r['win_rate_pct']):.2f}% | "
            f"{int(r['open_symbols'])} |"
        )

    by_window = {w.name: [r for r in rows if r["window"] == w.name] for w in _windows()}
    md = [
        "# V1/V2 Into V3 Backtest Matrix",
        "",
        "- V3 framework: crash guard, account cap 20,000, per-symbol cap 4,560, TP 100 bps.",
        "- `v1_into_v3`: v1 signal and v1 sizing under v3 protection.",
        "- `v2_into_v3`: v2 signal and v2 sizing under v3 protection.",
        "- `v1v2_agree_into_v3`: both v1 and v2 must signal same direction.",
        "- `v1v2_either_into_v3`: either v1 or v2 can signal; conflicts are ignored.",
        f"- Raw CSV: `{csv_path}`",
        "",
    ]
    for window_name, window_rows in by_window.items():
        ranked = sorted(window_rows, key=lambda r: (-float(r["roi_pct"]), float(r["max_dd_pct"])))
        md.extend(
            [
                f"## {window_name}",
                "",
                "| Variant | Window | Net PnL | ROI | Max DD % | Trades | Win rate | Open symbols |",
                "|---|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        md.extend(fmt(r) for r in ranked)
        md.append("")

    continuous_rows = by_window["2024_2025_continuous"]
    best_cont = min(continuous_rows, key=lambda r: (float(r["max_dd_pct"]), -float(r["roi_pct"])))
    best_2026 = max(by_window["2026_ytd"], key=lambda r: float(r["roi_pct"]))
    md.extend(
        [
            "## Read",
            "",
            f"Best 2026 YTD profit: `{best_2026['variant']}`.",
            f"Lowest continuous 2024-2025 DD: `{best_cont['variant']}`.",
            "",
            "A combined v1+v2 signal is only useful if it improves the continuous drawdown problem without destroying 2026 profit.",
        ]
    )
    report_path = reports_dir / "v1_v2_into_v3_backtest_matrix.md"
    report_path.write_text("\n".join(md) + "\n")
    print(f"wrote {csv_path}")
    print(f"wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
