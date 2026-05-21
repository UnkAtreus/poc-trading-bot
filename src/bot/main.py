"""CLI entry: `python -m bot.main {backtest|run} ...`."""

from __future__ import annotations

import argparse
import asyncio
import copy
import csv
import signal as posix_signal
import sys
from datetime import datetime, timezone
from pathlib import Path

from bot.config import Mode, load_settings
from bot.logger import configure as configure_logging, get_logger
from bot.persistence.store import StateStore
from bot.risk.manager import RiskManager
from bot.signals.base import build as build_signal
from bot.signals.labels import signal_full_label, signal_short_label


def _parse_iso_to_ms(s: str) -> int:
    # Accepts YYYY-MM-DD or full ISO.
    try:
        if len(s) == 10:
            dt = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(s).astimezone(timezone.utc)
    except Exception as e:
        raise SystemExit(f"bad date '{s}': {e}")
    return int(dt.timestamp() * 1000)


async def _load_candles_by_symbol(args, settings, *, log_event: str) -> dict[str, list]:
    """Load cached/fetched kline data for all requested symbols."""
    from bot.backtest.downloader import df_to_candles, load_or_fetch

    log = get_logger(__name__)
    syms = [s.strip() for s in args.symbols.split(",") if s.strip()] if args.symbols else settings.symbols.active
    start_ms = _parse_iso_to_ms(args.start)
    end_ms = _parse_iso_to_ms(args.end)
    workers = max(1, min(args.kline_workers, len(syms)))
    sem = asyncio.Semaphore(workers)

    async def load_one(sym: str):
        async with sem:
            log.info(log_event, symbol=sym)
            df = await asyncio.to_thread(
                load_or_fetch, sym, start_ms, end_ms, "data/klines"
            )
            if df.empty:
                empty_event = f"{log_event.rsplit('.', 1)[0]}.empty_klines"
                log.warning(empty_event, symbol=sym)
                return None
            return sym, df_to_candles(df, sym)

    loaded = await asyncio.gather(*(load_one(sym) for sym in syms))
    return dict(item for item in loaded if item is not None)


async def _cmd_backtest(args, settings) -> int:
    from bot.backtest.archive import archive_backtest_result
    from bot.backtest.monthly import by_month, render_monthly
    from bot.backtest.report import render
    from bot.backtest.runner import run_backtest

    log = get_logger(__name__)
    _apply_cli_overrides(args, settings)
    candles = await _load_candles_by_symbol(args, settings, log_event="backtest.loading")
    if not candles:
        log.error("backtest.no_data")
        return 1

    # Optional signal override via CLI (e.g. --signal "bollinger_bands:period=30:num_std=2.5")
    if args.signal:
        specs = _parse_signal_specs(args.signal)
        if len(specs) != 1:
            raise SystemExit("--signal accepts exactly one engine")
        sig_name, sig_params = specs[0]
    else:
        sig_name = settings.bot.signal.engine
        sig_params = dict(settings.bot.signal.params)

    sig = build_signal(sig_name, sig_params)

    risk = None
    if args.with_risk:
        risk = RiskManager(settings=settings, state_dir=Path("data/state"))

    initial_equity = _initial_equity_from_args(args, settings)
    result = await run_backtest(
        settings, candles, sig, risk=risk, initial_equity=initial_equity,
        stops=_stop_config_from_args(args),
        execution=_execution_config_from_args(args),
    )
    print(render(result))
    if args.by_month:
        print()
        print(render_monthly(by_month(result), initial_equity=initial_equity))
    try:
        archive_path = archive_backtest_result(
            kind="cli_backtest",
            settings=settings,
            start=args.start,
            end=args.end,
            symbols=sorted(candles.keys()),
            signal_name=sig_name,
            signal_params=sig_params,
            initial_equity=initial_equity,
            result=result,
            stops=_stop_config_from_args(args),
            risk_enabled=args.with_risk,
            args=vars(args),
            include_events=True,
        )
        print()
        print(f"archive        : {archive_path}")
    except Exception as exc:
        print()
        print(f"archive warning: {type(exc).__name__}: {exc}")
    return 0


def _parse_signal_specs(spec: str) -> list[tuple[str, dict]]:
    """Parse a comma-separated list of `name[:k=v[:k=v]]` into (name, params) tuples.

    Examples:
        "bollinger_bands"
        "bollinger_bands:period=20:num_std=2.0"
        "bollinger_bands,zscore:period=50:threshold=2"
    """
    out: list[tuple[str, dict]] = []
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        parts = token.split(":")
        name = parts[0]
        params: dict[str, float | int | str | bool] = {}
        for kv in parts[1:]:
            if "=" not in kv:
                raise SystemExit(f"bad signal param '{kv}' in '{token}' — expected k=v")
            k, v = kv.split("=", 1)
            params[k.strip()] = _coerce(v.strip())
        out.append((name, params))
    return out


def _coerce(v: str):
    for caster in (int, float):
        try:
            return caster(v)
        except ValueError:
            continue
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    return v


def _initial_equity_from_args(args, settings) -> float:
    value = getattr(args, "initial_equity", None)
    return settings.bot.account.initial_equity if value is None else value


async def _cmd_compare(args, settings) -> int:
    """Run several signals on the same historical klines and print a comparison."""
    from bot.backtest.monthly import by_month, render_monthly
    from bot.backtest.runner import run_backtest

    log = get_logger(__name__)
    _apply_cli_overrides(args, settings)
    specs = _parse_signal_specs(args.signals)
    if not specs:
        log.error("compare.no_signals")
        return 1

    candles = await _load_candles_by_symbol(args, settings, log_event="compare.loading")
    if not candles:
        log.error("compare.no_data")
        return 1

    rows: list[tuple[str, dict, "BacktestResult"]] = []
    for name, params in specs:
        log.info("compare.running", signal=name, params=params)
        sig = build_signal(name, dict(params))
        risk = RiskManager(settings=settings, state_dir=Path("data/state")) if args.with_risk else None
        result = await run_backtest(
            settings, candles, sig, risk=risk, initial_equity=_initial_equity_from_args(args, settings),
            stops=_stop_config_from_args(args),
        )
        rows.append((name, params, result))

    initial_equity = _initial_equity_from_args(args, settings)
    print(_render_compare(rows, candles, initial_equity=initial_equity))
    if args.by_month:
        # Print monthly breakdown for each signal in order they were given.
        print()
        for name, params, result in rows:
            label = name + (f"({','.join(f'{k}={v}' for k,v in params.items())})" if params else "")
            print(f"\n>>> {label}")
            print(render_monthly(by_month(result), initial_equity=initial_equity))
    return 0


