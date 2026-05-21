"""Persistent archive for backtest settings and results.

CSV is useful for sorting many runs; JSON is the source of truth for exact
settings, overrides, stops, gates, and detailed metrics.
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel

from bot.config import Settings
from bot.signals.labels import signal_short_label


INDEX_FIELDNAMES = [
    "run_id",
    "created_at_utc",
    "kind",
    "label",
    "start",
    "end",
    "symbols",
    "signal",
    "margin_usd",
    "leverage",
    "account_cap",
    "symbol_cap",
    "tp_offset_bps",
    "initial_equity",
    "trades",
    "win_rate_pct",
    "net_pnl",
    "roi_pct",
    "max_drawdown_pct",
    "liquidated",
    "near_liquidation",
    "final_open_exposure",
    "stability_pass",
    "avg_monthly_roi_pct",
    "target_month_pct",
    "positive_month_pct",
    "json_path",
    "csv_path",
    "report_path",
]


def settings_snapshot(settings: Settings) -> dict[str, Any]:
    """Snapshot trading config without writing API secrets."""
    return {
        "env": {
            "mode": settings.env.mode.value,
            "log_level": settings.env.log_level,
            "has_api_key": bool(settings.env.bybit_api_key),
            "has_api_secret": bool(settings.env.bybit_api_secret),
        },
        "bot": settings.bot.model_dump(mode="json"),
        "symbols": settings.symbols.model_dump(mode="json"),
    }


def result_summary(result: Any, *, initial_equity: float, include_events: bool = False) -> dict[str, Any]:
    from bot.backtest.monthly import by_month

    monthly = []
    for row in by_month(result):
        monthly.append({
            "period": row.period,
            "trades": row.trades,
            "wins": row.wins,
            "losses": row.losses,
            "win_rate_pct": row.win_rate * 100.0,
            "gross_pnl": row.gross_pnl,
            "fees": row.fees,
            "net_pnl": row.net_pnl,
            "roi_pct": row.net_pnl / initial_equity * 100.0 if initial_equity > 0 else 0.0,
            "max_drawdown": row.max_drawdown_value,
            "max_drawdown_pct": row.max_drawdown_value / initial_equity * 100.0 if initial_equity > 0 else 0.0,
        })

    per_symbol: dict[str, dict[str, Any]] = {}
    for trade in result.trades:
        row = per_symbol.setdefault(
            trade.symbol,
            {"symbol": trade.symbol, "trades": 0, "wins": 0, "losses": 0, "gross_pnl": 0.0, "fees": 0.0},
        )
        row["trades"] += 1
        row["wins"] += 1 if trade.realized_pnl > 0 else 0
        row["losses"] += 1 if trade.realized_pnl < 0 else 0
        row["gross_pnl"] += trade.realized_pnl
    for symbol, row in per_symbol.items():
        row["fees"] = result.fees_for_symbol(symbol)
        row["net_pnl"] = row["gross_pnl"] - row["fees"]

    final_state = {
        symbol: {
            "state": ctx.state.value,
            "direction": ctx.direction.value if ctx.direction is not None else None,
            "position_size": ctx.position_size,
            "bep": ctx.bep,
            "first_fill_ts": ctx.first_fill_ts,
            "pending_entry_link_id": ctx.pending_entry_link_id,
            "halted": ctx.halted,
        }
        for symbol, ctx in sorted(result.final_state.items())
    }

    payload = {
        "trades": len(result.trades),
        "wins": result.wins,
        "losses": result.losses,
        "stopped": result.stopped,
        "win_rate_pct": result.win_rate * 100.0,
        "gross_pnl": result.total_pnl,
        "fees": result.total_fees,
        "net_pnl": result.net_pnl,
        "roi_pct": result.net_pnl / initial_equity * 100.0 if initial_equity > 0 else 0.0,
        "initial_equity": initial_equity,
        "ending_equity": result.ending_equity,
        "max_drawdown": result.max_drawdown,
        "max_drawdown_pct": result.max_drawdown_pct * 100.0,
        "liquidated": result.liquidated,
        "near_liquidation": result.near_liquidation,
        "min_liq_distance_pct": result.min_liq_distance_pct,
        "margin_ratio_max_pct": result.margin_ratio_max * 100.0,
        "worst_unrealized_loss": result.worst_unrealized_loss,
        "time_in_recovery_hours": result.time_in_recovery / 3600.0,
        "final_open_exposure": result.final_open_exposure,
        "max_initial_margin": result.max_initial_margin,
        "min_available_balance": result.min_available_balance,
        "monthly": monthly,
        "per_symbol": sorted(per_symbol.values(), key=lambda row: row["symbol"]),
        "final_state": final_state,
        "execution": {
            "config": _clean(getattr(result, "execution_config", None)),
            "stats": _clean(getattr(result, "execution_stats", None)),
        },
    }
    if include_events:
        payload["trade_records"] = [_clean(trade) for trade in result.trades]
        payload["fills"] = [_clean(fill) for fill in result.fills]
        payload["liquidation_events"] = [_clean(event) for event in result.liquidation_events]
        payload["near_liquidation_events"] = [_clean(event) for event in result.near_liquidation_events]
    return payload


def archive_backtest_result(
    *,
    kind: str,
    settings: Settings,
    start: str,
    end: str,
    symbols: list[str],
    signal_name: str,
    signal_params: Mapping[str, Any],
    initial_equity: float,
    result: Any,
    label: str = "",
    stops: Any = None,
    gates: Any = None,
    stability: Any = None,
    risk_enabled: bool | None = None,
    args: Mapping[str, Any] | None = None,
    outputs: Mapping[str, Any] | None = None,
    extra: Mapping[str, Any] | None = None,
    include_events: bool = True,
    root: str | Path = ".",
) -> Path:
    metrics = result_summary(result, initial_equity=initial_equity, include_events=include_events)
    record = {
        "kind": kind,
        "label": label,
        "scope": {"start": start, "end": end, "symbols": symbols},
        "strategy": {
            "signal_name": signal_name,
            "signal_params": dict(signal_params),
            "risk_enabled": risk_enabled,
            "stops": _clean(stops),
            "gates": _clean(gates),
        },
        "settings": settings_snapshot(settings),
        "args": dict(args or {}),
        "outputs": dict(outputs or {}),
        "metrics": metrics,
        "stability": _clean(stability),
        "extra": dict(extra or {}),
    }
    return archive_record(record, root=root)


def archive_record(record: Mapping[str, Any], *, root: str | Path = ".") -> Path:
    root_path = Path(root)
    created_at = datetime.now(timezone.utc).isoformat()
    payload = _clean(dict(record))
    payload.setdefault("created_at_utc", created_at)
    run_id = payload.get("run_id") or _make_run_id(payload, created_at)
    payload["run_id"] = run_id
    payload.setdefault("command", sys.argv)
    payload.setdefault("git", _git_snapshot(root_path))

    archive_dir = root_path / "data" / "backtests"
    runs_dir = archive_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    json_path = runs_dir / f"{run_id}.json"
    payload["archive"] = {
        "json_path": str(json_path),
        "index_csv": str(archive_dir / "index.csv"),
        "index_jsonl": str(archive_dir / "index.jsonl"),
    }

    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    with (archive_dir / "index.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, sort_keys=True) + "\n")

    _append_index_csv(archive_dir / "index.csv", _index_row(payload, json_path))
    return json_path


def _index_row(payload: Mapping[str, Any], json_path: Path) -> dict[str, Any]:
    scope = payload.get("scope") or {}
    strategy = payload.get("strategy") or {}
    settings = payload.get("settings") or {}
    bot = settings.get("bot") or {}
    sizing = bot.get("sizing") or {}
    risk = bot.get("risk") or {}
    offsets = bot.get("offsets") or {}
    summary = payload.get("summary") or {}
    recommended = summary.get("recommended_settings") or {}
    metrics = payload.get("metrics") or payload.get("summary") or {}
    stability = payload.get("stability") or {}
    outputs = payload.get("outputs") or {}
    symbols = scope.get("symbols") or payload.get("symbols") or ""
    if isinstance(symbols, list):
        symbols = ",".join(str(symbol) for symbol in symbols)
    return {
        "run_id": payload.get("run_id", ""),
        "created_at_utc": payload.get("created_at_utc", ""),
        "kind": payload.get("kind", ""),
        "label": payload.get("label", ""),
        "start": scope.get("start") or payload.get("start", ""),
        "end": scope.get("end") or payload.get("end", ""),
        "symbols": symbols,
        "signal": _signal_label(strategy),
        "margin_usd": recommended.get("margin_usd", sizing.get("margin_usd", "")),
        "leverage": recommended.get("leverage", sizing.get("leverage", "")),
        "account_cap": recommended.get("account_cap", risk.get("max_notional_account_usd", "")),
        "symbol_cap": recommended.get("symbol_cap", risk.get("max_notional_per_symbol_usd", "")),
        "tp_offset_bps": recommended.get("tp_offset_bps", offsets.get("tp_offset_bps", "")),
        "initial_equity": metrics.get("initial_equity", ""),
        "trades": metrics.get("trades", ""),
        "win_rate_pct": metrics.get("win_rate_pct", ""),
        "net_pnl": metrics.get("net_pnl", ""),
        "roi_pct": metrics.get("roi_pct", ""),
        "max_drawdown_pct": metrics.get("max_drawdown_pct", ""),
        "liquidated": metrics.get("liquidated", ""),
        "near_liquidation": metrics.get("near_liquidation", ""),
        "final_open_exposure": metrics.get("final_open_exposure", ""),
        "stability_pass": stability.get("passes", metrics.get("stability_pass", metrics.get("launch_pass", ""))),
        "avg_monthly_roi_pct": stability.get("avg_monthly_roi_pct", metrics.get("avg_monthly_roi_pct", "")),
        "target_month_pct": stability.get("target_month_pct", metrics.get("target_month_pct", "")),
        "positive_month_pct": stability.get("positive_month_pct", metrics.get("positive_month_pct", "")),
        "json_path": str(json_path),
        "csv_path": outputs.get("csv_path") or outputs.get("output_csv") or "",
        "report_path": outputs.get("report_path") or outputs.get("output_report") or "",
    }


def _signal_label(strategy: Mapping[str, Any]) -> str:
    name = strategy.get("signal_name") or strategy.get("signal") or ""
    params = strategy.get("signal_params") or {}
    return signal_short_label(str(name), params)


def _append_index_csv(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rewrite = False
    if path.exists() and path.stat().st_size > 0:
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, [])
        rewrite = header != INDEX_FIELDNAMES
    if rewrite:
        with path.open(newline="", encoding="utf-8") as f:
            old_rows = list(csv.DictReader(f))
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=INDEX_FIELDNAMES, extrasaction="ignore")
            writer.writeheader()
            for old in old_rows:
                writer.writerow(old)
    file_exists = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=INDEX_FIELDNAMES, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def _make_run_id(payload: Mapping[str, Any], created_at: str) -> str:
    kind = str(payload.get("kind") or "backtest")
    safe_kind = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in kind)[:40]
    digest = hashlib.sha1(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()[:10]
    stamp = created_at.replace("-", "").replace(":", "").replace("+", "Z").replace(".", "")
    stamp = stamp[:22]
    return f"{stamp}_{safe_kind}_{digest}"


def _git_snapshot(root: Path) -> dict[str, Any]:
    def run(*cmd: str) -> str:
        return subprocess.check_output(cmd, cwd=root, text=True, stderr=subprocess.DEVNULL, timeout=2).strip()

    try:
        commit = run("git", "rev-parse", "HEAD")
        dirty = bool(run("git", "status", "--short"))
    except Exception:
        return {"available": False}
    return {"available": True, "commit": commit, "dirty": dirty}


def _clean(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, BaseModel):
        return _clean(value.model_dump(mode="json"))
    if is_dataclass(value):
        return _clean(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _clean(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_clean(item) for item in value]
    return str(value)
