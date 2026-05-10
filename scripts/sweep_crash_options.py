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
from bot.config import SymbolOverride, load_settings
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

V1_SIGNAL = {
    "inner": "grid",
    "inner_anchor_period": 200,
    "inner_entry_bps": 30,
    "inner_step_bps": 15,
    "max_trend_bps": 30,
}
V2_SIGNAL = {
    "inner": "grid",
    "inner_anchor_period": 100,
    "inner_entry_bps": 30,
    "inner_step_bps": 15,
    "max_trend_bps": 15,
}


@dataclass(frozen=True)
class StrategyCase:
    name: str
    signal_name: str
    signal_params: dict
    margin_usd: float


@dataclass(frozen=True)
class RiskCase:
    name: str
    account_cap: float
    default_symbol_cap: float
    overrides: dict[str, float]


def _parse_iso_to_ms(s: str) -> int:
    dt = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _strategies() -> list[StrategyCase]:
    return [
        StrategyCase("v1", "trend_filter", dict(V1_SIGNAL), 66),
        StrategyCase("v2", "trend_filter", dict(V2_SIGNAL), 114),
        StrategyCase(
            "v2_crash_guard",
            "crash_guard",
            {
                "inner": "trend_filter",
                "inner_inner": "grid",
                "inner_inner_anchor_period": 100,
                "inner_inner_entry_bps": 30,
                "inner_inner_step_bps": 15,
                "inner_max_trend_bps": 15,
                "btc_ema_period": 200,
                "btc_return_bars": 1440,
                "btc_drop_bps": 500,
            },
            114,
        ),
    ]


def _risk_cases() -> list[RiskCase]:
    return [
        RiskCase("cap50_global10", 50_000, 10_000, {"HYPEUSDT": 300}),
        RiskCase("cap30_global6", 30_000, 6_000, {"HYPEUSDT": 300}),
        RiskCase("cap20_global4560", 20_000, 4_560, {"HYPEUSDT": 300}),
        RiskCase("cap15_global3420", 15_000, 3_420, {"HYPEUSDT": 300}),
        RiskCase("cap12500_global2280", 12_500, 2_280, {"HYPEUSDT": 300}),
        RiskCase(
            "cap15_balanced",
            15_000,
            2_280,
            {"BTCUSDT": 3_420, "ETHUSDT": 3_420, "HYPEUSDT": 300},
        ),
        RiskCase(
            "cap20_balanced",
            20_000,
            2_280,
            {"BTCUSDT": 4_560, "ETHUSDT": 4_560, "HYPEUSDT": 300},
        ),
    ]


def _apply_strategy(settings, strategy: StrategyCase) -> None:
    settings.bot.offsets.tp_offset_bps = 100
    settings.bot.sizing.margin_usd = strategy.margin_usd
    settings.bot.sizing.leverage = 10
    settings.bot.risk.daily_loss_limit_usd = 5_000
    settings.bot.risk.max_consecutive_losses = 5
    settings.bot.risk.cooldown_minutes = 60


def _apply_risk(settings, risk_case: RiskCase) -> None:
    settings.bot.risk.max_notional_account_usd = risk_case.account_cap
    settings.bot.risk.max_notional_per_symbol_usd = risk_case.default_symbol_cap
    settings.symbols.overrides.clear()
    for symbol, cap in risk_case.overrides.items():
        settings.symbols.overrides[symbol] = SymbolOverride(max_notional_per_symbol_usd=cap)


def _last_closes(candles: dict[str, list]) -> dict[str, float]:
    return {symbol: rows[-1].close for symbol, rows in candles.items() if rows}


def _open_rows(result, marks: dict[str, float]) -> list[dict]:
    rows = []
    for symbol, ctx in result.final_state.items():
        if ctx.position_size <= 0 or ctx.bep <= 0 or ctx.direction is None:
            continue
        mark = marks.get(symbol, ctx.bep)
        if ctx.direction.value == "LONG":
            pnl = (mark - ctx.bep) * ctx.position_size
        else:
            pnl = (ctx.bep - mark) * ctx.position_size
        rows.append(
            {
                "symbol": symbol,
                "direction": ctx.direction.value,
                "qty": ctx.position_size,
                "bep": ctx.bep,
                "mark": mark,
                "entry_notional": ctx.position_size * ctx.bep,
                "mark_notional": ctx.position_size * mark,
                "unrealized": pnl,
            }
        )
    return rows