def _render_compare(rows, candles, *, initial_equity: float = 0.0) -> str:
    """Side-by-side comparison table for backtest results."""
    bars = sum(len(v) for v in candles.values())
    syms = ",".join(sorted(candles.keys()))
    lines: list[str] = []
    width = 148 if initial_equity > 0 else 132
    lines.append("=" * width)
    lines.append(f"COMPARE — {syms} — {bars} 1m bars total")
    lines.append("=" * width)
    if initial_equity > 0:
        lines.append(f"{'signal':<28}{'trades':>8}{'win%':>7}{'gross':>12}"
                     f"{'fees':>10}{'net':>12}{'roi%':>8}{'maxDD':>12}{'dd%':>8}"
                     f"{'liq':>6}{'near':>7}{'minLiq%':>9}{'open$':>10}{'open?':>9}")
    else:
        lines.append(f"{'signal':<28}{'trades':>8}{'win%':>7}{'gross':>12}"
                     f"{'fees':>10}{'net':>12}{'maxDD':>12}"
                     f"{'liq':>6}{'near':>7}{'minLiq%':>9}{'open$':>10}{'open?':>9}")
    lines.append("-" * width)
    rows_sorted = sorted(rows, key=lambda r: -r[2].net_pnl)
    for name, params, result in rows_sorted:
        n = len(result.trades)
        wr = result.win_rate * 100 if n else 0.0
        open_count = sum(
            1 for ctx in result.final_state.values()
            if ctx.state.value != "IDLE" and ctx.position_size > 0
        )
        label = name
        if params:
            kv = ",".join(f"{k}={v}" for k, v in params.items())
            label = f"{name}({kv})"
            if len(label) > 28:
                label = label[:25] + "..."
        if initial_equity > 0:
            roi = result.net_pnl / initial_equity * 100.0
            lines.append(
                f"{label:<28}{n:>8}{wr:>6.1f}%{result.total_pnl:>12.2f}"
                f"{result.total_fees:>10.2f}{result.net_pnl:>12.2f}{roi:>8.2f}"
                f"{result.max_drawdown:>12.2f}{result.max_drawdown_pct * 100:>8.2f}"
                f"{str(result.liquidated):>6}{str(result.near_liquidation):>7}"
                f"{result.min_liq_distance_pct:>9.2f}{result.final_open_exposure:>10.2f}{open_count:>9}"
            )
        else:
            lines.append(
                f"{label:<28}{n:>8}{wr:>6.1f}%{result.total_pnl:>12.2f}"
                f"{result.total_fees:>10.2f}{result.net_pnl:>12.2f}"
                f"{result.max_drawdown:>12.2f}{str(result.liquidated):>6}"
                f"{str(result.near_liquidation):>7}{result.min_liq_distance_pct:>9.2f}"
                f"{result.final_open_exposure:>10.2f}{open_count:>9}"
            )
    lines.append("")
    lines.append("Notes:")
    lines.append("  • 'fees' negative = maker rebate. 'net' = gross − fees.")
    lines.append("  • 'liq'/'near' are hard safety gates from the liquidation-risk model.")
    lines.append("  • 'open?' = symbols still in a non-IDLE state at end-of-run.")
    lines.append("    Higher numbers mean more unrealized exposure left over;")
    lines.append("    a winning strategy keeps this near 0.")
    lines.append("  • 'maxDD' is mark-to-market drawdown using candle closes;")
    lines.append("    it is not liquidation modeling.")
    lines.append("  • The merge-at-BEP recovery means trend signals (e.g. ema_crossover)")
    lines.append("    typically lose vs. mean-reversion signals on this architecture.")
    return "\n".join(lines)


async def _cmd_compare_execution(args, settings) -> int:
    """Compare naive fills against realistic execution penalties."""
    from bot.backtest.archive import archive_record, result_summary, settings_snapshot
    from bot.backtest.runner import run_backtest

    log = get_logger(__name__)
    _apply_cli_overrides(args, settings)
    sig_name, sig_params = _single_signal_from_args(args, settings)
    candles = await _load_candles_by_symbol(args, settings, log_event="compare_execution.loading")
    if not candles:
        log.error("compare_execution.no_data")
        return 1

    initial_equity = _initial_equity_from_args(args, settings)
    range_days = max((_parse_iso_to_ms(args.end) - _parse_iso_to_ms(args.start)) / 86_400_000.0, 1e-9)
    from bot.backtest.execution import EXECUTION_PROFILE_LATENCIES

    profile = _execution_profile_from_args(args)
    latency_spec = args.latencies or EXECUTION_PROFILE_LATENCIES[profile]
    scenarios = [_execution_config_from_args(args, force_model="naive")]
    scenarios.extend(
        _execution_config_from_args(args, force_model="realistic", latency_seconds=latency)
        for latency in _parse_float_list(latency_spec)
    )

    rows: list[dict] = []
    detailed: dict[str, dict] = {}
    for cfg in scenarios:
        label = _execution_label(cfg)
        log.info("compare_execution.running", execution=label)
        sig = build_signal(sig_name, dict(sig_params))
        risk = RiskManager(settings=settings, state_dir=Path("data/state")) if args.with_risk else None
        result = await run_backtest(
            settings,
            candles,
            sig,
            risk=risk,
            initial_equity=initial_equity,
            stops=_stop_config_from_args(args),
            execution=cfg,
        )
        rows.append(_execution_result_row(label, cfg, result, initial_equity, range_days, args))
        detailed[label] = result_summary(result, initial_equity=initial_equity, include_events=False)

    _add_naive_penalties(rows)
    csv_path = Path(args.output_csv)
    report_path = Path(args.output_report)
    _write_compare_execution_csv(csv_path, rows)
    report = _render_compare_execution_report(rows, args, settings, csv_path, sig_name, sig_params)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    try:
        archive_path = archive_record(
            {
                "kind": "compare_execution_models",
                "label": args.label,
                "scope": {
                    "start": args.start,
                    "end": args.end,
                    "symbols": sorted(candles.keys()),
                },
                "strategy": {
                    "signal_name": sig_name,
                    "signal_params": dict(sig_params),
                    "risk_enabled": args.with_risk,
                    "stops": _stop_config_from_args(args),
                },
                "settings": settings_snapshot(settings),
                "args": vars(args),
                "outputs": {"csv_path": str(csv_path), "report_path": str(report_path)},
                "summary": {
                    "signal_short": signal_short_label(sig_name, sig_params),
                    "signal_full": _format_signal_spec(sig_name, sig_params),
                    "target_min_annual_roi_pct": args.min_annual_roi_pct,
                    "target_max_annual_roi_pct": args.max_annual_roi_pct,
                    "rows": rows,
                },
                "metrics": _archive_metrics_from_execution_rows(rows, initial_equity),
                "extra": {"execution_results": detailed},
            }
        )
        print(report)
        print()
        print(f"csv            : {csv_path}")
        print(f"report         : {report_path}")
        print(f"archive        : {archive_path}")
    except Exception as exc:
        print(report)
        print()
        print(f"csv            : {csv_path}")
        print(f"report         : {report_path}")
        print(f"archive warning: {type(exc).__name__}: {exc}")
    return 0


def _execution_label(cfg) -> str:
    if cfg.mode == "realistic":
        return f"realistic_{cfg.latency_seconds:g}s"
    return "naive"


