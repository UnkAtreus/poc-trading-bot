from __future__ import annotations

import argparse
import asyncio
import copy
import csv
import glob
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from bot.backtest.archive import archive_record, settings_snapshot
from bot.backtest.downloader import df_to_candles, load_or_fetch
from bot.backtest.runner import BacktestStopConfig, run_backtest
from bot.backtest.stability import StabilityGates, analyze_stability
from bot.config import Settings, load_settings
from bot.logger import configure as configure_logging
from bot.risk.manager import RiskManager
from bot.signals.base import build as build_signal


CSV_FIELDNAMES = [
    "candidate_id",
    "start",
    "end",
    "symbols",
    "margin_usd",
    "leverage",
    "account_cap",
    "symbol_cap",
    "tp_offset_bps",
    "trades",
    "wins",
    "losses",
    "win_rate_pct",
    "net_pnl",
    "roi_pct",
    "max_drawdown",
    "max_drawdown_pct",
    "liquidated",
    "near_liquidation",
    "min_liq_distance_pct",
    "margin_ratio_max",
    "worst_unrealized_loss",
    "final_open_exposure",
    "months",
    "positive_month_pct",
    "target_month_pct",
    "avg_monthly_roi_pct",
    "median_monthly_roi_pct",
    "worst_monthly_roi_pct",
    "worst_monthly_dd_pct",
    "longest_non_positive_stretch",
    "stability_score",
    "safe",
    "stable",
    "launch_pass",
    "elapsed_seconds",
    "error",
]


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    start: str
    end: str
    symbols: tuple[str, ...]
    signal_name: str
    signal_params: dict[str, Any]
    margin_usd: float
    leverage: int
    account_cap: float
    symbol_cap: float
    tp_offset_bps: float
    stops: BacktestStopConfig | None