def _stress(result, marks: dict[str, float], *, initial_equity: float, btc_target: float) -> dict[str, float]:
    rows = _open_rows(result, marks)
    current_unrealized = sum(r["unrealized"] for r in rows)
    realized = result.net_pnl
    btc_last = marks["BTCUSDT"]
    ratio = btc_target / btc_last
    market_unrealized = 0.0
    btc_only_unrealized = 0.0
    for r in rows:
        mark = r["mark"]
        if r["symbol"] == "BTCUSDT":
            btc_mark = btc_target
            market_mark = btc_target
        elif r["symbol"] == "XAUTUSDT":
            btc_mark = mark
            market_mark = mark
        else:
            btc_mark = mark
            market_mark = mark * ratio
        if r["direction"] == "LONG":
            btc_only_unrealized += (btc_mark - r["bep"]) * r["qty"]
            market_unrealized += (market_mark - r["bep"]) * r["qty"]
        else:
            btc_only_unrealized += (r["bep"] - btc_mark) * r["qty"]
            market_unrealized += (r["bep"] - market_mark) * r["qty"]
    open_entry = sum(r["entry_notional"] for r in rows)
    return {
        "open_symbols": len(rows),
        "open_entry_notional": open_entry,
        "current_unrealized": current_unrealized,
        "current_equity": initial_equity + realized + current_unrealized,
        "btc48_equity": initial_equity + realized + btc_only_unrealized,
        "market48_equity": initial_equity + realized + market_unrealized,
        "market48_loss_from_initial_pct": (initial_equity - (initial_equity + realized + market_unrealized)) / initial_equity * 100.0,
    }