def _execution_result_row(label: str, cfg, result, initial_equity: float, range_days: float, args) -> dict:
    roi_pct = result.net_pnl / initial_equity * 100.0 if initial_equity > 0 else 0.0
    annualized_roi_pct = roi_pct * (365.0 / range_days)
    stats = result.execution_stats
    return {
        "label": label,
        "mode": cfg.mode,
        "latency_seconds": cfg.latency_seconds,
        "cancel_delay_seconds": cfg.cancel_delay_seconds,
        "slippage_bps": cfg.slippage_bps,
        "pass_through_bps": cfg.pass_through_bps,
        "full_fill_bps": cfg.full_fill_bps,
        "min_partial_fill_pct": cfg.min_partial_fill_pct,
        "trades": len(result.trades),
        "wins": result.wins,
        "losses": result.losses,
        "win_rate_pct": result.win_rate * 100.0,
        "gross_pnl": result.total_pnl,
        "fees": result.total_fees,
        "net_pnl": result.net_pnl,
        "roi_pct": roi_pct,
        "annualized_roi_pct": annualized_roi_pct,
        "target_min_pass": annualized_roi_pct >= args.min_annual_roi_pct,
        "target_band_pass": args.min_annual_roi_pct <= annualized_roi_pct <= args.max_annual_roi_pct,
        "max_drawdown": result.max_drawdown,
        "max_drawdown_pct": result.max_drawdown_pct * 100.0,
        "liquidated": result.liquidated,
        "near_liquidation": result.near_liquidation,
        "final_open_exposure": result.final_open_exposure,
        "placed_orders": stats.placed_orders,
        "accepted_orders": stats.accepted_orders,
        "rejected_orders": stats.rejected_orders,
        "partial_fills": stats.partial_fills,
        "full_fills": stats.full_fills,
        "cancel_requested": stats.cancel_requested,
        "cancel_effective": stats.cancel_effective,
        "cancel_race_fills": stats.cancel_race_fills,
        "dust_rejected": stats.dust_rejected,
        "slippage_cost": stats.slippage_cost,
        "penalty_net_pnl_vs_naive": 0.0,
        "penalty_roi_pct_vs_naive": 0.0,
    }


def _add_naive_penalties(rows: list[dict]) -> None:
    if not rows:
        return
    naive = rows[0]
    for row in rows:
        row["penalty_net_pnl_vs_naive"] = row["net_pnl"] - naive["net_pnl"]
        row["penalty_roi_pct_vs_naive"] = row["roi_pct"] - naive["roi_pct"]


def _write_compare_execution_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _render_compare_execution_report(
    rows: list[dict],
    args,
    settings,
    csv_path: Path,
    signal_name: str,
    signal_params: dict,
) -> str:
    from bot.backtest.execution import EXECUTION_PROFILE_LATENCIES

    signal_full = _format_signal_spec(signal_name, signal_params)
    signal_short = signal_short_label(signal_name, signal_params)
    profile = _execution_profile_from_args(args)
    latency_spec = args.latencies or EXECUTION_PROFILE_LATENCIES[profile]
    realistic_cfg = _execution_config_from_args(args, force_model="realistic")
    lines = [
        "# Execution Model Comparison",
        "",
        f"- Range: `{args.start}` to `{args.end}`",
        f"- Signal: `{signal_short}`",
        f"- Full signal: `{signal_full}`",
        f"- Execution profile: `{profile}`",
        f"- Realistic latencies: `{latency_spec}` seconds",
        f"- Realistic penalties: cancel `{realistic_cfg.cancel_delay_seconds:g}`s, "
        f"slippage `{realistic_cfg.slippage_bps:g}` bps, "
        f"pass-through `{realistic_cfg.pass_through_bps:g}` bps, "
        f"full-fill `{realistic_cfg.full_fill_bps:g}` bps, "
        f"min partial `{realistic_cfg.min_partial_fill_pct:g}`%",
        f"- Initial equity: `{_initial_equity_from_args(args, settings):,.2f}` USDT",
        f"- Target: `{args.min_annual_roi_pct:g}-{args.max_annual_roi_pct:g}%` annualized ROI",
        f"- Raw CSV: `{csv_path}`",
        "",
        "| Model | Net PnL | ROI | Annual ROI | Max DD | Trades | Win % | Rejected | Partial | Cancel race | Dust | Slip cost | Vs naive | Target >= min |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['label']} | {row['net_pnl']:,.2f} | {row['roi_pct']:.2f}% | "
            f"{row['annualized_roi_pct']:.2f}% | {row['max_drawdown_pct']:.2f}% | "
            f"{int(row['trades'])} | {row['win_rate_pct']:.2f}% | "
            f"{int(row['rejected_orders'])} | {int(row['partial_fills'])} | "
            f"{int(row['cancel_race_fills'])} | {int(row['dust_rejected'])} | "
            f"{row['slippage_cost']:,.4f} | {row['penalty_roi_pct_vs_naive']:+.2f}% | "
            f"{'yes' if row['target_min_pass'] else 'no'} |"
        )
    lines.extend(
        [
            "",
            "## Read",
            "",
            "- Realistic rows are candle-only execution proxies, not order-book replay.",
            "- If realistic rows lose most of naive PnL, the old backtest was likely execution-sensitive.",
            "- A strategy is interesting only if realistic rows still clear the target with acceptable drawdown and low dust/rejection counts.",
        ]
    )
    return "\n".join(lines)


def _archive_metrics_from_execution_rows(rows: list[dict], initial_equity: float) -> dict:
    realistic = [row for row in rows if row["mode"] == "realistic"]
    chosen = min(realistic or rows, key=lambda row: row["annualized_roi_pct"])
    return {
        "initial_equity": initial_equity,
        "trades": chosen["trades"],
        "win_rate_pct": chosen["win_rate_pct"],
        "net_pnl": chosen["net_pnl"],
        "roi_pct": chosen["roi_pct"],
        "max_drawdown_pct": chosen["max_drawdown_pct"],
        "liquidated": chosen["liquidated"],
        "near_liquidation": chosen["near_liquidation"],
        "final_open_exposure": chosen["final_open_exposure"],
        "annualized_roi_pct": chosen["annualized_roi_pct"],
        "target_min_pass": chosen["target_min_pass"],
    }


async def _cmd_classify_market(args, settings) -> int:
    from bot.backtest.regime import classify_market, render_regime

    candles = await _load_candles_by_symbol(args, settings, log_event="classify.loading")
    if not candles:
        get_logger(__name__).error("classify.no_data")
        return 1
    print(render_regime(classify_market(candles)))
    return 0


async def _cmd_stress(args, settings) -> int:
    from bot.backtest.stress import build_stress_scenarios
    from bot.backtest.runner import run_backtest

    _apply_cli_overrides(args, settings)
    candles = await _load_candles_by_symbol(args, settings, log_event="stress.loading")
    if not candles:
        get_logger(__name__).error("stress.no_data")
        return 1
    sig_name, sig_params = _single_signal_from_args(args, settings)
    shocks = _parse_float_list(args.shocks)
    initial_equity = _initial_equity_from_args(args, settings)

    rows = []
    scenarios = build_stress_scenarios(candles, shocks=tuple(shocks))
    for scenario in scenarios:
        scenario_settings = copy.deepcopy(settings)
        scenario_settings.bot.liquidation.funding_stress_bps = max(
            scenario_settings.bot.liquidation.funding_stress_bps,
            scenario.funding_stress_bps,
        )
        sig = build_signal(sig_name, dict(sig_params))
        risk = RiskManager(settings=scenario_settings, state_dir=Path("data/state")) if args.with_risk else None
        result = await run_backtest(
            scenario_settings,
            scenario.candles_by_symbol,
            sig,
            risk=risk,
            initial_equity=initial_equity,
            stops=_stop_config_from_args(args),
        )
        rows.append((scenario.name, result))

    print(_render_stress(rows, initial_equity=initial_equity))
    return 0