def _parse_day(day: str) -> datetime:
    return datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _parse_csv_list(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def _parse_float_list(raw: str) -> list[float]:
    values = [float(part.strip()) for part in raw.split(",") if part.strip()]
    if not values:
        raise SystemExit("expected a comma-separated list of numbers")
    return values


def _coerce(value: str) -> int | float | bool | str:
    for caster in (int, float):
        try:
            return caster(value)
        except ValueError:
            pass
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    return value


def _parse_signal_spec(spec: str, settings: Settings) -> tuple[str, dict[str, Any]]:
    if not spec:
        return settings.bot.signal.engine, dict(settings.bot.signal.params)
    tokens = _parse_csv_list(spec)
    if len(tokens) != 1:
        raise SystemExit("--signal accepts exactly one engine")
    parts = tokens[0].split(":")
    params: dict[str, Any] = {}
    for kv in parts[1:]:
        if "=" not in kv:
            raise SystemExit(f"bad signal param '{kv}' in '{tokens[0]}': expected k=v")
        key, value = kv.split("=", 1)
        params[key.strip()] = _coerce(value.strip())
    return parts[0], params


def _stop_config_from_args(args: argparse.Namespace) -> BacktestStopConfig | None:
    max_hold_seconds = None
    if args.stop_max_hold_hours is not None:
        max_hold_seconds = args.stop_max_hold_hours * 3600.0
    cfg = BacktestStopConfig(
        bep_stop_bps=args.stop_bep_bps,
        max_symbol_loss_usd=args.stop_symbol_loss,
        account_dd_stop_pct=args.stop_account_dd_pct,
        max_hold_seconds=max_hold_seconds,
        monthly_profit_lock_pct=args.stop_monthly_profit_lock_pct,
        monthly_dd_stop_pct=args.stop_monthly_dd_pct,
    )
    if all(value is None for value in asdict(cfg).values()):
        return None
    return cfg


def _stops_identity(stops: BacktestStopConfig | None) -> dict[str, Any]:
    return {} if stops is None else asdict(stops)


def _candidate_id(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha1(encoded.encode("utf-8")).hexdigest()


def _build_candidates(args: argparse.Namespace, settings: Settings) -> list[Candidate]:
    symbols = tuple(_parse_csv_list(args.symbols) or settings.symbols.active)
    signal_name, signal_params = _parse_signal_spec(args.signal, settings)
    stops = _stop_config_from_args(args)
    margins = _parse_float_list(args.margins)
    leverages = [int(value) for value in _parse_float_list(args.leverages)]
    account_caps = _parse_float_list(args.account_caps) if args.account_caps else [settings.bot.risk.max_notional_account_usd]
    symbol_caps = _parse_float_list(args.symbol_caps) if args.symbol_caps else [settings.bot.risk.max_notional_per_symbol_usd]
    tp_offsets = _parse_float_list(args.tp_offsets) if args.tp_offsets else [settings.bot.offsets.tp_offset_bps]

    candidates: list[Candidate] = []
    seen: set[str] = set()
    for margin in margins:
        for leverage in leverages:
            for account_cap in account_caps:
                for symbol_cap in symbol_caps:
                    for tp_offset in tp_offsets:
                        identity = {
                            "start": args.start,
                            "end": args.end,
                            "symbols": list(symbols),
                            "signal": signal_name,
                            "signal_params": signal_params,
                            "margin_usd": margin,
                            "leverage": leverage,
                            "account_cap": account_cap,
                            "symbol_cap": symbol_cap,
                            "tp_offset_bps": tp_offset,
                            "stops": _stops_identity(stops),
                        }
                        candidate_id = _candidate_id(identity)
                        if candidate_id in seen:
                            continue
                        seen.add(candidate_id)
                        candidates.append(Candidate(
                            candidate_id=candidate_id,
                            start=args.start,
                            end=args.end,
                            symbols=symbols,
                            signal_name=signal_name,
                            signal_params=signal_params,
                            margin_usd=margin,
                            leverage=leverage,
                            account_cap=account_cap,
                            symbol_cap=symbol_cap,
                            tp_offset_bps=tp_offset,
                            stops=stops,
                        ))

    return candidates


def _select_shard(candidates: list[Candidate], args: argparse.Namespace) -> list[Candidate]:
    if args.shard_count < 1:
        raise SystemExit("--shard-count must be >= 1")
    if args.shard_index < 0 or args.shard_index >= args.shard_count:
        raise SystemExit("--shard-index must be >= 0 and < --shard-count")

    selected = [
        candidate
        for index, candidate in enumerate(candidates)
        if index % args.shard_count == args.shard_index
    ]
    if args.max_candidates is not None:
        selected = selected[:args.max_candidates]
    return selected


def _format_shard_path(path: Path, args: argparse.Namespace) -> Path:
    if args.shard_count <= 1:
        return path
    raw = str(path)
    if "{shard" in raw or "{shard_index" in raw or "{shard_count" in raw:
        return Path(raw.format(
            shard=args.shard_index,
            shard_index=args.shard_index,
            shard_count=args.shard_count,
        ))
    suffix = "".join(path.suffixes)
    stem = path.name[:-len(suffix)] if suffix else path.name
    shard_name = f"{stem}_shard{args.shard_index:02d}of{args.shard_count:02d}{suffix}"
    return path.with_name(shard_name)


async def _load_candles(
    symbols: Iterable[str],
    start: datetime,
    end: datetime,
    *,
    workers: int,
    cache_dir: str,
) -> dict[str, list]:
    sem = asyncio.Semaphore(max(1, workers))
    start_ms = _to_ms(start)
    end_ms = _to_ms(end)

    async def load_one(symbol: str):
        async with sem:
            df = await asyncio.to_thread(load_or_fetch, symbol, start_ms, end_ms, cache_dir)
            if df.empty:
                return None
            return symbol, df_to_candles(df, symbol)

    loaded = await asyncio.gather(*(load_one(symbol) for symbol in symbols))
    return dict(item for item in loaded if item is not None)


def _load_completed_ids(csv_path: Path) -> set[str]:
    if not csv_path.exists():
        return set()
    with csv_path.open(newline="") as f:
        return {
            row["candidate_id"]
            for row in csv.DictReader(f)
            if row.get("candidate_id")
        }


def _open_writer(csv_path: Path, *, append: bool) -> tuple[Any, csv.DictWriter]:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = csv_path.exists() and csv_path.stat().st_size > 0
    f = csv_path.open("a" if append else "w", newline="")
    writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
    if not append or not file_exists:
        writer.writeheader()
        f.flush()
    return f, writer


def _base_row(candidate: Candidate, *, elapsed_seconds: float, error: str = "") -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "start": candidate.start,
        "end": candidate.end,
        "symbols": ",".join(candidate.symbols),
        "margin_usd": candidate.margin_usd,
        "leverage": candidate.leverage,
        "account_cap": candidate.account_cap,
        "symbol_cap": candidate.symbol_cap,
        "tp_offset_bps": candidate.tp_offset_bps,
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "win_rate_pct": 0.0,
        "net_pnl": 0.0,
        "roi_pct": 0.0,
        "max_drawdown": 0.0,
        "max_drawdown_pct": 0.0,
        "liquidated": False,
        "near_liquidation": False,
        "min_liq_distance_pct": 0.0,
        "margin_ratio_max": 0.0,
        "worst_unrealized_loss": 0.0,
        "final_open_exposure": 0.0,
        "months": 0,
        "positive_month_pct": 0.0,
        "target_month_pct": 0.0,
        "avg_monthly_roi_pct": 0.0,
        "median_monthly_roi_pct": 0.0,
        "worst_monthly_roi_pct": 0.0,
        "worst_monthly_dd_pct": 0.0,
        "longest_non_positive_stretch": 0,
        "stability_score": -1_000_000.0,
        "safe": False,
        "stable": False,
        "launch_pass": False,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "error": error,
    }


def _prune_reason(candidate: Candidate) -> str | None:
    notional = candidate.margin_usd * candidate.leverage
    if notional > candidate.symbol_cap:
        return "notional_gt_symbol_cap"
    if notional > candidate.account_cap:
        return "notional_gt_account_cap"
    if candidate.symbol_cap * len(candidate.symbols) < notional:
        return "symbol_capacity_lt_order_notional"
    return None


def _safe(result, *, max_drawdown_pct: float, max_open_exposure: float) -> bool:
    return (
        not result.liquidated
        and not result.near_liquidation
        and result.max_drawdown_pct * 100.0 <= max_drawdown_pct
        and result.final_open_exposure <= max_open_exposure
    )


def _row_from_result(
    candidate: Candidate,
    result,
    stability,
    *,
    initial_equity: float,
    elapsed_seconds: float,
    max_drawdown_pct: float,
    max_open_exposure: float,
) -> dict[str, Any]:
    safe = _safe(result, max_drawdown_pct=max_drawdown_pct, max_open_exposure=max_open_exposure)
    stable = stability.passes
    row = _base_row(candidate, elapsed_seconds=elapsed_seconds)
    row.update({
        "trades": len(result.trades),
        "wins": result.wins,
        "losses": result.losses,
        "win_rate_pct": result.win_rate * 100.0,
        "net_pnl": result.net_pnl,
        "roi_pct": result.net_pnl / initial_equity * 100.0 if initial_equity > 0 else 0.0,
        "max_drawdown": result.max_drawdown,
        "max_drawdown_pct": result.max_drawdown_pct * 100.0,
        "liquidated": result.liquidated,
        "near_liquidation": result.near_liquidation,
        "min_liq_distance_pct": result.min_liq_distance_pct,
        "margin_ratio_max": result.margin_ratio_max,
        "worst_unrealized_loss": result.worst_unrealized_loss,
        "final_open_exposure": result.final_open_exposure,
        "months": stability.months,
        "positive_month_pct": stability.positive_month_pct,
        "target_month_pct": stability.target_month_pct,
        "avg_monthly_roi_pct": stability.avg_monthly_roi_pct,
        "median_monthly_roi_pct": stability.median_monthly_roi_pct,
        "worst_monthly_roi_pct": stability.worst_monthly_roi_pct,
        "worst_monthly_dd_pct": stability.worst_monthly_dd_pct,
        "longest_non_positive_stretch": stability.longest_non_positive_stretch,
        "stability_score": stability.score,
        "safe": safe,
        "stable": stable,
        "launch_pass": safe and stable,
    })
    return row


def _apply_candidate_settings(settings: Settings, candidate: Candidate) -> Settings:
    scenario = copy.deepcopy(settings)
    scenario.bot.sizing.margin_usd = candidate.margin_usd
    scenario.bot.sizing.leverage = candidate.leverage
    scenario.bot.risk.max_notional_account_usd = candidate.account_cap
    scenario.bot.risk.max_notional_per_symbol_usd = candidate.symbol_cap
    scenario.bot.offsets.tp_offset_bps = candidate.tp_offset_bps
    return scenario


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _format_finish_time(eta_seconds: float) -> str:
    finish_at = datetime.now().astimezone().timestamp() + max(0.0, eta_seconds)
    return datetime.fromtimestamp(finish_at).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def _progress_line(
    done: int,
    total: int,
    candidate: Candidate,
    row: dict[str, Any],
    started_at: float,
    processed_this_run: int,
) -> str:
    elapsed = time.monotonic() - started_at
    remaining = max(0, total - done)
    pct = done / total * 100.0 if total else 100.0
    avg_seconds = elapsed / processed_this_run if processed_this_run > 0 else 0.0
    eta = avg_seconds * remaining
    return (
        f"[{done}/{total} {pct:.1f}%] margin={candidate.margin_usd:g} leverage={candidate.leverage} "
        f"account_cap={candidate.account_cap:g} symbol_cap={candidate.symbol_cap:g} "
        f"tp={candidate.tp_offset_bps:g} safe={row['safe']} stable={row['stable']} "
        f"elapsed={_format_duration(elapsed)} avg={avg_seconds:.1f}s/candidate "
        f"remaining={remaining} eta={_format_duration(eta)} finish_at=\"{_format_finish_time(eta)}\""
    )


def _read_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")
    with csv_path.open(newline="") as f:
        return list(csv.DictReader(f))


def _expand_csv_inputs(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for raw in patterns:
        for token in _parse_csv_list(raw):
            matches = sorted(Path(match) for match in glob.glob(token))
            if not matches:
                matches = [Path(token)]
            for path in matches:
                if path not in seen:
                    paths.append(path)
                    seen.add(path)
    return paths


def _merge_csv_rows(paths: list[Path]) -> list[dict[str, str]]:
    rows_by_id: dict[str, dict[str, str]] = {}
    rows_without_id: list[dict[str, str]] = []
    for path in paths:
        for row in _read_rows(path):
            candidate_id = row.get("candidate_id", "")
            if candidate_id:
                rows_by_id[candidate_id] = row
            else:
                rows_without_id.append(row)
    return rows_without_id + list(rows_by_id.values())


def _write_rows(csv_path: Path, rows: list[dict[str, Any]]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _as_bool(row: dict[str, str], key: str) -> bool:
    return str(row.get(key, "")).lower() == "true"


def _as_float(row: dict[str, str], key: str) -> float:
    try:
        return float(row.get(key, "") or 0.0)
    except ValueError:
        return 0.0


def _as_int(row: dict[str, str], key: str) -> int:
    try:
        return int(float(row.get(key, "") or 0))
    except ValueError:
        return 0


def _sort_best(row: dict[str, str]) -> tuple[float, float, float, float]:
    return (
        -_as_float(row, "stability_score"),
        _as_float(row, "max_drawdown_pct"),
        _as_float(row, "margin_usd"),
        -_as_float(row, "net_pnl"),
    )


def _render_table(rows: list[dict[str, str]]) -> list[str]:
    lines = [
        "| Margin | Lev | Account cap | Symbol cap | TP bps | Safe | Stable | Score | ROI | Max DD | Open exposure | Error |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {_as_float(row, 'margin_usd'):g} | {_as_int(row, 'leverage')} | "
            f"{_as_float(row, 'account_cap'):,.0f} | {_as_float(row, 'symbol_cap'):,.0f} | "
            f"{_as_float(row, 'tp_offset_bps'):g} | {row.get('safe', '')} | {row.get('stable', '')} | "
            f"{_as_float(row, 'stability_score'):.2f} | {_as_float(row, 'roi_pct'):.2f}% | "
            f"{_as_float(row, 'max_drawdown_pct'):.2f}% | {_as_float(row, 'final_open_exposure'):,.2f} | "
            f"{row.get('error', '')} |"
        )
    return lines


def _render_report(rows: list[dict[str, str]], csv_path: Path, *, total_candidates: int | None = None) -> str:
    completed = len(rows)
    pruned = [row for row in rows if row.get("error", "").startswith("pruned:")]
    errors = [row for row in rows if row.get("error", "") and not row.get("error", "").startswith("pruned:")]
    launch_pass = [row for row in rows if _as_bool(row, "launch_pass")]
    safe_not_stable = [
        row for row in rows
        if _as_bool(row, "safe") and not _as_bool(row, "stable") and not row.get("error")
    ]
    by_score = sorted(rows, key=_sort_best)
    worst_drawdown = sorted(rows, key=lambda row: _as_float(row, "max_drawdown_pct"), reverse=True)
    candidate_count = total_candidates if total_candidates is not None else completed
    best = sorted(launch_pass, key=_sort_best)

    if best:
        recommended = best[0]
        decision = "trade"
    elif safe_not_stable:
        recommended = sorted(safe_not_stable, key=_sort_best)[0]
        decision = "reduce_size"
    else:
        recommended = None
        decision = "no_trade"

    unique = lambda key: ", ".join(dict.fromkeys(row.get(key, "") for row in rows if row.get(key, "")))
    md = [
        "# Batch Stability Optimizer Report",
        "",
        "## Run Config",
        "",
        f"- Raw CSV: `{csv_path}`",
        f"- Start: `{unique('start')}`",
        f"- End: `{unique('end')}`",
        f"- Symbols: `{unique('symbols')}`",
        "",
        "## Counts",
        "",
        f"- Candidate count: `{candidate_count}`",
        f"- Completed count: `{completed}`",
        f"- Pruned count: `{len(pruned)}`",
        f"- Error count: `{len(errors)}`",
        f"- Launch-pass count: `{len(launch_pass)}`",
        "",
        "## Top 20 Launch-Pass Candidates",
        "",
    ]
    md.extend(_render_table(best[:20]) if best else ["No launch-pass candidates."])
    md.extend([
        "",
        "## Top 20 Safe But Not Stable Candidates",
        "",
    ])
    md.extend(_render_table(sorted(safe_not_stable, key=_sort_best)[:20]) if safe_not_stable else ["No safe-but-unstable candidates."])
    md.extend([
        "",
        "## Top 20 By Stability Score",
        "",
    ])
    md.extend(_render_table(by_score[:20]) if by_score else ["No completed candidates."])
    md.extend([
        "",
        "## Worst 20 By Drawdown",
        "",
    ])
    md.extend(_render_table(worst_drawdown[:20]) if worst_drawdown else ["No completed candidates."])
    md.extend([
        "",
        "## Recommended Lot Size",
        "",
    ])
    if recommended is None:
        md.append("No candidate is safe enough to recommend.")
    else:
        md.extend([
            f"- Margin USD: `{_as_float(recommended, 'margin_usd'):g}`",
            f"- Leverage: `{_as_int(recommended, 'leverage')}`",
            f"- Account cap: `{_as_float(recommended, 'account_cap'):g}`",
            f"- Symbol cap: `{_as_float(recommended, 'symbol_cap'):g}`",
            f"- TP offset bps: `{_as_float(recommended, 'tp_offset_bps'):g}`",
            f"- Stability score: `{_as_float(recommended, 'stability_score'):.2f}`",
        ])
    md.extend([
        "",
        "## Decision",
        "",
        f"`{decision}`",
        "",
    ])
    return "\n".join(md)


async def _run_batch(args: argparse.Namespace) -> int:
    configure_logging(args.log_level)
    settings = load_settings()
    all_candidates = _build_candidates(args, settings)
    candidates = _select_shard(all_candidates, args)
    if not candidates:
        raise SystemExit("no candidates generated")

    csv_path = _format_shard_path(Path(args.output_csv), args)
    report_path = _format_shard_path(Path(args.output_report), args)
    completed_ids = _load_completed_ids(csv_path) if args.resume else set()
    candidate_ids = {candidate.candidate_id for candidate in candidates}
    completed_ids &= candidate_ids

    if args.shard_count > 1:
        print(
            f"shard {args.shard_index}/{args.shard_count}: "
            f"{len(candidates)} of {len(all_candidates)} global candidates -> {csv_path}",
            flush=True,
        )
    print(
        f"loading candles {args.start} -> {args.end} symbols={','.join(candidates[0].symbols)}",
        flush=True,
    )
    candles = await _load_candles(
        candidates[0].symbols,
        _parse_day(args.start),
        _parse_day(args.end),
        workers=args.kline_workers,
        cache_dir=args.kline_cache,
    )
    if not candles:
        raise SystemExit("no candle data loaded")

    gates = StabilityGates(
        target_monthly_roi_pct=args.target_monthly_roi_pct,
        min_positive_month_pct=args.min_positive_month_pct,
        min_target_month_pct=args.min_target_month_pct,
        max_non_positive_stretch=args.max_non_positive_stretch,
        max_worst_monthly_dd_pct=args.max_worst_monthly_dd_pct,
    )
    initial_equity = args.initial_equity or settings.bot.account.initial_equity
    append = args.resume
    started_at = time.monotonic()
    done = len(completed_ids)
    processed_this_run = 0
    if done:
        print(f"resume: {done}/{len(candidates)} candidates already complete", flush=True)

    f, writer = _open_writer(csv_path, append=append)
    with f:
        for candidate in candidates:
            if candidate.candidate_id in completed_ids:
                continue

            candidate_started = time.monotonic()
            prune_reason = _prune_reason(candidate)
            if prune_reason is not None:
                row = _base_row(
                    candidate,
                    elapsed_seconds=time.monotonic() - candidate_started,
                    error=f"pruned:{prune_reason}",
                )
            else:
                try:
                    scenario = _apply_candidate_settings(settings, candidate)
                    signal = build_signal(candidate.signal_name, dict(candidate.signal_params))
                    risk = None
                    if not args.no_risk:
                        risk = RiskManager(settings=scenario, state_dir=Path("data/state"))
                    result = await run_backtest(
                        scenario,
                        candles,
                        signal,
                        risk=risk,
                        initial_equity=initial_equity,
                        stops=candidate.stops,
                    )
                    stability = analyze_stability(result, gates=gates, initial_equity=initial_equity)
                    row = _row_from_result(
                        candidate,
                        result,
                        stability,
                        initial_equity=initial_equity,
                        elapsed_seconds=time.monotonic() - candidate_started,
                        max_drawdown_pct=args.max_drawdown_pct,
                        max_open_exposure=args.max_open_exposure,
                    )
                except Exception as exc:  # Keep overnight sweeps resumable after isolated failures.
                    row = _base_row(
                        candidate,
                        elapsed_seconds=time.monotonic() - candidate_started,
                        error=f"{type(exc).__name__}: {exc}",
                    )

            writer.writerow(row)
            f.flush()
            done += 1
            processed_this_run += 1
            completed_ids.add(candidate.candidate_id)
            print(
                _progress_line(done, len(candidates), candidate, row, started_at, processed_this_run),
                flush=True,
            )

    rows = _read_rows(csv_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_render_report(rows, csv_path, total_candidates=len(candidates)), encoding="utf-8")
    print(f"wrote {csv_path}", flush=True)
    print(f"wrote {report_path}", flush=True)
    _archive_batch_run(
        args=args,
        settings=settings,
        rows=rows,
        csv_path=csv_path,
        report_path=report_path,
        signal_name=candidates[0].signal_name,
        signal_params=candidates[0].signal_params,
        stops=candidates[0].stops,
        gates=gates,
        total_candidates=len(candidates),
        kind="batch_optimize_stability",
    )
    return 0


def _run_report_only(args: argparse.Namespace) -> int:
    csv_path = Path(args.csv or args.output_csv)
    report_path = Path(args.output_report)
    rows = _read_rows(csv_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_render_report(rows, csv_path), encoding="utf-8")
    print(f"wrote {report_path}", flush=True)
    return 0


def _run_merge_csvs(args: argparse.Namespace) -> int:
    input_paths = _expand_csv_inputs(args.merge_csvs)
    if not input_paths:
        raise SystemExit("--merge-csvs did not match any CSV files")
    rows = _merge_csv_rows(input_paths)
    csv_path = Path(args.output_csv)
    report_path = Path(args.output_report)
    _write_rows(csv_path, rows)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_render_report(rows, csv_path, total_candidates=len(rows)), encoding="utf-8")
    print(f"merged {len(input_paths)} CSV files into {csv_path}", flush=True)
    print(f"wrote {report_path}", flush=True)
    settings = load_settings()
    signal_name, signal_params = _parse_signal_spec(args.signal, settings)
    _archive_batch_run(
        args=args,
        settings=settings,
        rows=rows,
        csv_path=csv_path,
        report_path=report_path,
        signal_name=signal_name,
        signal_params=signal_params,
        stops=_stop_config_from_args(args),
        gates=StabilityGates(
            target_monthly_roi_pct=args.target_monthly_roi_pct,
            min_positive_month_pct=args.min_positive_month_pct,
            min_target_month_pct=args.min_target_month_pct,
            max_non_positive_stretch=args.max_non_positive_stretch,
            max_worst_monthly_dd_pct=args.max_worst_monthly_dd_pct,
        ),
        total_candidates=len(rows),
        kind="batch_optimize_stability_merge",
    )
    return 0


def _archive_batch_run(
    *,
    args: argparse.Namespace,
    settings: Settings,
    rows: list[dict[str, str]],
    csv_path: Path,
    report_path: Path,
    signal_name: str,
    signal_params: dict[str, Any],
    stops: BacktestStopConfig | None,
    gates: StabilityGates,
    total_candidates: int,
    kind: str,
) -> None:
    launch_pass = [row for row in rows if _as_bool(row, "launch_pass")]
    safe = [row for row in rows if _as_bool(row, "safe")]
    stable = [row for row in rows if _as_bool(row, "stable")]
    recommended = _recommended_row(rows)
    try:
        archive_path = archive_record({
            "kind": kind,
            "label": f"{args.start}_to_{args.end}",
            "scope": {
                "start": args.start,
                "end": args.end,
                "symbols": _parse_csv_list(args.symbols),
            },
            "strategy": {
                "signal_name": signal_name,
                "signal_params": signal_params,
                "risk_enabled": not getattr(args, "no_risk", False),
                "stops": stops,
                "gates": gates,
            },
            "settings": settings_snapshot(settings),
            "args": vars(args),
            "outputs": {"csv_path": str(csv_path), "report_path": str(report_path)},
            "summary": _archive_summary(
                rows,
                total_candidates=total_candidates,
                launch_pass_count=len(launch_pass),
                safe_count=len(safe),
                stable_count=len(stable),
                recommended=recommended,
                initial_equity=args.initial_equity or settings.bot.account.initial_equity,
            ),
        })
        print(f"archived {archive_path}", flush=True)
    except Exception as exc:
        print(f"archive warning: {type(exc).__name__}: {exc}", flush=True)


def _recommended_row(rows: list[dict[str, str]]) -> dict[str, str] | None:
    launch_pass = [row for row in rows if _as_bool(row, "launch_pass")]
    if launch_pass:
        return sorted(launch_pass, key=_sort_best)[0]
    safe_not_stable = [
        row for row in rows
        if _as_bool(row, "safe") and not _as_bool(row, "stable") and not row.get("error")
    ]
    if safe_not_stable:
        return sorted(safe_not_stable, key=_sort_best)[0]
    return None


def _archive_summary(
    rows: list[dict[str, str]],
    *,
    total_candidates: int,
    launch_pass_count: int,
    safe_count: int,
    stable_count: int,
    recommended: dict[str, str] | None,
    initial_equity: float,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "candidate_count": total_candidates,
        "completed_count": len(rows),
        "launch_pass_count": launch_pass_count,
        "safe_count": safe_count,
        "stable_count": stable_count,
        "initial_equity": initial_equity,
    }
    if recommended:
        summary.update({
            "recommended_candidate_id": recommended.get("candidate_id", ""),
            "recommended_settings": {
                "margin_usd": _as_float(recommended, "margin_usd"),
                "leverage": _as_int(recommended, "leverage"),
                "account_cap": _as_float(recommended, "account_cap"),
                "symbol_cap": _as_float(recommended, "symbol_cap"),
                "tp_offset_bps": _as_float(recommended, "tp_offset_bps"),
            },
            "trades": _as_int(recommended, "trades"),
            "win_rate_pct": _as_float(recommended, "win_rate_pct"),
            "net_pnl": _as_float(recommended, "net_pnl"),
            "roi_pct": _as_float(recommended, "roi_pct"),
            "max_drawdown_pct": _as_float(recommended, "max_drawdown_pct"),
            "liquidated": _as_bool(recommended, "liquidated"),
            "near_liquidation": _as_bool(recommended, "near_liquidation"),
            "final_open_exposure": _as_float(recommended, "final_open_exposure"),
            "avg_monthly_roi_pct": _as_float(recommended, "avg_monthly_roi_pct"),
            "target_month_pct": _as_float(recommended, "target_month_pct"),
            "positive_month_pct": _as_float(recommended, "positive_month_pct"),
        })
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resumable batch stability optimizer")
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2026-05-01")
    parser.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT")
    parser.add_argument("--signal", default="")
    parser.add_argument("--margins", default="10,20,30,50,66,80,100")
    parser.add_argument("--leverages", default="3,5,10")
    parser.add_argument("--account-caps", default="5000,7500,10000,12500,15000,20000")
    parser.add_argument("--symbol-caps", default="500,1000,1500,2000,3000,4000")
    parser.add_argument("--tp-offsets", default="30,50,75,100")
    parser.add_argument("--initial-equity", type=float, default=None)
    parser.add_argument("--target-monthly-roi-pct", type=float, default=0.5)
    parser.add_argument("--min-positive-month-pct", type=float, default=70.0)
    parser.add_argument("--min-target-month-pct", type=float, default=50.0)
    parser.add_argument("--max-non-positive-stretch", type=int, default=2)
    parser.add_argument("--max-worst-monthly-dd-pct", type=float, default=10.0)
    parser.add_argument("--max-drawdown-pct", type=float, default=25.0)
    parser.add_argument("--max-open-exposure", type=float, default=5_000.0)
    parser.add_argument("--output-csv", default="logs/batch_optimize_stability_2024_2026_core.csv")
    parser.add_argument("--output-report", default="reports/batch_optimize_stability_2024_2026_core.md")
    parser.add_argument("--csv", default="", help="Input CSV for --report-only; defaults to --output-csv")
    parser.add_argument(
        "--merge-csvs",
        nargs="+",
        default=[],
        help="Merge shard CSV files or glob patterns, then write --output-csv and --output-report",
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--max-candidates", type=int, default=None)
    parser.add_argument("--shard-count", type=int, default=1, help="Split the candidate grid across this many workers")
    parser.add_argument("--shard-index", type=int, default=0, help="Zero-based shard index for this worker")
    parser.add_argument("--kline-workers", type=int, default=4)
    parser.add_argument("--kline-cache", default="data/klines")
    parser.add_argument("--no-risk", action="store_true", help="Run without RiskManager caps")
    parser.add_argument("--log-level", default="ERROR")
    parser.add_argument("--stop-bep-bps", type=float, default=None)
    parser.add_argument("--stop-symbol-loss", type=float, default=None)
    parser.add_argument("--stop-account-dd-pct", type=float, default=None)
    parser.add_argument("--stop-max-hold-hours", type=float, default=None)
    parser.add_argument("--stop-monthly-profit-lock-pct", type=float, default=None)
    parser.add_argument("--stop-monthly-dd-pct", type=float, default=None)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    if args.merge_csvs:
        return _run_merge_csvs(args)
    if args.report_only:
        return _run_report_only(args)
    return asyncio.run(_run_batch(args))


if __name__ == "__main__":
    raise SystemExit(main())