def _format_pct(v: float) -> str:
    return f"{v:.2f}%"


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2026-01-01")
    parser.add_argument("--end", default="2026-05-02")
    parser.add_argument("--initial-equity", type=float, default=30_000)
    parser.add_argument("--btc-target", type=float, default=48_000)
    args = parser.parse_args()

    configure_logging("WARNING")
    base_settings = load_settings()
    start_ms = _parse_iso_to_ms(args.start)
    end_ms = _parse_iso_to_ms(args.end)
    candles: dict[str, list] = {}
    for symbol in SYMBOLS:
        df = await asyncio.to_thread(load_or_fetch, symbol, start_ms, end_ms, "data/klines")
        if not df.empty:
            candles[symbol] = df_to_candles(df, symbol)
    marks = _last_closes(candles)

    rows = []
    for strategy in _strategies():
        for risk_case in _risk_cases():
            settings = copy.deepcopy(base_settings)
            _apply_strategy(settings, strategy)
            _apply_risk(settings, risk_case)
            signal = build_signal(strategy.signal_name, dict(strategy.signal_params))
            risk = RiskManager(settings=settings, state_dir=Path("data/state"))
            label = f"{strategy.name}_{risk_case.name}"
            print(f"running {label}", flush=True)
            result = await run_backtest(
                settings,
                candles,
                signal,
                risk=risk,
                initial_equity=args.initial_equity,
            )
            stress = _stress(result, marks, initial_equity=args.initial_equity, btc_target=args.btc_target)
            roi = result.net_pnl / args.initial_equity * 100.0
            cap60_loss = risk_case.account_cap * 0.60
            cap80_loss = risk_case.account_cap * 0.80
            rows.append(
                {
                    "case": label,
                    "strategy": strategy.name,
                    "risk_case": risk_case.name,
                    "account_cap": risk_case.account_cap,
                    "symbol_cap": risk_case.default_symbol_cap,
                    "net_pnl": result.net_pnl,
                    "roi_pct": roi,
                    "trades": len(result.trades),
                    "win_rate_pct": result.win_rate * 100.0,
                    "max_dd": result.max_drawdown,
                    "max_dd_pct": result.max_drawdown_pct * 100.0,
                    "open_symbols": stress["open_symbols"],
                    "open_entry_notional": stress["open_entry_notional"],
                    "current_equity": stress["current_equity"],
                    "btc48_equity": stress["btc48_equity"],
                    "market48_equity": stress["market48_equity"],
                    "market48_loss_from_initial_pct": stress["market48_loss_from_initial_pct"],
                    "cap60_loss": cap60_loss,
                    "cap80_loss": cap80_loss,
                    "target_6pct": "yes" if roi >= 6.0 else "no",
                    "cap60_under_30pct_equity": "yes" if cap60_loss <= args.initial_equity * 0.30 else "no",
                }
            )

    logs_dir = Path("logs")
    reports_dir = Path("reports")
    logs_dir.mkdir(exist_ok=True)
    reports_dir.mkdir(exist_ok=True)
    csv_path = logs_dir / "crash_option_sweep_2026_ytd.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    viable = [
        r for r in rows
        if r["target_6pct"] == "yes" and r["cap60_under_30pct_equity"] == "yes"
    ]
    if viable:
        best = sorted(viable, key=lambda r: (-float(r["roi_pct"]), float(r["max_dd_pct"])))[0]
    else:
        best = sorted(rows, key=lambda r: (-float(r["roi_pct"]), float(r["cap60_loss"])))[0]
    by_roi = sorted(rows, key=lambda r: -float(r["roi_pct"]))
    by_safety = sorted(rows, key=lambda r: (float(r["cap60_loss"]), -float(r["roi_pct"])))

    def fmt(r) -> str:
        return (
            f"| {r['case']} | {float(r['net_pnl']):,.2f} | {_format_pct(float(r['roi_pct']))} | "
            f"{_format_pct(float(r['max_dd_pct']))} | {float(r['account_cap']):,.0f} | "
            f"{float(r['cap60_loss']):,.0f} | {float(r['market48_equity']):,.2f} | "
            f"{int(r['open_symbols'])} | {int(r['trades'])} | {_format_pct(float(r['win_rate_pct']))} | "
            f"{r['target_6pct']} | {r['cap60_under_30pct_equity']} |"
        )

    md = [
        "# Crash Option Sweep - 2026 YTD",
        "",
        f"- Date range: `{args.start}` to `{args.end}`",
        f"- Initial equity: `{args.initial_equity:,.0f} USDT`",
        f"- BTC stress target: `{args.btc_target:,.0f}`",
        f"- Raw CSV: `{csv_path}`",
        "",
        "## V1 vs V2 Check",
        "",
        "They are **not the same**, so they should not be combined.",
        "",
        "| Version | Signal | Margin/order | Status |",
        "|---|---|---:|---|",
        "| v1 | `trend_filter(grid anchor=200, max_trend=30)` | 66 | Historical 2025 setup |",
        "| v2 | `trend_filter(grid anchor=100, max_trend=15)` | 114 | Current baseline |",
        "| v2_crash_guard | v2 wrapped with BTC crash long-blocker | 114 | Experimental |",
        "",
        "## Best Candidate",
        "",
        "Chosen by: reaches 6% YTD ROI target and keeps a 60% full-cap crash loss under 30% of equity.",
        "",
        "| Case | Net PnL | ROI | Max DD | Account cap | 60% cap loss | Market BTC48 equity | Open syms | Trades | Win rate | Target? | Safe cap? |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        fmt(best),
        "",
        "## Highest ROI",
        "",
        "| Case | Net PnL | ROI | Max DD | Account cap | 60% cap loss | Market BTC48 equity | Open syms | Trades | Win rate | Target? | Safe cap? |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    md.extend(fmt(r) for r in by_roi[:10])
    md.extend(
        [
            "",
            "## Safest Caps",
            "",
            "| Case | Net PnL | ROI | Max DD | Account cap | 60% cap loss | Market BTC48 equity | Open syms | Trades | Win rate | Target? | Safe cap? |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    md.extend(fmt(r) for r in by_safety[:10])
    md.extend(
        [
            "",
            "## All Cases",
            "",
            "| Case | Net PnL | ROI | Max DD | Account cap | 60% cap loss | Market BTC48 equity | Open syms | Trades | Win rate | Target? | Safe cap? |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    md.extend(fmt(r) for r in rows)
    report_path = reports_dir / "crash_option_sweep_2026_ytd.md"
    report_path.write_text("\n".join(md) + "\n")

    print(f"wrote {csv_path}")
    print(f"wrote {report_path}")
    print(f"best={best['case']} roi={float(best['roi_pct']):.2f}% cap={float(best['account_cap']):.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