async def _cmd_optimize_lot_size(args, settings) -> int:
    from bot.backtest.runner import run_backtest

    base_settings = copy.deepcopy(settings)
    _apply_cli_overrides(args, base_settings)
    candles = await _load_candles_by_symbol(args, base_settings, log_event="optimize.loading")
    if not candles:
        get_logger(__name__).error("optimize.no_data")
        return 1
    sig_name, sig_params = _single_signal_from_args(args, base_settings)
    margins = _parse_float_list(args.margins)
    leverages = [int(v) for v in _parse_float_list(args.leverages)]
    account_caps = _parse_float_list(args.account_caps) if args.account_caps else [base_settings.bot.risk.max_notional_account_usd]
    symbol_caps = _parse_float_list(args.symbol_caps) if args.symbol_caps else [base_settings.bot.risk.max_notional_per_symbol_usd]
    initial_equity = _initial_equity_from_args(args, base_settings)

    rows = []
    for margin in margins:
        for leverage in leverages:
            for account_cap in account_caps:
                for symbol_cap in symbol_caps:
                    scenario_settings = copy.deepcopy(base_settings)
                    scenario_settings.bot.sizing.margin_usd = margin
                    scenario_settings.bot.sizing.leverage = leverage
                    scenario_settings.bot.risk.max_notional_account_usd = account_cap
                    scenario_settings.bot.risk.max_notional_per_symbol_usd = symbol_cap
                    sig = build_signal(sig_name, dict(sig_params))
                    risk = RiskManager(settings=scenario_settings, state_dir=Path("data/state")) if args.with_risk else None
                    result = await run_backtest(
                        scenario_settings,
                        candles,
                        sig,
                        risk=risk,
                        initial_equity=initial_equity,
                        stops=_stop_config_from_args(args),
                    )
                    rows.append((margin, leverage, account_cap, symbol_cap, result))

    print(_render_optimizer(rows, initial_equity=initial_equity, settings=base_settings))
    return 0


async def _cmd_select_strategy(args, settings) -> int:
    from bot.backtest.regime import classify_market
    from bot.backtest.runner import run_backtest

    _apply_cli_overrides(args, settings)
    specs = _parse_signal_specs(args.signals)
    candles = await _load_candles_by_symbol(args, settings, log_event="selector.loading")
    if not candles:
        get_logger(__name__).error("selector.no_data")
        return 1
    regime = classify_market(candles)
    initial_equity = _initial_equity_from_args(args, settings)
    candidates = []
    for name, params in specs:
        sig = build_signal(name, dict(params))
        risk = RiskManager(settings=settings, state_dir=Path("data/state")) if args.with_risk else None
        result = await run_backtest(
            settings,
            candles,
            sig,
            risk=risk,
            initial_equity=initial_equity,
            stops=_stop_config_from_args(args),
        )
        candidates.append((name, params, result))

    safe = [(n, p, r) for n, p, r in candidates if _passes_safety_gates(r, settings)]
    safe.sort(key=lambda row: (-row[2].net_pnl, row[2].max_drawdown, row[2].final_open_exposure))
    print(_render_strategy_selection(regime.label, safe[0] if safe else None, candidates, settings))
    return 0


async def _cmd_optimize_stability(args, settings) -> int:
    from bot.backtest.runner import run_backtest
    from bot.backtest.stability import StabilityGates, analyze_stability

    base_settings = copy.deepcopy(settings)
    _apply_cli_overrides(args, base_settings)
    candles = await _load_candles_by_symbol(args, base_settings, log_event="stability.loading")
    if not candles:
        get_logger(__name__).error("stability.no_data")
        return 1
    sig_name, sig_params = _single_signal_from_args(args, base_settings)
    margins = _parse_float_list(args.margins)
    leverages = [int(v) for v in _parse_float_list(args.leverages)]
    account_caps = _parse_float_list(args.account_caps) if args.account_caps else [base_settings.bot.risk.max_notional_account_usd]
    symbol_caps = _parse_float_list(args.symbol_caps) if args.symbol_caps else [base_settings.bot.risk.max_notional_per_symbol_usd]
    tp_offsets = _parse_float_list(args.tp_offsets) if args.tp_offsets else [base_settings.bot.offsets.tp_offset_bps]
    initial_equity = _initial_equity_from_args(args, base_settings)
    gates = StabilityGates(
        target_monthly_roi_pct=args.target_monthly_roi_pct,
        min_positive_month_pct=args.min_positive_month_pct,
        min_target_month_pct=args.min_target_month_pct,
        max_non_positive_stretch=args.max_non_positive_stretch,
        max_worst_monthly_dd_pct=args.max_worst_monthly_dd_pct,
    )

    rows = []
    for margin in margins:
        for leverage in leverages:
            for account_cap in account_caps:
                for symbol_cap in symbol_caps:
                    for tp_offset in tp_offsets:
                        scenario_settings = copy.deepcopy(base_settings)
                        scenario_settings.bot.sizing.margin_usd = margin
                        scenario_settings.bot.sizing.leverage = leverage
                        scenario_settings.bot.risk.max_notional_account_usd = account_cap
                        scenario_settings.bot.risk.max_notional_per_symbol_usd = symbol_cap
                        scenario_settings.bot.offsets.tp_offset_bps = tp_offset
                        sig = build_signal(sig_name, dict(sig_params))
                        risk = RiskManager(settings=scenario_settings, state_dir=Path("data/state")) if args.with_risk else None
                        result = await run_backtest(
                            scenario_settings,
                            candles,
                            sig,
                            risk=risk,
                            initial_equity=initial_equity,
                            stops=_stop_config_from_args(args),
                        )
                        stability = analyze_stability(result, gates=gates, initial_equity=initial_equity)
                        rows.append((margin, leverage, account_cap, symbol_cap, tp_offset, result, stability))

    print(_render_stability_optimizer(rows, initial_equity=initial_equity, settings=base_settings))
    return 0


def _single_signal_from_args(args, settings) -> tuple[str, dict]:
    if getattr(args, "signal", ""):
        specs = _parse_signal_specs(args.signal)
        if len(specs) != 1:
            raise SystemExit("--signal accepts exactly one engine")
        return specs[0]
    return settings.bot.signal.engine, dict(settings.bot.signal.params)


def _format_signal_spec(name: str, params: dict) -> str:
    return signal_full_label(name, params)


def _parse_float_list(raw: str) -> list[float]:
    vals = [float(x.strip()) for x in raw.split(",") if x.strip()]
    if not vals:
        raise SystemExit("expected a comma-separated list of numbers")
    return vals


def _passes_safety_gates(result, settings) -> bool:
    gates = settings.bot.optimizer.safety_gates
    if gates.reject_liquidated and result.liquidated:
        return False
    if gates.reject_near_liquidation and result.near_liquidation:
        return False
    if gates.max_drawdown_pct is not None and result.max_drawdown_pct * 100.0 > gates.max_drawdown_pct:
        return False
    if (
        gates.max_final_open_exposure_usd is not None
        and result.final_open_exposure > gates.max_final_open_exposure_usd
    ):
        return False
    return True


def _render_stress(rows, *, initial_equity: float) -> str:
    width = 134
    lines = ["=" * width, "STRESS RESULTS", "=" * width]
    lines.append(
        f"{'scenario':<36}{'trades':>8}{'net':>12}{'roi%':>8}{'maxDD':>12}{'liq':>6}"
        f"{'near':>7}{'minLiq%':>9}{'open$':>10}{'worstUnrl':>12}"
    )
    lines.append("-" * width)
    for label, result in rows:
        roi = result.net_pnl / initial_equity * 100.0 if initial_equity > 0 else 0.0
        lines.append(
            f"{label:<36}{len(result.trades):>8}{result.net_pnl:>12.2f}{roi:>8.2f}"
            f"{result.max_drawdown:>12.2f}{str(result.liquidated):>6}"
            f"{str(result.near_liquidation):>7}{result.min_liq_distance_pct:>9.2f}"
            f"{result.final_open_exposure:>10.2f}{result.worst_unrealized_loss:>12.2f}"
        )
    return "\n".join(lines)


def _render_optimizer(rows, *, initial_equity: float, settings) -> str:
    ranked = sorted(
        rows,
        key=lambda row: (
            not _passes_safety_gates(row[4], settings),
            -row[4].net_pnl,
            row[4].max_drawdown,
            row[4].final_open_exposure,
        ),
    )
    lines = ["=" * 148, "LOT SIZE OPTIMIZATION", "=" * 148]
    lines.append(
        f"{'margin':>8}{'lev':>5}{'acctCap':>10}{'symCap':>10}{'safe':>7}{'trades':>8}"
        f"{'net':>12}{'roi%':>8}{'maxDD':>12}{'liq':>6}{'near':>7}{'minLiq%':>9}{'open$':>10}"
    )
    lines.append("-" * 148)
    for margin, leverage, account_cap, symbol_cap, result in ranked:
        safe = _passes_safety_gates(result, settings)
        roi = result.net_pnl / initial_equity * 100.0 if initial_equity > 0 else 0.0
        lines.append(
            f"{margin:>8.2f}{leverage:>5}{account_cap:>10.0f}{symbol_cap:>10.0f}{str(safe):>7}"
            f"{len(result.trades):>8}{result.net_pnl:>12.2f}{roi:>8.2f}{result.max_drawdown:>12.2f}"
            f"{str(result.liquidated):>6}{str(result.near_liquidation):>7}"
            f"{result.min_liq_distance_pct:>9.2f}{result.final_open_exposure:>10.2f}"
        )
    return "\n".join(lines)


def _render_stability_optimizer(rows, *, initial_equity: float, settings) -> str:
    ranked = sorted(
        rows,
        key=lambda row: (
            not _passes_safety_gates(row[5], settings),
            not row[6].passes,
            -row[6].score,
            row[5].max_drawdown,
            row[0],
        ),
    )
    lines = ["=" * 176, "MONTHLY STABILITY OPTIMIZATION", "=" * 176]
    lines.append(
        f"{'margin':>8}{'lev':>5}{'acctCap':>10}{'symCap':>10}{'tpBps':>8}"
        f"{'safe':>7}{'stable':>8}{'score':>9}{'months':>7}{'pos%':>7}{'target%':>9}"
        f"{'avgROI':>8}{'medROI':>8}{'worstROI':>10}{'zeroStr':>8}{'worstDD%':>10}"
        f"{'net':>12}{'open$':>10}"
    )
    lines.append("-" * 176)
    for margin, leverage, account_cap, symbol_cap, tp_offset, result, stability in ranked:
        safe = _passes_safety_gates(result, settings)
        stable = safe and stability.passes
        lines.append(
            f"{margin:>8.2f}{leverage:>5}{account_cap:>10.0f}{symbol_cap:>10.0f}{tp_offset:>8.1f}"
            f"{str(safe):>7}{str(stable):>8}{stability.score:>9.2f}{stability.months:>7}"
            f"{stability.positive_month_pct:>7.1f}{stability.target_month_pct:>9.1f}"
            f"{stability.avg_monthly_roi_pct:>8.2f}{stability.median_monthly_roi_pct:>8.2f}"
            f"{stability.worst_monthly_roi_pct:>10.2f}{stability.longest_non_positive_stretch:>8}"
            f"{stability.worst_monthly_dd_pct:>10.2f}{result.net_pnl:>12.2f}"
            f"{result.final_open_exposure:>10.2f}"
        )
    lines.append("")
    lines.append("Notes:")
    lines.append("  • stable=True requires safety gates plus monthly stability gates.")
    lines.append("  • zeroStr is the longest run of months with net ROI <= 0.")
    lines.append("  • Ranking always rejects unsafe liquidation-risk candidates before stability score.")
    return "\n".join(lines)


def _render_strategy_selection(regime: str, selected, candidates, settings) -> str:
    lines = ["strategy_selector:", f"  regime: {regime}"]
    if selected is None:
        lines.append("  action: no_trade")
    else:
        name, params, result = selected
        lines.append(f"  action: trade")
        lines.append(f"  signal: {name}")
        lines.append(f"  params: {params}")
        lines.append(f"  net_pnl: {result.net_pnl:.2f}")
        lines.append(f"  max_drawdown: {result.max_drawdown:.2f}")
        lines.append(f"  min_liq_distance_pct: {result.min_liq_distance_pct:.2f}")
        lines.append(f"  final_open_exposure: {result.final_open_exposure:.2f}")
    rejected = [f"{n}({p})" for n, p, r in candidates if not _passes_safety_gates(r, settings)]
    if rejected:
        lines.append(f"  rejected_unsafe: {rejected}")
    return "\n".join(lines)


def _apply_cli_overrides(args, settings) -> None:
    if getattr(args, "tp_offset_bps", None) is not None:
        settings.bot.offsets.tp_offset_bps = args.tp_offset_bps
    if getattr(args, "margin_usd", None) is not None:
        settings.bot.sizing.margin_usd = args.margin_usd
    if getattr(args, "leverage", None) is not None:
        settings.bot.sizing.leverage = args.leverage
    if getattr(args, "max_notional_account", None) is not None:
        settings.bot.risk.max_notional_account_usd = args.max_notional_account
    if getattr(args, "max_notional_per_symbol", None) is not None:
        settings.bot.risk.max_notional_per_symbol_usd = args.max_notional_per_symbol
    if getattr(args, "daily_loss_limit", None) is not None:
        settings.bot.risk.daily_loss_limit_usd = args.daily_loss_limit


def _stop_config_from_args(args):
    from bot.backtest.runner import BacktestStopConfig

    max_hold_hours = getattr(args, "stop_max_hold_hours", None)
    max_hold_seconds = None if max_hold_hours is None else max_hold_hours * 3600.0
    cfg = BacktestStopConfig(
        bep_stop_bps=getattr(args, "stop_bep_bps", None),
        max_symbol_loss_usd=getattr(args, "stop_symbol_loss", None),
        account_dd_stop_pct=getattr(args, "stop_account_dd_pct", None),
        max_hold_seconds=max_hold_seconds,
        monthly_profit_lock_pct=getattr(args, "stop_monthly_profit_lock_pct", None),
        monthly_dd_stop_pct=getattr(args, "stop_monthly_dd_pct", None),
    )
    if (
        cfg.bep_stop_bps is None
        and cfg.max_symbol_loss_usd is None
        and cfg.account_dd_stop_pct is None
        and cfg.max_hold_seconds is None
        and cfg.monthly_profit_lock_pct is None
        and cfg.monthly_dd_stop_pct is None
    ):
        return None
    return cfg


def _execution_config_from_args(args, *, force_model: str | None = None, latency_seconds: float | None = None):
    from bot.backtest.execution import BacktestExecutionConfig

    model = force_model or getattr(args, "execution_model", "naive")
    if model == "naive":
        return BacktestExecutionConfig.naive()
    if model != "realistic":
        raise SystemExit(f"bad execution model: {model}")
    profile = _execution_profile_from_args(args)
    return BacktestExecutionConfig.from_profile(
        profile,
        latency_seconds=latency_seconds
        if latency_seconds is not None
        else getattr(args, "latency_seconds", None),
        cancel_delay_seconds=getattr(args, "cancel_delay_seconds", None),
        slippage_bps=getattr(args, "slippage_bps", None),
        pass_through_bps=getattr(args, "pass_through_bps", None),
        full_fill_bps=getattr(args, "full_fill_bps", None),
        min_partial_fill_pct=getattr(args, "min_partial_fill_pct", None),
    )


def _execution_profile_from_args(args) -> str:
    profile = getattr(args, "execution_profile", "conservative") or "conservative"
    if profile not in {"conservative", "mainnet-like"}:
        raise SystemExit(f"bad execution profile: {profile}")
    return profile


def _add_execution_args(parser: argparse.ArgumentParser, *, include_model: bool = True) -> None:
    if include_model:
        parser.add_argument(
            "--execution-model",
            choices=("naive", "realistic"),
            default="naive",
            help="Backtest execution model; naive preserves the legacy fill rules",
        )
    parser.add_argument("--execution-profile", choices=("conservative", "mainnet-like"), default="conservative",
                        help="Default realistic execution penalties; manual flags override this profile")
    parser.add_argument("--latency-seconds", type=float, default=None,
                        help="Override realistic order activation latency")
    parser.add_argument("--cancel-delay-seconds", type=float, default=None,
                        help="Override realistic cancel acknowledgement delay")
    parser.add_argument("--slippage-bps", type=float, default=None,
                        help="Override realistic adverse fill-price penalty")
    parser.add_argument("--pass-through-bps", type=float, default=None,
                        help="Override realistic minimum price pass-through required to fill")
    parser.add_argument("--full-fill-bps", type=float, default=None,
                        help="Override realistic pass-through required for a full fill")
    parser.add_argument("--min-partial-fill-pct", type=float, default=None,
                        help="Override realistic minimum partial fill percentage")


async def _cmd_run(args, settings) -> int:
    """Live run against testnet or mainnet."""
    from bot.exchange.bybit_live import BybitLive
    from bot.strategy.orchestrator import Orchestrator

    log = get_logger(__name__)
    if settings.env.mode is Mode.BACKTEST:
        log.error("run_requires_live_mode")
        return 1
    if not settings.env.bybit_api_key or not settings.env.bybit_api_secret:
        log.error("missing_api_credentials")
        return 1

    adapter = BybitLive(
        api_key=settings.env.bybit_api_key,
        api_secret=settings.env.bybit_api_secret,
        testnet=settings.env.mode is Mode.TESTNET,
        leverage=settings.bot.sizing.leverage,
    )
    sig = build_signal(settings.bot.signal.engine, dict(settings.bot.signal.params))
    risk = RiskManager(settings=settings, state_dir=Path("data/state"))
    store = StateStore("data/state")
    orch = Orchestrator(settings, adapter, sig, risk, store)

    loop = asyncio.get_running_loop()
    stop_signals = (posix_signal.SIGINT, posix_signal.SIGTERM)
    for s in stop_signals:
        loop.add_signal_handler(s, lambda: asyncio.create_task(orch.stop()))

    await orch.start()
    await orch.run_until_stop()
    return 0


def cli() -> int:
    parser = argparse.ArgumentParser(prog="trading-bot")
    parser.add_argument(
        "--config-dir",
        default="config",
        help="Directory containing bot.yaml and symbols.yaml",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_bt = sub.add_parser("backtest", help="Run a backtest on historical klines")
    p_bt.add_argument("--start", required=True, help="UTC date YYYY-MM-DD or ISO")
    p_bt.add_argument("--end", required=True, help="UTC date YYYY-MM-DD or ISO")
    p_bt.add_argument("--symbols", default="", help="Comma-separated; defaults to symbols.yaml")
    p_bt.add_argument("--signal", default="", help="Override signal: name[:k=v[:k=v]]")
    p_bt.add_argument("--by-month", action="store_true", help="Print monthly breakdown")
    p_bt.add_argument("--with-risk", action="store_true",
                      help="Apply RiskManager caps during the backtest (matches live behavior)")
    p_bt.add_argument("--kline-workers", type=int, default=4,
                      help="Concurrent symbol kline loads/fetches")
    p_bt.add_argument("--tp-offset-bps", type=float, default=None,
                      help="Override TP offset in basis points")
    p_bt.add_argument("--initial-equity", type=float, default=None,
                      help="Initial equity used for ROI and drawdown percentages; defaults to account.initial_equity")
    p_bt.add_argument("--margin-usd", type=float, default=None,
                      help="Override margin per entry order in USDT")
    p_bt.add_argument("--leverage", type=int, default=None,
                      help="Override leverage")
    p_bt.add_argument("--max-notional-account", type=float, default=None,
                      help="Override account-wide risk notional cap in USDT")
    p_bt.add_argument("--max-notional-per-symbol", type=float, default=None,
                      help="Override per-symbol risk notional cap in USDT")
    p_bt.add_argument("--daily-loss-limit", type=float, default=None,
                      help="Override daily loss limit in USDT")
    p_bt.add_argument("--stop-bep-bps", type=float, default=None,
                      help="Backtest forced close when price moves this many bps from BEP")
    p_bt.add_argument("--stop-symbol-loss", type=float, default=None,
                      help="Backtest forced close when a symbol's unrealized loss reaches this USDT amount")
    p_bt.add_argument("--stop-account-dd-pct", type=float, default=None,
                      help="Backtest forced close all positions and halt new entries at this account DD percent")
    p_bt.add_argument("--stop-max-hold-hours", type=float, default=None,
                      help="Backtest forced close when a symbol has been open this many hours")
    p_bt.add_argument("--stop-monthly-profit-lock-pct", type=float, default=None,
                      help="Backtest lock new entries for the rest of a UTC month after this realized ROI percent")
    p_bt.add_argument("--stop-monthly-dd-pct", type=float, default=None,
                      help="Backtest force close and lock new entries for the rest of a UTC month after this DD percent")
    _add_execution_args(p_bt)

    p_cmp = sub.add_parser("compare", help="Run several signals on same data, side-by-side")
    p_cmp.add_argument("--start", required=True, help="UTC date YYYY-MM-DD or ISO")
    p_cmp.add_argument("--end", required=True, help="UTC date YYYY-MM-DD or ISO")
    p_cmp.add_argument("--symbols", default="", help="Comma-separated; defaults to symbols.yaml")
    p_cmp.add_argument(
        "--signals", required=True,
        help="Comma-separated `name[:k=v[:k=v]]` (e.g. "
             "'bollinger_bands,zscore:period=50,grid:entry_bps=80')",
    )
    p_cmp.add_argument("--by-month", action="store_true", help="Print monthly breakdown per signal")
    p_cmp.add_argument("--with-risk", action="store_true",
                       help="Apply RiskManager caps during the backtest")
    p_cmp.add_argument("--kline-workers", type=int, default=4,
                       help="Concurrent symbol kline loads/fetches")
    p_cmp.add_argument("--tp-offset-bps", type=float, default=None,
                       help="Override TP offset in basis points")
    p_cmp.add_argument("--initial-equity", type=float, default=None,
                       help="Initial equity used for ROI and drawdown percentages; defaults to account.initial_equity")
    p_cmp.add_argument("--margin-usd", type=float, default=None,
                       help="Override margin per entry order in USDT")
    p_cmp.add_argument("--leverage", type=int, default=None,
                       help="Override leverage")
    p_cmp.add_argument("--max-notional-account", type=float, default=None,
                       help="Override account-wide risk notional cap in USDT")
    p_cmp.add_argument("--max-notional-per-symbol", type=float, default=None,
                       help="Override per-symbol risk notional cap in USDT")
    p_cmp.add_argument("--daily-loss-limit", type=float, default=None,
                       help="Override daily loss limit in USDT")
    p_cmp.add_argument("--stop-bep-bps", type=float, default=None,
                       help="Backtest forced close when price moves this many bps from BEP")
    p_cmp.add_argument("--stop-symbol-loss", type=float, default=None,
                       help="Backtest forced close when a symbol's unrealized loss reaches this USDT amount")
    p_cmp.add_argument("--stop-account-dd-pct", type=float, default=None,
                       help="Backtest forced close all positions and halt new entries at this account DD percent")
    p_cmp.add_argument("--stop-max-hold-hours", type=float, default=None,
                       help="Backtest forced close when a symbol has been open this many hours")
    p_cmp.add_argument("--stop-monthly-profit-lock-pct", type=float, default=None,
                       help="Backtest lock new entries for the rest of a UTC month after this realized ROI percent")
    p_cmp.add_argument("--stop-monthly-dd-pct", type=float, default=None,
                       help="Backtest force close and lock new entries for the rest of a UTC month after this DD percent")

    p_ce = sub.add_parser("compare-execution", help="Compare naive vs realistic execution backtests")
    p_ce.add_argument("--start", required=True, help="UTC date YYYY-MM-DD or ISO")
    p_ce.add_argument("--end", required=True, help="UTC date YYYY-MM-DD or ISO")
    p_ce.add_argument("--symbols", default="", help="Comma-separated; defaults to symbols.yaml")
    p_ce.add_argument("--signal", default="", help="Override signal: name[:k=v[:k=v]]")
    p_ce.add_argument("--with-risk", action="store_true",
                      help="Apply RiskManager caps during the backtest")
    p_ce.add_argument("--kline-workers", type=int, default=4,
                      help="Concurrent symbol kline loads/fetches")
    p_ce.add_argument("--tp-offset-bps", type=float, default=None,
                      help="Override TP offset in basis points")
    p_ce.add_argument("--initial-equity", type=float, default=None,
                      help="Initial equity used for ROI and drawdown percentages; defaults to account.initial_equity")
    p_ce.add_argument("--margin-usd", type=float, default=None,
                      help="Override margin per entry order in USDT")
    p_ce.add_argument("--leverage", type=int, default=None,
                      help="Override leverage")
    p_ce.add_argument("--max-notional-account", type=float, default=None,
                      help="Override account-wide risk notional cap in USDT")
    p_ce.add_argument("--max-notional-per-symbol", type=float, default=None,
                      help="Override per-symbol risk notional cap in USDT")
    p_ce.add_argument("--daily-loss-limit", type=float, default=None,
                      help="Override daily loss limit in USDT")
    p_ce.add_argument("--stop-bep-bps", type=float, default=None,
                      help="Backtest forced close when price moves this many bps from BEP")
    p_ce.add_argument("--stop-symbol-loss", type=float, default=None,
                      help="Backtest forced close when a symbol's unrealized loss reaches this USDT amount")
    p_ce.add_argument("--stop-account-dd-pct", type=float, default=None,
                      help="Backtest force close all positions and halt new entries at this account DD percent")
    p_ce.add_argument("--stop-max-hold-hours", type=float, default=None,
                      help="Backtest forced close when a symbol has been open this many hours")
    p_ce.add_argument("--stop-monthly-profit-lock-pct", type=float, default=None,
                      help="Backtest lock new entries for the rest of a UTC month after this realized ROI percent")
    p_ce.add_argument("--stop-monthly-dd-pct", type=float, default=None,
                      help="Backtest force close and lock new entries for the rest of a UTC month after this DD percent")
    p_ce.add_argument("--latencies", default=None,
                      help="Comma-separated realistic execution latencies; defaults to execution profile")
    p_ce.add_argument("--min-annual-roi-pct", type=float, default=12.0,
                      help="Minimum annualized ROI target")
    p_ce.add_argument("--max-annual-roi-pct", type=float, default=30.0,
                      help="Upper annualized ROI target band")
    p_ce.add_argument("--output-csv", default="logs/compare_execution_models.csv")
    p_ce.add_argument("--output-report", default="reports/compare_execution_models.md")
    p_ce.add_argument("--label", default="")
    _add_execution_args(p_ce, include_model=False)

    p_stress = sub.add_parser("stress", help="Run historical plus synthetic liquidation stress tests")
    p_stress.add_argument("--start", required=True, help="UTC date YYYY-MM-DD or ISO")
    p_stress.add_argument("--end", required=True, help="UTC date YYYY-MM-DD or ISO")
    p_stress.add_argument("--symbols", default="", help="Comma-separated; defaults to symbols.yaml")
    p_stress.add_argument("--signal", default="", help="Override signal: name[:k=v[:k=v]]")
    p_stress.add_argument("--with-risk", action="store_true", help="Apply RiskManager caps during the backtest")
    p_stress.add_argument("--kline-workers", type=int, default=4, help="Concurrent symbol kline loads/fetches")
    p_stress.add_argument("--shocks", default="-20,-40,-60,-80", help="Comma-separated instant shock percentages")
    p_stress.add_argument("--initial-equity", type=float, default=None,
                          help="Initial equity; defaults to account.initial_equity")
    p_stress.add_argument("--margin-usd", type=float, default=None, help="Override margin per entry order")
    p_stress.add_argument("--leverage", type=int, default=None, help="Override leverage")
    p_stress.add_argument("--max-notional-account", type=float, default=None, help="Override account cap")
    p_stress.add_argument("--max-notional-per-symbol", type=float, default=None, help="Override symbol cap")
    p_stress.add_argument("--daily-loss-limit", type=float, default=None, help="Override daily loss limit")

    p_opt = sub.add_parser("optimize-lot-size", help="Sweep sizing/risk parameters with safety gates first")
    p_opt.add_argument("--start", required=True, help="UTC date YYYY-MM-DD or ISO")
    p_opt.add_argument("--end", required=True, help="UTC date YYYY-MM-DD or ISO")
    p_opt.add_argument("--symbols", default="", help="Comma-separated; defaults to symbols.yaml")
    p_opt.add_argument("--signal", default="", help="Override signal: name[:k=v[:k=v]]")
    p_opt.add_argument("--with-risk", action="store_true", help="Apply RiskManager caps during the backtest")
    p_opt.add_argument("--kline-workers", type=int, default=4, help="Concurrent symbol kline loads/fetches")
    p_opt.add_argument("--margins", required=True, help="Comma-separated margin_usd values")
    p_opt.add_argument("--leverages", default="10", help="Comma-separated leverage values")
    p_opt.add_argument("--account-caps", default="", help="Comma-separated account notional caps")
    p_opt.add_argument("--symbol-caps", default="", help="Comma-separated per-symbol notional caps")
    p_opt.add_argument("--initial-equity", type=float, default=None,
                       help="Initial equity; defaults to account.initial_equity")
    p_opt.add_argument("--tp-offset-bps", type=float, default=None, help="Override TP offset in basis points")
    p_opt.add_argument("--margin-usd", type=float, default=None, help="Base margin override before sweep")
    p_opt.add_argument("--leverage", type=int, default=None, help="Base leverage override before sweep")
    p_opt.add_argument("--max-notional-account", type=float, default=None, help="Base account cap override")
    p_opt.add_argument("--max-notional-per-symbol", type=float, default=None, help="Base symbol cap override")
    p_opt.add_argument("--daily-loss-limit", type=float, default=None, help="Override daily loss limit")

    p_stab = sub.add_parser("optimize-stability", help="Sweep safe sizing configs and rank monthly stability")
    p_stab.add_argument("--start", required=True, help="UTC date YYYY-MM-DD or ISO")
    p_stab.add_argument("--end", required=True, help="UTC date YYYY-MM-DD or ISO")
    p_stab.add_argument("--symbols", default="", help="Comma-separated; defaults to symbols.yaml")
    p_stab.add_argument("--signal", default="", help="Override signal: name[:k=v[:k=v]]")
    p_stab.add_argument("--with-risk", action="store_true", help="Apply RiskManager caps during the backtest")
    p_stab.add_argument("--kline-workers", type=int, default=4, help="Concurrent symbol kline loads/fetches")
    p_stab.add_argument("--margins", required=True, help="Comma-separated margin_usd values")
    p_stab.add_argument("--leverages", default="10", help="Comma-separated leverage values")
    p_stab.add_argument("--account-caps", default="", help="Comma-separated account notional caps")
    p_stab.add_argument("--symbol-caps", default="", help="Comma-separated per-symbol notional caps")
    p_stab.add_argument("--tp-offsets", default="", help="Comma-separated TP offset bps values")
    p_stab.add_argument("--initial-equity", type=float, default=None,
                        help="Initial equity; defaults to account.initial_equity")
    p_stab.add_argument("--target-monthly-roi-pct", type=float, default=0.5,
                        help="Target monthly ROI percentage for stability scoring")
    p_stab.add_argument("--min-positive-month-pct", type=float, default=70.0,
                        help="Required positive-month percentage")
    p_stab.add_argument("--min-target-month-pct", type=float, default=50.0,
                        help="Required percentage of months at or above target monthly ROI")
    p_stab.add_argument("--max-non-positive-stretch", type=int, default=2,
                        help="Maximum consecutive months with ROI <= 0")
    p_stab.add_argument("--max-worst-monthly-dd-pct", type=float, default=10.0,
                        help="Maximum allowed worst monthly drawdown percentage")
    p_stab.add_argument("--tp-offset-bps", type=float, default=None, help="Base TP offset override before sweep")
    p_stab.add_argument("--margin-usd", type=float, default=None, help="Base margin override before sweep")
    p_stab.add_argument("--leverage", type=int, default=None, help="Base leverage override before sweep")
    p_stab.add_argument("--max-notional-account", type=float, default=None, help="Base account cap override")
    p_stab.add_argument("--max-notional-per-symbol", type=float, default=None, help="Base symbol cap override")
    p_stab.add_argument("--daily-loss-limit", type=float, default=None, help="Override daily loss limit")
    p_stab.add_argument("--stop-bep-bps", type=float, default=None,
                        help="Backtest forced close when price moves this many bps from BEP")
    p_stab.add_argument("--stop-symbol-loss", type=float, default=None,
                        help="Backtest forced close when a symbol's unrealized loss reaches this USDT amount")
    p_stab.add_argument("--stop-account-dd-pct", type=float, default=None,
                        help="Backtest force close all positions and halt new entries at this account DD percent")
    p_stab.add_argument("--stop-max-hold-hours", type=float, default=None,
                        help="Backtest forced close when a symbol has been open this many hours")
    p_stab.add_argument("--stop-monthly-profit-lock-pct", type=float, default=None,
                        help="Backtest lock new entries for the rest of a UTC month after this realized ROI percent")
    p_stab.add_argument("--stop-monthly-dd-pct", type=float, default=None,
                        help="Backtest force close and lock new entries for the rest of a UTC month after this DD percent")

    p_class = sub.add_parser("classify-market", help="Label historical/current market regime")
    p_class.add_argument("--start", required=True, help="UTC date YYYY-MM-DD or ISO")
    p_class.add_argument("--end", required=True, help="UTC date YYYY-MM-DD or ISO")
    p_class.add_argument("--symbols", default="", help="Comma-separated; defaults to symbols.yaml")
    p_class.add_argument("--kline-workers", type=int, default=4, help="Concurrent symbol kline loads/fetches")

    p_sel = sub.add_parser("select-strategy", help="Pick the safest validated strategy for the detected regime")
    p_sel.add_argument("--start", required=True, help="UTC date YYYY-MM-DD or ISO")
    p_sel.add_argument("--end", required=True, help="UTC date YYYY-MM-DD or ISO")
    p_sel.add_argument("--symbols", default="", help="Comma-separated; defaults to symbols.yaml")
    p_sel.add_argument("--signals", required=True, help="Comma-separated `name[:k=v[:k=v]]`")
    p_sel.add_argument("--with-risk", action="store_true", help="Apply RiskManager caps during the backtest")
    p_sel.add_argument("--kline-workers", type=int, default=4, help="Concurrent symbol kline loads/fetches")
    p_sel.add_argument("--initial-equity", type=float, default=None,
                       help="Initial equity; defaults to account.initial_equity")
    p_sel.add_argument("--tp-offset-bps", type=float, default=None, help="Override TP offset in basis points")
    p_sel.add_argument("--margin-usd", type=float, default=None, help="Override margin per entry order")
    p_sel.add_argument("--leverage", type=int, default=None, help="Override leverage")
    p_sel.add_argument("--max-notional-account", type=float, default=None, help="Override account cap")
    p_sel.add_argument("--max-notional-per-symbol", type=float, default=None, help="Override symbol cap")
    p_sel.add_argument("--daily-loss-limit", type=float, default=None, help="Override daily loss limit")

    p_run = sub.add_parser("run", help="Run live (mode picked from .env)")

    args = parser.parse_args()
    settings = load_settings(config_dir=args.config_dir)
    configure_logging(settings.env.log_level)
    log = get_logger(__name__)
    log.info(
        "boot.banner", mode=settings.env.mode.value,
        margin_per_order=settings.bot.sizing.margin_usd,
        leverage=settings.bot.sizing.leverage,
        symbols=len(settings.symbols.active),
    )

    if args.cmd == "backtest":
        return asyncio.run(_cmd_backtest(args, settings))
    if args.cmd == "compare":
        return asyncio.run(_cmd_compare(args, settings))
    if args.cmd == "compare-execution":
        return asyncio.run(_cmd_compare_execution(args, settings))
    if args.cmd == "stress":
        return asyncio.run(_cmd_stress(args, settings))
    if args.cmd == "optimize-lot-size":
        return asyncio.run(_cmd_optimize_lot_size(args, settings))
    if args.cmd == "optimize-stability":
        return asyncio.run(_cmd_optimize_stability(args, settings))
    if args.cmd == "classify-market":
        return asyncio.run(_cmd_classify_market(args, settings))
    if args.cmd == "select-strategy":
        return asyncio.run(_cmd_select_strategy(args, settings))
    if args.cmd == "run":
        return asyncio.run(_cmd_run(args, settings))
    return 2


if __name__ == "__main__":
    sys.exit(cli())
