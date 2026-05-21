from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from bot.config import load_settings
from bot.monitoring.ai_context import (
    CRITICAL_EVENTS,
    IMPORTANT_EVENTS,
    iter_ai_events,
    latest_log,
)
from bot.monitoring.alerting import (
    AlertingConfig,
    AlertSecrets,
    deliver_if_new,
    load_alert_secrets,
    load_alerting,
    mask_secret,
    save_alert_secrets,
    save_alerting,
    send_test_message,
)
from bot.monitoring.live_monitor import (
    append_monitor_history,
    run_monitor,
    write_alerts_markdown,
    write_monitor_jsonl,
    write_monitor_markdown,
)
from bot.signals.labels import signal_full_label, signal_short_label

SAFE_SIGNALS = (
    "trend_filter",
    "grid",
    "placeholder_rsi",
    "bollinger_bands",
    "ema_crossover",
    "zscore",
    "dual_signal",
    "regime_gate",
    "crash_guard",
)

BANGKOK_TZ = ZoneInfo("Asia/Bangkok")


class DashboardService:
    def __init__(self, root: Path):
        self.root = root
        self.config_dir = root / "config"
        self.reports_dir = root / "reports"
        self.logs_dir = root / "logs"
        self.state_dir = root / "data" / "state"
        self.secrets_dir = root / "data" / "secrets"
        self.history_path = self.logs_dir / "live_monitor_history.jsonl"
        self.alerting_path = self.config_dir / "alerting.yaml"
        self.alert_secrets_path = self.secrets_dir / "alerting.json"
        self.alert_fingerprint_path = self.state_dir / "alert_fingerprint.txt"

    def password(self) -> str | None:
        return os.environ.get("DASHBOARD_PASSWORD") or self._dotenv_value("DASHBOARD_PASSWORD")

    def status(self) -> dict[str, Any]:
        settings = self.safe_settings()
        monitor = self.latest_monitor()
        return {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "kill_active": self.kill_active(),
            "monitor": monitor,
            "settings": settings,
            "alerts": self.read_text(self.reports_dir / "live_alerts.md"),
            "ai_context": self.read_text(self.reports_dir / "live_ai_context.md"),
            "ws_status": self.ws_status(),
        }

    def overview_summary(self) -> dict[str, Any]:
        monitor = self.latest_monitor()
        wallet = monitor.get("wallet") or {}
        positions = monitor.get("positions") or []
        balance = self.balance_summary()
        settings = self.safe_settings()
        symbols = settings.get("symbols", {}).get("active") or []
        sizing = settings.get("sizing") or {}
        risk = settings.get("risk") or {}
        dust_cleanup = settings.get("dust_cleanup") or {}
        longs = sum(1 for p in positions if p.get("side") == "Buy")
        shorts = sum(1 for p in positions if p.get("side") == "Sell")
        open_notional = sum(
            abs(float(p.get("size") or 0.0))
            * float(p.get("mark_price") or p.get("avg_price") or 0.0)
            for p in positions
        )
        return {
            "total_equity": float(wallet.get("total_equity") or 0),
            "daily_pnl": float(monitor.get("daily_closed_pnl") or 0),
            "unrealised_pnl": float(wallet.get("usdt_unrealised_pnl") or 0),
            "available": float(wallet.get("total_available_balance") or 0),
            "severity": monitor.get("severity") or "unknown",
            "kill_active": self.kill_active(),
            "mode": settings.get("mode"),
            "profile": settings.get("profile") or {},
            "active_symbols": symbols,
            "margin_usd": float(sizing.get("margin_usd") or 0),
            "leverage": float(sizing.get("leverage") or 0),
            "notional_per_order": float(sizing.get("margin_usd") or 0) * float(sizing.get("leverage") or 0),
            "max_notional_per_symbol": float(risk.get("max_notional_per_symbol_usd") or 0),
            "max_notional_account": float(risk.get("max_notional_account_usd") or 0),
            "dust_cleanup_enabled": bool(dust_cleanup.get("enabled")),
            "open_positions": len(positions),
            "longs": longs,
            "shorts": shorts,
            "open_notional": open_notional,
            "peak_equity": float(balance.get("peak_equity") or 0),
            "current_drawdown": float(balance.get("current_drawdown") or 0),
            "current_drawdown_pct": float(balance.get("current_drawdown_pct") or 0),
            "max_drawdown": float(balance.get("max_drawdown") or 0),
            "max_drawdown_pct": float(balance.get("max_drawdown_pct") or 0),
            "equity_change_24h": float(balance.get("equity_change_24h") or 0),
            "equity_change_24h_pct": float(balance.get("equity_change_24h_pct") or 0),
            "snapshots": int(balance.get("snapshots") or 0),
        }

    def ws_status(self) -> dict[str, Any] | None:
        path = self.state_dir / "system" / "ws_status.json"
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def safe_settings(self) -> dict[str, Any]:
        profile = self.profile_context()
        config_dir = Path(profile["abs_config_dir"])
        settings = load_settings(config_dir=config_dir)
        bot_yaml = self._read_yaml(config_dir / "bot.yaml")
        symbols_yaml = self._read_yaml(config_dir / "symbols.yaml")
        return {
            "mode": settings.env.mode.value,
            "profile": {k: v for k, v in profile.items() if k != "abs_config_dir"},
            "has_api_key": bool(settings.env.bybit_api_key),
            "has_api_secret": bool(settings.env.bybit_api_secret),
            "sizing": bot_yaml.get("sizing", {}),
            "offsets": bot_yaml.get("offsets", {}),
            "risk": bot_yaml.get("risk", {}),
            "account": bot_yaml.get("account", {}),
            "dust_cleanup": bot_yaml.get("dust_cleanup", {}),
            "signal": bot_yaml.get("signal", {}),
            "loop": bot_yaml.get("loop", {}),
            "symbols": symbols_yaml,
        }

    def profile_context(self) -> dict[str, Any]:
        detected = self._detect_running_config_dir()
        config_dir = detected or self.config_dir
        rel = _display_path(config_dir, self.root)
        name = config_dir.name if config_dir.parent.name == "profiles" else "default"
        return {
            "name": name,
            "label": name.replace("_", " "),
            "config_dir": rel,
            "abs_config_dir": str(config_dir),
            "source": "running process" if detected else "default config",
            "detected": detected is not None,
            "is_default": config_dir.resolve() == self.config_dir.resolve(),
        }

    def _active_config_dir(self) -> Path:
        return Path(self.profile_context()["abs_config_dir"])

    def _detect_running_config_dir(self) -> Path | None:
        try:
            proc = subprocess.run(
                ["ps", "-axo", "command"],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (OSError, subprocess.TimeoutExpired, TypeError):
            return None
        if proc.returncode != 0:
            return None

        for line in proc.stdout.splitlines():
            if " run" not in line:
                continue
            if "bot.main" not in line and "trading-bot" not in line:
                continue
            if "dashboard" in line or "monitor_live" in line:
                continue
            config_arg = _extract_config_dir_arg(line)
            if not config_arg:
                continue
            candidate = Path(config_arg)
            if not candidate.is_absolute():
                candidate = self.root / candidate
            candidate = candidate.resolve()
            if (candidate / "bot.yaml").is_file() and (candidate / "symbols.yaml").is_file():
                return candidate
        return None

    def latest_monitor(self) -> dict[str, Any]:
        path = self.logs_dir / "live_monitor.jsonl"
        if not path.exists():
            return {}
        last = ""
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.strip():
                    last = line
        if not last:
            return {}
        try:
            return json.loads(last)
        except json.JSONDecodeError:
            return {"error": "invalid live_monitor.jsonl"}

    def local_states(self) -> dict[str, dict]:
        states: dict[str, dict] = {}
        if not self.state_dir.exists():
            return states
        for path in sorted(self.state_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            states[path.stem] = data
        return states

    def profile_local_states(self) -> dict[str, dict]:
        active = {str(s).upper() for s in self.safe_settings().get("symbols", {}).get("active") or []}
        return {
            symbol: data
            for symbol, data in self.local_states().items()
            if symbol.upper() in active
        }

    def log_analysis(self, *, bucket_minutes: int = 15, recent_critical: int = 30) -> dict[str, Any]:
        try:
            source = latest_log(self.logs_dir, "*.log")
        except FileNotFoundError:
            return {"available": False, "source": None}

        total = 0
        critical_count = 0
        warning_count = 0
        info_count = 0
        per_event: dict[str, int] = {}
        per_symbol: dict[str, dict[str, Any]] = {}
        per_level: dict[str, int] = {}
        buckets: dict[str, dict[str, int]] = {}
        critical_rows: list[dict[str, Any]] = []
        first_ts: str | None = None
        last_ts: str | None = None
        last_heartbeat: str | None = None
        state_summary: dict[str, str] = {}

        bucket_size = max(1, int(bucket_minutes)) * 60

        for ev in iter_ai_events(source):
            total += 1
            first_ts = first_ts or ev.ts
            last_ts = ev.ts
            level = (ev.level or "info").lower()
            per_level[level] = per_level.get(level, 0) + 1
            if ev.event == "heartbeat":
                last_heartbeat = ev.ts
                states = ev.fields.get("states")
                if states:
                    state_summary["raw"] = states
            per_event[ev.event] = per_event.get(ev.event, 0) + 1

            ts_seconds = _parse_ts_seconds(ev.ts)
            if ts_seconds is not None:
                bucket_key = _bucket_label(ts_seconds, bucket_size)
                b = buckets.setdefault(bucket_key, {"total": 0, "critical": 0, "warning": 0})
                b["total"] += 1

            is_critical = ev.is_critical
            is_warning = level in {"warning", "warn"} and not is_critical
            if is_critical:
                critical_count += 1
                if ts_seconds is not None:
                    buckets[bucket_key]["critical"] += 1  # type: ignore[index]
                critical_rows.append({
                    "ts": ev.ts,
                    "level": level,
                    "event": ev.event,
                    "symbol": ev.symbol or "",
                    "fields": ev.fields,
                })
            elif is_warning:
                warning_count += 1
                if ts_seconds is not None:
                    buckets[bucket_key]["warning"] += 1  # type: ignore[index]
            else:
                info_count += 1

            if ev.symbol:
                row = per_symbol.setdefault(ev.symbol, {"symbol": ev.symbol, "count": 0, "critical": 0, "last_event": "", "last_ts": ""})
                row["count"] += 1
                if is_critical:
                    row["critical"] += 1
                row["last_event"] = ev.event
                row["last_ts"] = ev.ts

        timeline = [
            {"bucket": k, "total": v["total"], "critical": v["critical"], "warning": v["warning"]}
            for k, v in sorted(buckets.items())
        ]

        top_events = [
            {"event": name, "count": count, "is_critical": name in CRITICAL_EVENTS, "is_important": name in IMPORTANT_EVENTS}
            for name, count in sorted(per_event.items(), key=lambda kv: (-kv[1], kv[0]))
        ]
        top_events = top_events[:20]

        per_symbol_rows = sorted(per_symbol.values(), key=lambda r: -r["count"])

        heartbeat_age = None
        if last_heartbeat:
            heartbeat_age = _seconds_since(_parse_ts_seconds(last_heartbeat))

        return {
            "available": True,
            "source": str(source.relative_to(self.root)) if source.is_relative_to(self.root) else str(source),
            "total": total,
            "critical": critical_count,
            "warning": warning_count,
            "info": info_count,
            "first_ts": first_ts,
            "last_ts": last_ts,
            "last_heartbeat_ts": last_heartbeat,
            "heartbeat_age_seconds": heartbeat_age,
            "per_level": per_level,
            "top_events": top_events,
            "per_symbol": per_symbol_rows[:30],
            "timeline": timeline[-96:],  # last ~24h at 15-min buckets
            "recent_critical": critical_rows[-recent_critical:],
        }

    def log_events(self, *, event: str = "", symbol: str = "", limit: int = 120) -> list[dict[str, Any]]:
        try:
            source = latest_log(self.logs_dir, "*.log")
        except FileNotFoundError:
            return []
        rows: list[dict[str, Any]] = []
        for ev in iter_ai_events(source):
            if event and ev.event != event:
                continue
            if symbol and ev.symbol != symbol:
                continue
            rows.append({
                "ts": ev.ts,
                "level": ev.level,
                "event": ev.event,
                "symbol": ev.symbol or "",
                "fields": ev.fields,
                "critical": ev.is_critical,
            })
        return rows[-max(1, min(limit, 500)):]

    def backtest_analysis(
        self,
        *,
        strategies: list[str] | None = None,
        symbols: list[str] | None = None,
        start: str | None = None,
        end: str | None = None,
        min_trades: int = 0,
        min_win_rate_pct: float = 0.0,
        hide_zero_trades: bool = True,
    ) -> dict[str, Any]:
        """Aggregate the research backtest index into a per-run dataset for the Analysis tab.

        Source: `data/backtests/index.jsonl` (rich) with `data/backtests/index.csv` as fallback.
        Each row in `index.jsonl` is a research run; the `sensitivity_results` section
        gives multiple start-date windows per strategy, which we flatten into one row per
        (strategy, window).
        """
        runs = self._load_backtest_index()
        rows: list[dict[str, Any]] = []
        for run in runs:
            rows.extend(self._flatten_research_run(run))

        # Strict deny-list — hide strategies whose name (or ` / `-suffix) matches.
        rows = [r for r in rows if not _strategy_is_hidden(r.get("strategy") or "")]

        strategy_set = {s for s in (strategies or []) if s}
        symbol_set = {s.upper() for s in (symbols or []) if s}
        start_ts = _parse_date(start)
        end_ts = _parse_date(end)

        filtered: list[dict[str, Any]] = []
        for row in rows:
            if strategy_set and row["strategy"] not in strategy_set:
                continue
            if symbol_set and not (symbol_set & set(row["symbols"])):
                continue
            row_start = _parse_date(row.get("start"))
            row_end = _parse_date(row.get("end"))
            if start_ts and row_end and row_end < start_ts:
                continue
            if end_ts and row_start and row_start > end_ts:
                continue
            if min_trades and (row.get("trades") or 0) < min_trades:
                continue
            if hide_zero_trades and (row.get("trades") or 0) <= 0:
                continue
            wr = row.get("win_rate_pct")
            if min_win_rate_pct and (wr is None or wr < min_win_rate_pct):
                continue
            filtered.append(row)

        filtered.sort(key=lambda r: (r["strategy"], r.get("start") or ""))

        all_strategies = sorted({r["strategy"] for r in rows if r["strategy"]})
        all_symbols = sorted({s for r in rows for s in r["symbols"]})

        per_strategy: dict[str, dict[str, Any]] = {}
        for row in filtered:
            strat = row["strategy"]
            bucket = per_strategy.setdefault(strat, {
                "strategy": strat,
                "runs": 0,
                "net_pnl_total": 0.0,
                "trades_total": 0,
                "wins_total": 0,
                "best_roi_pct": None,
                "worst_roi_pct": None,
                "max_drawdown_pct": 0.0,
                "windows": [],
                "config": row.get("config") or {},
                "symbols": list(row.get("symbols") or []),
                "report_path": row.get("report_path"),
            })
            bucket["runs"] += 1
            bucket["net_pnl_total"] += row.get("net_pnl") or 0.0
            bucket["trades_total"] += row.get("trades") or 0
            bucket["wins_total"] += row.get("wins") or 0
            roi = row.get("roi_pct")
            if roi is not None:
                bucket["best_roi_pct"] = roi if bucket["best_roi_pct"] is None else max(bucket["best_roi_pct"], roi)
                bucket["worst_roi_pct"] = roi if bucket["worst_roi_pct"] is None else min(bucket["worst_roi_pct"], roi)
            mdd = row.get("max_drawdown_pct") or 0.0
            if mdd > bucket["max_drawdown_pct"]:
                bucket["max_drawdown_pct"] = mdd
            bucket["windows"].append({
                "start": row.get("start"),
                "end": row.get("end"),
                "roi_pct": roi,
                "net_pnl": row.get("net_pnl"),
                "max_drawdown_pct": row.get("max_drawdown_pct"),
                "trades": row.get("trades"),
                "win_rate_pct": row.get("win_rate_pct"),
                "months": row.get("months"),
                "launch_pass": row.get("launch_pass"),
            })

        summary_rows = []
        for bucket in per_strategy.values():
            avg_roi = None
            roi_values = [w["roi_pct"] for w in bucket["windows"] if w["roi_pct"] is not None]
            if roi_values:
                avg_roi = sum(roi_values) / len(roi_values)
            trades = bucket["trades_total"]
            wr = (bucket["wins_total"] / trades * 100.0) if trades else None
            summary_rows.append({
                "strategy": bucket["strategy"],
                "runs": bucket["runs"],
                "net_pnl_total": bucket["net_pnl_total"],
                "trades_total": trades,
                "win_rate_pct": wr,
                "avg_roi_pct": avg_roi,
                "best_roi_pct": bucket["best_roi_pct"],
                "worst_roi_pct": bucket["worst_roi_pct"],
                "max_drawdown_pct": bucket["max_drawdown_pct"],
                "config": bucket.get("config") or {},
                "symbols": bucket.get("symbols") or [],
                "report_path": bucket.get("report_path"),
                "windows": bucket.get("windows") or [],
            })
        summary_rows.sort(key=lambda r: -(r["net_pnl_total"] or 0.0))

        return {
            "rows": filtered,
            "per_strategy": summary_rows,
            "all_strategies": all_strategies,
            "all_symbols": all_symbols,
            "filters": {
                "strategies": sorted(strategy_set),
                "symbols": sorted(symbol_set),
                "start": start,
                "end": end,
                "min_trades": min_trades,
                "min_win_rate_pct": min_win_rate_pct,
                "hide_zero_trades": hide_zero_trades,
            },
            "total_runs_indexed": len(rows),
        }

    def _load_backtest_index(self) -> list[dict[str, Any]]:
        index_jsonl = self.root / "data" / "backtests" / "index.jsonl"
        runs: list[dict[str, Any]] = []
        if index_jsonl.exists():
            with index_jsonl.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        runs.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return runs

    def _flatten_research_run(self, run: dict[str, Any]) -> list[dict[str, Any]]:
        """One row per (strategy_label, sensitivity-window).

        Falls back to a single row from `summary` if `sensitivity_results` is empty.
        """
        run_id = str(run.get("run_id") or "")
        kind = str(run.get("kind") or "")
        report_path = (run.get("outputs") or {}).get("report_path")
        sensitivity = run.get("sensitivity_results") or {}
        exact = run.get("exact_results") or {}
        settings_signal_block = (run.get("settings") or {}).get("bot", {}).get("signal") or {}
        signal_block = self._run_signal_block(run)
        sensitivity_signal_block = settings_signal_block or signal_block
        rows: list[dict[str, Any]] = []
        for strategy_label, windows in sensitivity.items():
            if not isinstance(windows, list):
                continue
            config = self._strategy_config(
                exact.get(strategy_label) or {},
                sensitivity_signal_block,
                candidate_name=strategy_label,
            )
            for w in windows:
                rows.append(self._build_analysis_row(
                    run_id=run_id,
                    kind=kind,
                    report_path=report_path,
                    strategy=strategy_label,
                    record=w,
                    fallback_symbols=(run.get("scope") or {}).get("symbols") or [],
                    config=config,
                ))
        if rows:
            return rows
        summary_rows = (run.get("summary") or {}).get("rows") or []
        if isinstance(summary_rows, list) and summary_rows:
            signal_label = self._strategy_label(run)
            out: list[dict[str, Any]] = []
            scope = run.get("scope") or {}
            config = self._strategy_config(
                self._candidate_settings(run),
                signal_block,
                candidate_name=signal_label,
            )
            for record in summary_rows:
                if not isinstance(record, dict):
                    continue
                label = str(record.get("label") or record.get("mode") or kind or "summary")
                out.append(self._build_analysis_row(
                    run_id=run_id,
                    kind=kind,
                    report_path=report_path,
                    strategy=f"{signal_label} / {label}",
                    record={
                        **record,
                        "start": scope.get("start"),
                        "end": scope.get("end"),
                        "max_drawdown_pct": record.get("max_drawdown_pct"),
                    },
                    fallback_symbols=scope.get("symbols") or [],
                    config=config,
                ))
            if out:
                return out
        # Fallback: synthesize one row from the run summary.
        summary = run.get("summary") or {}
        metrics = run.get("metrics") or {}
        record = summary if any(k in summary for k in ("roi_pct", "net_pnl", "trades")) else metrics
        scope = run.get("scope") or {}
        rows.append(self._build_analysis_row(
            run_id=run_id,
            kind=kind,
            report_path=report_path,
            strategy=self._strategy_label(run) or kind or "summary",
            record={
                "start": scope.get("start"),
                "end": scope.get("end"),
                "roi_pct": record.get("roi_pct"),
                "net_pnl": record.get("net_pnl"),
                "max_dd_pct": record.get("max_drawdown_pct"),
                "trades": record.get("trades"),
                "wins": record.get("wins"),
                "win_rate_pct": record.get("win_rate_pct"),
                "months": record.get("months"),
            },
            fallback_symbols=scope.get("symbols") or [],
            config=self._strategy_config(
                self._candidate_settings(run),
                signal_block,
                candidate_name=self._strategy_label(run) or kind or "summary",
            ),
        ))
        return rows

    @staticmethod
    def _run_signal_block(run: dict[str, Any]) -> dict[str, Any]:
        strategy = run.get("strategy") or {}
        name = str(strategy.get("signal_name") or strategy.get("signal") or "").strip()
        params = strategy.get("signal_params") or {}
        if name:
            return {"engine": name, "params": params if isinstance(params, dict) else {}}
        return (run.get("settings") or {}).get("bot", {}).get("signal") or {}

    @staticmethod
    def _candidate_settings(run: dict[str, Any]) -> dict[str, Any]:
        summary = run.get("summary") or {}
        settings = run.get("settings") or {}
        bot = settings.get("bot") or {}
        sizing = bot.get("sizing") or {}
        risk = bot.get("risk") or {}
        offsets = bot.get("offsets") or {}
        return {
            **(summary.get("recommended_settings") or {}),
            "margin_usd": sizing.get("margin_usd"),
            "leverage": sizing.get("leverage"),
            "account_cap": risk.get("max_notional_account_usd"),
            "symbol_cap": risk.get("max_notional_per_symbol_usd"),
            "tp_offset_bps": offsets.get("tp_offset_bps"),
            "daily_loss_limit": risk.get("daily_loss_limit_usd"),
        }

    @staticmethod
    def _strategy_label(run: dict[str, Any]) -> str:
        strategy = run.get("strategy") or {}
        name = str(strategy.get("signal_name") or strategy.get("signal") or "").strip()
        params = strategy.get("signal_params") or {}
        if not name:
            signal_block = (run.get("settings") or {}).get("bot", {}).get("signal") or {}
            name = str(signal_block.get("engine") or "").strip()
            params = signal_block.get("params") or {}
        return signal_short_label(name, params)

    @staticmethod
    def _strategy_config(
        candidate: dict[str, Any],
        signal_block: dict[str, Any],
        *,
        candidate_name: str = "",
    ) -> dict[str, Any]:
        engine = str(signal_block.get("engine") or "").strip() or None
        params = signal_block.get("params") or {}
        if isinstance(params, dict):
            params_dict = {str(k): params[k] for k in params}
        else:
            params_dict = {}

        # Apply per-candidate hints extracted from the candidate's *name* — the
        # research index doesn't store true per-candidate signal params, but names like
        # `grid40_trend15`, `grid50_best`, or `latest_grid40` encode the variant.
        inferred = DashboardService._infer_signal_params_from_name(candidate_name)
        inferred_keys: list[str] = []
        for key, value in inferred.items():
            if value is None:
                continue
            if params_dict.get(key) != value:
                inferred_keys.append(key)
            params_dict[key] = value

        params_str_parts = [f"{k}={v}" for k, v in params_dict.items()]
        signal_full = signal_full_label(engine or "", params_dict)
        signal_short = signal_short_label(engine or "", params_dict)
        return {
            "margin_usd": _coerce_float(candidate.get("margin_usd")),
            "leverage": _coerce_int(candidate.get("leverage")),
            "account_cap": _coerce_float(candidate.get("account_cap")),
            "symbol_cap": _coerce_float(candidate.get("symbol_cap")),
            "tp_offset_bps": _coerce_float(candidate.get("tp_offset_bps")),
            "daily_loss_limit": _coerce_float(candidate.get("daily_loss_limit")),
            "signal_engine": engine,
            "signal_params": params_dict,
            "signal_params_str": ":".join(params_str_parts) if params_str_parts else "",
            "signal_full": signal_full,
            "signal_short": signal_short,
            "candidate_name": candidate_name or None,
            "inferred_keys": inferred_keys,
        }

    @staticmethod
    def _infer_signal_params_from_name(name: str) -> dict[str, Any]:
        """Pull grid/trend hints out of a candidate name.

        Returns a partial dict suitable for merging into `signal.params`.
        Known patterns (case-insensitive):
          - `grid<N>` anywhere       -> inner_entry_bps=N, inner_step_bps=N/2
          - `trend<M>` anywhere      -> max_trend_bps=M
        Anything not matched is left to the run-level signal.
        """
        if not name:
            return {}
        text = name.lower()
        out: dict[str, Any] = {}
        m = re.search(r"grid(\d+)", text)
        if m:
            entry = int(m.group(1))
            out["inner_entry_bps"] = entry
            out["inner_step_bps"] = entry // 2 if entry >= 2 else entry
        m = re.search(r"trend(\d+)", text)
        if m:
            out["max_trend_bps"] = int(m.group(1))
        return out

    @staticmethod
    def _build_analysis_row(
        *,
        run_id: str,
        kind: str,
        report_path: str | None,
        strategy: str,
        record: dict[str, Any],
        fallback_symbols: list[str],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        symbols_raw = record.get("symbols") or fallback_symbols
        if isinstance(symbols_raw, str):
            symbols = [s.strip().upper() for s in symbols_raw.split(",") if s.strip()]
        else:
            symbols = [str(s).strip().upper() for s in symbols_raw if str(s).strip()]
        return {
            "run_id": run_id,
            "kind": kind,
            "report_path": report_path,
            "strategy": strategy,
            "start": _coerce_str(record.get("start")),
            "end": _coerce_str(record.get("end")),
            "symbols": symbols,
            "roi_pct": _coerce_float(record.get("roi_pct")),
            "net_pnl": _coerce_float(record.get("net_pnl")),
            "max_drawdown_pct": _coerce_float(
                record.get("max_dd_pct")
                or record.get("max_drawdown_pct")
            ),
            "trades": _coerce_int(record.get("trades")),
            "wins": _coerce_int(record.get("wins")),
            "win_rate_pct": _coerce_float(record.get("win_rate_pct")),
            "months": _coerce_int(record.get("months")),
            "launch_pass": _coerce_bool(record.get("launch_pass") or record.get("launch_pass_bool")),
            "stability_score": _coerce_float(record.get("stability_score")),
            "avg_monthly_roi_pct": _coerce_float(record.get("avg_monthly_roi_pct")),
            "worst_monthly_dd_pct": _coerce_float(record.get("worst_monthly_dd_pct")),
            "config": config or {},
        }

    def backtest_reports(self) -> list[dict[str, Any]]:
        candidates = (
            list(self.reports_dir.rglob("*.md"))
            + list(self.logs_dir.glob("backtest*"))
            + list(self.logs_dir.glob("*.csv"))
        )
        reports = []
        for path in candidates:
            try:
                st = path.stat()
            except OSError:
                continue
            reports.append({
                "path": str(path.relative_to(self.root)),
                "name": path.name,
                "size": st.st_size,
                "modified": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
            })
        return sorted(reports, key=lambda r: r["modified"], reverse=True)[:120]

    def report_text(self, rel_path: str) -> str:
        path = (self.root / rel_path).resolve()
        if self.root.resolve() not in path.parents and path != self.root.resolve():
            raise ValueError("path outside repo")
        if not (path.is_file() and (path.suffix in {".md", ".txt", ".log", ".csv"})):
            raise ValueError("unsupported report")
        return self.read_text(path, max_chars=80_000)

    def create_kill(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        (self.state_dir / "KILL").write_text(
            f"Created by dashboard at {datetime.now(timezone.utc).isoformat()}\n",
            encoding="utf-8",
        )

    def clear_kill(self) -> None:
        try:
            (self.state_dir / "KILL").unlink()
        except FileNotFoundError:
            pass

    def kill_active(self) -> bool:
        return (self.state_dir / "KILL").exists()

    def regenerate_monitor(self, *, tmux_session: str = "", skip_process_check: bool = True) -> dict[str, Any]:
        settings = load_settings(config_dir=self._active_config_dir())
        alerting = self.load_alerting()
        snapshot = run_monitor(
            settings,
            log_dir=self.logs_dir,
            state_dir=self.state_dir,
            tmux_session=tmux_session or None,
            process_pattern=None if skip_process_check else "trading-bot run|bot.main run|python -m bot.main run",
            heartbeat_stale_seconds=alerting.heartbeat_stale_seconds,
            repeated_failure_threshold=alerting.repeated_failure_threshold,
            failure_window_seconds=alerting.failure_window_seconds,
            write_kill=False,
        )
        write_monitor_markdown(snapshot, self.reports_dir / "live_monitor.md")
        write_alerts_markdown(snapshot, self.reports_dir / "live_alerts.md")
        write_monitor_jsonl(snapshot, self.logs_dir / "live_monitor.jsonl")
        append_monitor_history(snapshot, self.history_path)
        delivery: dict[str, Any] = {"delivered": False, "skipped": True, "reason": "disabled"}
        if alerting.enabled:
            secrets = load_alert_secrets(self.alert_secrets_path)
            delivery = deliver_if_new(
                snapshot,
                config=alerting,
                secrets=secrets,
                fingerprint_path=self.alert_fingerprint_path,
            )
        payload = asdict(snapshot)
        payload["delivery"] = delivery
        return payload

    def load_alerting(self) -> AlertingConfig:
        return load_alerting(self.alerting_path)

    def save_alerting_values(self, values: dict[str, Any]) -> dict[str, Any]:
        cfg = AlertingConfig(
            enabled=_bool(values.get("enabled")),
            heartbeat_stale_seconds=_positive_float(values.get("heartbeat_stale_seconds")),
            repeated_failure_threshold=_bounded_int(values.get("repeated_failure_threshold"), 1, 100),
            failure_window_seconds=_positive_float(values.get("failure_window_seconds")),
            daily_loss_alert_usd=_positive_float(values.get("daily_loss_alert_usd")),
            delivery={
                "telegram": {"enabled": _bool(values.get("telegram_enabled"))},
                "discord": {"enabled": _bool(values.get("discord_enabled"))},
            },
        )
        save_alerting(self.alerting_path, cfg)
        return cfg.model_dump()

    def alert_secrets_masked(self) -> dict[str, str]:
        secrets = load_alert_secrets(self.alert_secrets_path)
        return {
            "telegram_bot_token": mask_secret(secrets.telegram_bot_token),
            "telegram_chat_id": mask_secret(secrets.telegram_chat_id),
            "discord_webhook_url": mask_secret(secrets.discord_webhook_url),
        }

    def save_alert_secrets_values(self, values: dict[str, Any]) -> None:
        current = load_alert_secrets(self.alert_secrets_path)
        new = AlertSecrets(
            telegram_bot_token=_keep_or_replace(values.get("telegram_bot_token"), current.telegram_bot_token),
            telegram_chat_id=_keep_or_replace(values.get("telegram_chat_id"), current.telegram_chat_id),
            discord_webhook_url=_keep_or_replace(values.get("discord_webhook_url"), current.discord_webhook_url),
        )
        save_alert_secrets(self.alert_secrets_path, new)

    def test_alert_delivery(
        self,
        channel: str,
        *,
        overrides: dict[str, Any] | None = None,
        client: Any | None = None,
    ) -> dict[str, Any]:
        current = load_alert_secrets(self.alert_secrets_path)
        overrides = overrides or {}
        merged = AlertSecrets(
            telegram_bot_token=_keep_or_replace(
                overrides.get("telegram_bot_token"), current.telegram_bot_token
            ),
            telegram_chat_id=_keep_or_replace(
                overrides.get("telegram_chat_id"), current.telegram_chat_id
            ),
            discord_webhook_url=_keep_or_replace(
                overrides.get("discord_webhook_url"), current.discord_webhook_url
            ),
        )
        try:
            return send_test_message(channel, secrets=merged, client=client)
        except ValueError as exc:
            return {
                "ok": False,
                "channel": channel.strip().lower(),
                "status_code": None,
                "detail": str(exc),
            }

    def equity_history(self, *, limit: int = 500) -> list[dict[str, Any]]:
        if not self.history_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with self.history_path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        if limit and len(rows) > limit:
            rows = rows[-limit:]
        return rows

    def positions_breakdown(self) -> list[dict[str, Any]]:
        monitor = self.latest_monitor()
        out: list[dict[str, Any]] = []
        for pos in monitor.get("positions") or []:
            size = abs(float(pos.get("size") or 0.0))
            price = float(pos.get("mark_price") or pos.get("avg_price") or 0.0)
            notional = size * price
            if notional <= 0:
                continue
            out.append({"symbol": pos.get("symbol", ""), "notional": notional, "side": pos.get("side", "")})
        return out

    def balance_summary(self) -> dict[str, Any]:
        history = self.equity_history()
        monitor = self.latest_monitor()
        wallet = monitor.get("wallet") or {}
        positions = monitor.get("positions") or []

        current_equity = float(wallet.get("total_equity") or 0.0)
        current_available = float(wallet.get("total_available_balance") or 0.0)
        current_unrealised = float(wallet.get("usdt_unrealised_pnl") or 0.0)
        current_realised_cum = float(wallet.get("usdt_cum_realised_pnl") or 0.0)
        margin_in_use = max(0.0, current_equity - current_available)
        margin_utilization_pct = (margin_in_use / current_equity * 100.0) if current_equity > 0 else 0.0

        # Peak / drawdown / 24h delta from history.
        peak = 0.0
        peak_ts: str | None = None
        max_dd = 0.0
        max_dd_pct = 0.0
        max_dd_ts: str | None = None
        last_equity = current_equity
        ts_24h_back = time.time() - 86400.0
        equity_24h_ago: float | None = None
        period_high = current_equity
        period_low = current_equity if current_equity else None
        snapshots = len(history)

        running_peak = 0.0
        for row in history:
            eq = float(row.get("total_equity") or 0.0)
            if eq <= 0:
                continue
            row_ts_s = _parse_ts_seconds(row.get("ts"))
            if eq > running_peak:
                running_peak = eq
                if eq > peak:
                    peak = eq
                    peak_ts = row.get("ts")
            dd = max(0.0, running_peak - eq)
            dd_pct = (dd / running_peak * 100.0) if running_peak > 0 else 0.0
            if dd_pct > max_dd_pct:
                max_dd = dd
                max_dd_pct = dd_pct
                max_dd_ts = row.get("ts")
            if row_ts_s is not None and equity_24h_ago is None and row_ts_s >= ts_24h_back:
                equity_24h_ago = eq
            if period_low is None or eq < period_low:
                period_low = eq
            if eq > period_high:
                period_high = eq
            last_equity = eq

        if equity_24h_ago is None and history:
            equity_24h_ago = float(history[0].get("total_equity") or 0.0)

        equity_change_24h = current_equity - (equity_24h_ago or 0.0) if equity_24h_ago else 0.0
        equity_change_24h_pct = (
            equity_change_24h / equity_24h_ago * 100.0 if equity_24h_ago else 0.0
        )

        if peak > 0:
            current_dd = max(0.0, peak - current_equity)
            current_dd_pct = current_dd / peak * 100.0
        else:
            current_dd = 0.0
            current_dd_pct = 0.0

        # Daily PnL aggregation from history snapshots.
        daily: dict[str, dict[str, float]] = {}
        for row in history:
            ts = row.get("ts") or ""
            day = ts[:10] if isinstance(ts, str) else ""
            if not day:
                continue
            d = daily.setdefault(day, {"realised_first": None, "realised_last": None, "daily_closed_last": 0.0})  # type: ignore[assignment]
            d_first = d.get("realised_first")
            realised = row.get("usdt_cum_realised_pnl")
            if realised is None:
                realised = 0.0
            if d_first is None:
                d["realised_first"] = float(realised)
            d["realised_last"] = float(realised)
            d["daily_closed_last"] = float(row.get("daily_closed_pnl") or 0.0)

        daily_rows = []
        for day in sorted(daily.keys()):
            d = daily[day]
            realised_delta = (d["realised_last"] or 0.0) - (d["realised_first"] or 0.0)
            daily_rows.append({
                "day": day,
                "realised_delta": realised_delta,
                "daily_closed_pnl": d["daily_closed_last"],
            })

        per_symbol_unrealised = []
        for p in positions:
            symbol = p.get("symbol", "")
            upnl = float(p.get("unrealised_pnl") or 0.0)
            size = abs(float(p.get("size") or 0.0))
            mark = float(p.get("mark_price") or p.get("avg_price") or 0.0)
            per_symbol_unrealised.append({
                "symbol": symbol,
                "side": p.get("side", ""),
                "notional": size * mark,
                "unrealised_pnl": upnl,
            })
        per_symbol_unrealised.sort(key=lambda r: -r["unrealised_pnl"])

        return {
            "current_equity": current_equity,
            "current_available": current_available,
            "current_unrealised": current_unrealised,
            "current_realised_cum": current_realised_cum,
            "margin_in_use": margin_in_use,
            "margin_utilization_pct": margin_utilization_pct,
            "equity_change_24h": equity_change_24h,
            "equity_change_24h_pct": equity_change_24h_pct,
            "peak_equity": peak,
            "peak_ts": peak_ts,
            "current_drawdown": current_dd,
            "current_drawdown_pct": current_dd_pct,
            "max_drawdown": max_dd,
            "max_drawdown_pct": max_dd_pct,
            "max_drawdown_ts": max_dd_ts,
            "period_high": period_high,
            "period_low": period_low or 0.0,
            "snapshots": snapshots,
            "daily_pnl": daily_rows[-30:],
            "per_symbol_unrealised": per_symbol_unrealised,
            "history": history,
        }

    def trading_overview(self) -> dict[str, Any]:
        monitor = self.latest_monitor()
        positions = monitor.get("positions") or []
        orders = monitor.get("open_orders") or []
        local_states = self.local_states()
        leverage = float(self.safe_settings().get("sizing", {}).get("leverage") or 1.0) or 1.0

        # Index TP / merge orders per (symbol, side) for fast join.
        tp_index: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for o in orders:
            if not _truthy(o.get("reduce_only")):
                continue
            if (o.get("purpose") or "") not in {"tp", "merge"}:
                continue
            key = (o.get("symbol", ""), o.get("side", ""))
            tp_index.setdefault(key, []).append(o)

        rows: list[dict[str, Any]] = []
        totals = {
            "open_notional": 0.0,
            "unrealised_pnl": 0.0,
            "longs": 0,
            "shorts": 0,
            "winners": 0,
            "losers": 0,
            "pending_tps": 0,
            "merges": 0,
            "entries": 0,
        }
        for pos in positions:
            symbol = pos.get("symbol", "")
            side = pos.get("side", "")
            size = abs(float(pos.get("size") or 0.0))
            avg = float(pos.get("avg_price") or 0.0)
            mark = float(pos.get("mark_price") or avg)
            upnl = float(pos.get("unrealised_pnl") or 0.0)
            notional = size * (mark or avg)
            margin = (notional / leverage) if leverage > 0 else notional

            exit_side = "Sell" if side == "Buy" else "Buy"
            tps = tp_index.get((symbol, exit_side), [])
            tp_qty = sum(float(o.get("qty") or 0.0) for o in tps)
            tp_price = None
            tp_distance_pct: float | None = None
            if tps:
                # Weighted average TP price by qty for display.
                tp_price = (
                    sum(float(o.get("price") or 0.0) * float(o.get("qty") or 0.0) for o in tps)
                    / tp_qty
                ) if tp_qty else float(tps[0].get("price") or 0.0)
                if mark > 0 and tp_price > 0:
                    tp_distance_pct = (tp_price - mark) / mark * 100.0

            price_diff_pct = 0.0
            if avg > 0:
                price_diff_pct = (mark - avg) / avg * 100.0
                if side == "Sell":
                    price_diff_pct = -price_diff_pct  # signed in position direction

            roi_pct = (upnl / margin * 100.0) if margin > 0 else 0.0
            state_data = local_states.get(symbol) or {}

            row = {
                "symbol": symbol,
                "side": side,
                "state": state_data.get("state", ""),
                "size": size,
                "avg_price": avg,
                "bep_local": state_data.get("bep"),
                "mark_price": mark,
                "price_diff_pct": price_diff_pct,
                "notional": notional,
                "margin": margin,
                "unrealised_pnl": upnl,
                "roi_pct": roi_pct,
                "tp_price": tp_price,
                "tp_distance_pct": tp_distance_pct,
                "pending_tps": len(tps),
                "updated_at": state_data.get("updated_at", ""),
            }
            rows.append(row)

            totals["open_notional"] += notional
            totals["unrealised_pnl"] += upnl
            if side == "Buy":
                totals["longs"] += 1
            elif side == "Sell":
                totals["shorts"] += 1
            if upnl > 0:
                totals["winners"] += 1
            elif upnl < 0:
                totals["losers"] += 1
            totals["pending_tps"] += len(tps)

        for o in orders:
            purpose = o.get("purpose", "")
            if purpose == "entry":
                totals["entries"] += 1
            elif purpose == "merge":
                totals["merges"] += 1

        rows.sort(key=lambda r: -r["notional"])
        best = max(rows, key=lambda r: r["unrealised_pnl"]) if rows else None
        worst = min(rows, key=lambda r: r["unrealised_pnl"]) if rows else None
        return {
            "rows": rows,
            "totals": totals,
            "leverage": leverage,
            "daily_closed_pnl": monitor.get("daily_closed_pnl"),
            "best": best,
            "worst": worst,
            "pnl_by_symbol": [
                {"symbol": r["symbol"], "unrealised_pnl": r["unrealised_pnl"]} for r in rows
            ],
            "performance": self.trade_performance_by_symbol(
                positions=positions,
                local_states=local_states,
                monitor=monitor,
            ),
        }

    def trade_performance_by_symbol(
        self,
        *,
        positions: list[dict[str, Any]] | None = None,
        local_states: dict[str, dict] | None = None,
        monitor: dict[str, Any] | None = None,
        recent_limit: int = 50,
    ) -> dict[str, Any]:
        symbols = self._trading_symbols(positions=positions, local_states=local_states)
        monitor_fallback = _performance_from_monitor_closed_pnl(
            monitor or self.latest_monitor(),
            symbols=symbols,
        )
        try:
            source = latest_log(self.logs_dir, "*.log")
        except FileNotFoundError:
            if monitor_fallback is not None:
                return monitor_fallback
            return {
                "available": False,
                "source": None,
                "rows": [_finalize_trade_stats(_empty_trade_stats(symbol)) for symbol in symbols],
                "recent_trades": [],
                "priced_trades": 0,
                "unpriced_exits": 0,
            }

        stats = {symbol: _empty_trade_stats(symbol) for symbol in symbols}
        open_lots: dict[str, list[dict[str, float | str | None]]] = {}
        recent: list[dict[str, Any]] = []

        for ev in iter_ai_events(source):
            symbol = (ev.symbol or _field_text(ev.fields, "symbol") or "").upper()
            if not symbol:
                continue
            if symbol not in stats:
                continue

            name = ev.event.lower().replace(".", "_").replace("-", "_")
            purpose = _event_purpose(ev)
            if _is_entry_fill_event(name, purpose):
                qty = _field_float(
                    ev.fields,
                    "qty",
                    "exec_qty",
                    "execQty",
                    "size",
                    "order_qty",
                    "orderQty",
                )
                price = _field_float(
                    ev.fields,
                    "price",
                    "exec_price",
                    "execPrice",
                    "avg_price",
                    "avgPrice",
                )
                direction = _entry_direction_from_event(ev)
                stats[symbol]["entries"] += 1
                if qty and qty > 0 and price and price > 0 and direction:
                    open_lots.setdefault(symbol, []).append({
                        "qty": abs(qty),
                        "price": price,
                        "direction": direction,
                        "ts": ev.ts,
                    })
                continue

            if not _is_exit_fill_event(name, purpose):
                continue

            qty = _field_float(
                ev.fields,
                "qty",
                "exec_qty",
                "execQty",
                "size",
                "order_qty",
                "orderQty",
            )
            exit_price = _field_float(
                ev.fields,
                "price",
                "exec_price",
                "execPrice",
                "avg_price",
                "avgPrice",
            )
            pnl = _field_float(
                ev.fields,
                "pnl",
                "profit",
                "realized_pnl",
                "realised_pnl",
                "realizedPnl",
                "realisedPnl",
                "closed_pnl",
                "closedPnl",
            )
            direction = _exit_direction_from_event(ev)
            avg_entry: float | None = None

            if pnl is None and qty and qty > 0 and exit_price and exit_price > 0:
                pnl, avg_entry = _close_open_lots(
                    open_lots.get(symbol, []),
                    abs(qty),
                    exit_price,
                    direction,
                )
                fee = _field_float(ev.fields, "fee", "exec_fee", "execFee")
                if pnl is not None and fee:
                    pnl -= abs(fee)

            stats[symbol]["exits"] += 1
            if pnl is None:
                stats[symbol]["unpriced_exits"] += 1
                continue

            trade = _record_trade_stats(
                stats[symbol],
                ts=ev.ts,
                purpose=purpose or name,
                qty=abs(qty or 0.0),
                entry_price=avg_entry,
                exit_price=exit_price,
                direction=direction,
                pnl=pnl,
            )
            recent.append(trade)

        rows = [_finalize_trade_stats(row) for row in stats.values()]
        rows.sort(key=lambda r: (-r["trades"], r["symbol"]))
        priced_trades = sum(int(r["trades"]) for r in rows)
        unpriced_exits = sum(int(r["unpriced_exits"]) for r in rows)
        recent.sort(key=lambda r: _parse_ts_seconds(r.get("ts")) or 0.0, reverse=True)
        if priced_trades == 0 and monitor_fallback is not None:
            return monitor_fallback
        try:
            source_label = str(source.relative_to(self.root))
        except ValueError:
            source_label = str(source)
        return {
            "available": True,
            "source": source_label,
            "rows": rows,
            "recent_trades": recent[:recent_limit],
            "priced_trades": priced_trades,
            "unpriced_exits": unpriced_exits,
        }

    def _trading_symbols(
        self,
        *,
        positions: list[dict[str, Any]] | None = None,
        local_states: dict[str, dict] | None = None,
    ) -> list[str]:
        out: list[str] = []

        def add(symbol: Any) -> None:
            text = str(symbol or "").strip().upper()
            if text and text not in out:
                out.append(text)

        active = {str(s).strip().upper() for s in self.safe_settings().get("symbols", {}).get("active") or []}
        for symbol in sorted(active):
            add(symbol)
        for pos in positions or []:
            add(pos.get("symbol"))
        for symbol in (local_states or {}).keys():
            if symbol.upper() in active:
                add(symbol)
        return out

    def backtest_csv(self, rel_path: str) -> dict[str, Any]:
        path = (self.root / rel_path).resolve()
        root_resolved = self.root.resolve()
        if root_resolved not in path.parents and path != root_resolved:
            raise ValueError("path outside repo")
        if not path.is_file() or path.suffix.lower() != ".csv":
            raise ValueError("not a csv file")
        rows: list[dict[str, str]] = []
        import csv

        with path.open("r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            for row in reader:
                rows.append(row)
                if len(rows) >= 5000:
                    break
        return {"headers": headers, "rows": rows}

    def restart_bot(
        self,
        *,
        tmux_session: str = "testnet_dry_run",
        confirm: str,
    ) -> dict[str, Any]:
        if confirm != "RESTART":
            raise ValueError("type RESTART to confirm")
        if not re.fullmatch(r"[A-Za-z0-9_\-]{1,64}", tmux_session):
            raise ValueError("session name must match [A-Za-z0-9_-]{1,64}")

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_rel = f"logs/testnet_dry_run_{ts}.log"
        log_abs = self.root / log_rel
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # 1. Graceful SIGTERM to the bot process (if running).
        subprocess.run(
            ["pkill", "-TERM", "-f", "bot.main run"],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        # Give the orchestrator a moment to flush state and close WS.
        time.sleep(3)
        # 2. Tear down any leftover tmux session.
        subprocess.run(
            ["tmux", "kill-session", "-t", tmux_session],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        # 3. Start a fresh tmux session with the run command + new log.
        cmd_str = f".venv/bin/python3 -u -m bot.main run 2>&1 | tee {log_rel}"
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", tmux_session, "-c", str(self.root), cmd_str],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return {
            "tmux_session": tmux_session,
            "log_path": log_rel,
            "log_abs": str(log_abs),
        }

    def regenerate_ai_context(self) -> None:
        source_log = latest_log(self.logs_dir, "*.log")
        from bot.monitoring.ai_context import build_context, write_jsonl, write_markdown

        context = build_context(source_log, monitor_report=self.reports_dir / "live_monitor.md")
        write_markdown(context, self.reports_dir / "live_ai_context.md")
        write_jsonl(context, self.logs_dir / "ai_context.jsonl")

    def preview_config(self, values: dict[str, Any]) -> dict[str, Any]:
        config_dir = self._active_config_dir()
        bot_yaml = self._read_yaml(config_dir / "bot.yaml")
        symbols_yaml = self._read_yaml(config_dir / "symbols.yaml")
        updated_bot = json.loads(json.dumps(bot_yaml))
        updated_symbols = json.loads(json.dumps(symbols_yaml))

        updated_bot.setdefault("sizing", {})["margin_usd"] = _positive_float(values.get("margin_usd"))
        updated_bot.setdefault("sizing", {})["leverage"] = _bounded_int(values.get("leverage"), 1, 100)
        updated_bot.setdefault("offsets", {})["entry_offset_bps"] = _nonnegative_float(values.get("entry_offset_bps"))
        updated_bot.setdefault("offsets", {})["tp_offset_bps"] = _positive_float(values.get("tp_offset_bps"))
        updated_bot.setdefault("risk", {})["max_notional_per_symbol_usd"] = _positive_float(values.get("max_notional_per_symbol_usd"))
        updated_bot.setdefault("risk", {})["max_notional_account_usd"] = _positive_float(values.get("max_notional_account_usd"))
        updated_bot.setdefault("risk", {})["daily_loss_limit_usd"] = _positive_float(values.get("daily_loss_limit_usd"))
        active = [s.strip().upper() for s in str(values.get("active_symbols", "")).split(",") if s.strip()]
        if not active:
            raise ValueError("active_symbols must not be empty")
        updated_symbols["active"] = active

        return {
            "config_dir": _display_path(config_dir, self.root),
            "bot_yaml": yaml.safe_dump(updated_bot, sort_keys=False),
            "symbols_yaml": yaml.safe_dump(updated_symbols, sort_keys=False),
        }

    def save_config(self, values: dict[str, Any]) -> None:
        config_dir = self._active_config_dir()
        preview = self.preview_config(values)
        (config_dir / "bot.yaml").write_text(preview["bot_yaml"], encoding="utf-8")
        (config_dir / "symbols.yaml").write_text(preview["symbols_yaml"], encoding="utf-8")

    def start_backtest(self, values: dict[str, Any]) -> dict[str, Any]:
        start = _date(values.get("start"))
        end = _date(values.get("end"))
        defaults = self.safe_settings()
        active_default = defaults["symbols"]["active"]
        symbols = _collect_symbols(values, active_default)
        initial_equity = _optional_positive_float(values.get("initial_equity"))
        if initial_equity is None:
            initial_equity = _positive_float((defaults.get("account") or {}).get("initial_equity"))
        signal_engine = str(values.get("signal_engine") or "").strip()
        signal_params = str(values.get("signal_params") or "").strip().lstrip(":")
        raw_signal = str(values.get("signal") or "").strip()
        if not signal_engine and raw_signal:
            signal_engine = raw_signal.split(":", 1)[0]
            signal_params = signal_params or raw_signal.split(":", 1)[1] if ":" in raw_signal else signal_params
        if not signal_engine:
            signal_block = defaults.get("signal") or {}
            signal_engine = str(signal_block.get("engine") or "").strip()
            params = signal_block.get("params") or {}
            signal_params = _params_to_signal_params_str(params) if isinstance(params, dict) else ""
        if signal_engine and signal_engine not in SAFE_SIGNALS:
            raise ValueError("unsupported signal")
        signal_param_dict = _parse_param_string(signal_params)
        signal = signal_full_label(signal_engine, signal_param_dict)
        signal_short = signal_short_label(signal_engine, signal_param_dict)

        ts = int(time.time())
        log_path = self.logs_dir / f"dashboard_backtest_{ts}.txt"
        report_path = self.reports_dir / f"dashboard_backtest_{ts}.md"
        registry_path = self.state_dir / "backtests" / f"{ts}.json"

        cmd = [
            "uv", "run", "trading-bot", "backtest",
            "--start", start,
            "--end", end,
            "--symbols", ",".join(symbols),
            "--initial-equity", str(initial_equity),
            "--by-month",
            "--with-risk",
        ]
        cmd.extend(["--signal", signal])

        resolved = {
            "--margin-usd": _resolve_optional_positive_float(
                values.get("margin_usd"), (defaults.get("sizing") or {}).get("margin_usd")
            ),
            "--leverage": _resolve_optional_bounded_int(
                values.get("leverage"), (defaults.get("sizing") or {}).get("leverage"), 1, 100
            ),
            "--max-notional-account": _resolve_optional_positive_float(
                values.get("max_notional_account"),
                (defaults.get("risk") or {}).get("max_notional_account_usd"),
            ),
            "--max-notional-per-symbol": _resolve_optional_positive_float(
                values.get("max_notional_per_symbol"),
                (defaults.get("risk") or {}).get("max_notional_per_symbol_usd"),
            ),
            "--tp-offset-bps": _resolve_optional_positive_float(
                values.get("tp_offset_bps"), (defaults.get("offsets") or {}).get("tp_offset_bps")
            ),
            "--daily-loss-limit": _resolve_optional_positive_float(
                values.get("daily_loss_limit"), (defaults.get("risk") or {}).get("daily_loss_limit_usd")
            ),
        }
        for flag, val in resolved.items():
            cmd.extend([flag, str(val)])

        spec = {
            "ts": str(ts),
            "cmd": cmd,
            "log_path": str(log_path.relative_to(self.root)),
            "report_path": str(report_path.relative_to(self.root)),
            "registry_path": str(registry_path.relative_to(self.root)),
            "summary": {
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "signal": signal,
                "signal_short": signal_short,
                "symbols": symbols,
                "start": start,
                "end": end,
                "initial_equity": initial_equity,
                "margin_usd": resolved["--margin-usd"],
                "leverage": resolved["--leverage"],
                "max_notional_account": resolved["--max-notional-account"],
                "max_notional_per_symbol": resolved["--max-notional-per-symbol"],
                "tp_offset_bps": resolved["--tp-offset-bps"],
                "daily_loss_limit": resolved["--daily-loss-limit"],
                "signal_engine": signal_engine,
                "signal_params": signal_params,
                "signal_full": signal,
                "command": " ".join(cmd),
            },
        }
        spec_path = self.state_dir / "backtests" / f"{ts}.spec.json"
        spec_path.parent.mkdir(parents=True, exist_ok=True)
        spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
        registry_path.write_text(
            json.dumps({"status": "queued", "ts": ts, **spec["summary"]}, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        runner = self.root / "scripts" / "dashboard_backtest_runner.py"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen(
            ["uv", "run", "python", str(runner), str(spec_path)],
            cwd=self.root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return {
            "pid": proc.pid,
            "ts": ts,
            "log": str(log_path.relative_to(self.root)),
            "report": str(report_path.relative_to(self.root)),
            "registry": str(registry_path.relative_to(self.root)),
            "cmd": cmd,
        }

    def list_backtest_jobs(
        self,
        *,
        limit: int = 30,
        stale_started_seconds: float = 1800.0,
        stale_log_seconds: float = 300.0,
    ) -> list[dict[str, Any]]:
        directory = self.state_dir / "backtests"
        if not directory.exists():
            return []
        all_rows: list[dict[str, Any]] = []
        for path in sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            if path.name.endswith(".spec.json"):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            data["ts"] = data.get("ts") or path.stem
            data["registry"] = str(path.relative_to(self.root))
            all_rows.append(data)

        # Dedup shard rows: same (shard_index, shard_count) keeps the row with the largest ts.
        kept: dict[tuple[int, int], dict[str, Any]] = {}
        out: list[dict[str, Any]] = []
        for row in all_rows:
            shard_index = row.get("shard_index")
            shard_count = row.get("shard_count")
            if isinstance(shard_index, int) and isinstance(shard_count, int):
                key = (shard_index, shard_count)
                existing = kept.get(key)
                if existing is None:
                    kept[key] = row
                else:
                    try:
                        if int(row.get("ts", 0)) > int(existing.get("ts", 0)):
                            kept[key] = row
                    except (TypeError, ValueError):
                        pass
            else:
                out.append(row)
        out.extend(kept.values())
        # Preserve newest-first ordering by ts.
        out.sort(key=lambda r: int(r.get("ts", 0) or 0), reverse=True)

        # Mark stale: status=running, started long ago, no report, and log file is missing or idle.
        now = time.time()
        shard_processes = _batch_shard_process_statuses()
        for row in out:
            if row.get("status") != "running":
                continue
            started_at = row.get("started_at")
            if not isinstance(started_at, (int, float)):
                continue
            if now - float(started_at) < stale_started_seconds:
                continue
            report_rel = row.get("report_path")
            if report_rel and (self.root / report_rel).exists():
                continue
            shard_index = row.get("shard_index")
            if isinstance(shard_index, int) and shard_index in shard_processes:
                process_status = shard_processes[shard_index]
                row["process_status"] = process_status
                if process_status.startswith("T"):
                    row["status"] = "paused"
                continue
            log_rel = row.get("log_path")
            log_fresh = False
            if log_rel:
                log_path = self.root / log_rel
                try:
                    log_fresh = (now - log_path.stat().st_mtime) < stale_log_seconds
                except OSError:
                    log_fresh = False
            if not log_fresh:
                row["status"] = "stale"

        return out[:limit]

    def available_signals(self) -> list[str]:
        return list(SAFE_SIGNALS)

    def read_text(self, path: Path, *, max_chars: int = 40_000) -> str:
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            return text[:max_chars] + "\n... truncated ..."
        return text

    def _read_yaml(self, path: Path) -> dict[str, Any]:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}

    def _dotenv_value(self, key: str) -> str | None:
        path = self.root / ".env"
        if not path.exists():
            return None
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == key:
                return v.strip().strip('"').strip("'")
        return None


def _batch_shard_process_statuses() -> dict[int, str]:
    try:
        out = subprocess.run(
            ["ps", "-A", "-o", "pid=,stat=,args="],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
    except OSError:
        return {}
    statuses: dict[int, str] = {}
    for line in out.splitlines():
        text = line.strip()
        if not text:
            continue
        parts = text.split(None, 2)
        if len(parts) < 3:
            continue
        _pid, stat, args = parts
        if args.lstrip().startswith("uv "):
            continue
        if "batch_optimize_stability.py" not in args:
            continue
        match = re.search(r"--shard-index\s+(\d+)(?!\d)", args)
        if match:
            statuses[int(match.group(1))] = stat
    return statuses


def _empty_trade_stats(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "entries": 0,
        "exits": 0,
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "breakeven": 0,
        "unpriced_exits": 0,
        "realised_pnl": 0.0,
        "best_trade": None,
        "worst_trade": None,
        "avg_pnl": 0.0,
        "winrate_pct": None,
        "max_drawdown": 0.0,
        "max_drawdown_pct": None,
        "last_closed_at": None,
        "_running_pnl": 0.0,
        "_peak_pnl": 0.0,
    }


def _performance_from_monitor_closed_pnl(
    monitor: dict[str, Any],
    *,
    symbols: list[str],
) -> dict[str, Any] | None:
    raw = monitor.get("daily_closed_pnl_by_symbol")
    if not isinstance(raw, dict):
        return None

    rows: list[dict[str, Any]] = []
    recent: list[dict[str, Any]] = []
    known = list(symbols)

    for symbol in known:
        source = raw.get(symbol) or {}
        if not isinstance(source, dict):
            source = {}
        row = _empty_trade_stats(symbol)
        trades = int(source.get("trades") or 0)
        row.update({
            "entries": trades,
            "exits": trades,
            "trades": trades,
            "wins": int(source.get("wins") or 0),
            "losses": int(source.get("losses") or 0),
            "breakeven": int(source.get("breakeven") or 0),
            "realised_pnl": float(source.get("realised_pnl") or 0.0),
            "best_trade": source.get("best_trade"),
            "worst_trade": source.get("worst_trade"),
            "max_drawdown": float(source.get("max_drawdown") or 0.0),
            "max_drawdown_pct": source.get("max_drawdown_pct"),
            "last_closed_at": source.get("last_closed_at"),
        })
        rows.append(_finalize_trade_stats(row))
        source_recent = source.get("recent_trades")
        if isinstance(source_recent, list):
            for trade in source_recent:
                if isinstance(trade, dict):
                    recent.append(_with_display_trade_time(trade))

    rows.sort(key=lambda r: (-r["trades"], r["symbol"]))
    priced_trades = sum(int(r["trades"]) for r in rows)
    recent.sort(key=lambda r: _parse_ts_seconds(r.get("ts")) or 0.0, reverse=True)
    return {
        "available": True,
        "source": "logs/live_monitor.jsonl daily closed PnL",
        "rows": rows,
        "recent_trades": recent[:50],
        "priced_trades": priced_trades,
        "unpriced_exits": 0,
    }


def _finalize_trade_stats(row: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in row.items() if not k.startswith("_")}
    trades = int(out["trades"])
    if trades:
        out["avg_pnl"] = float(out["realised_pnl"]) / trades
        out["winrate_pct"] = float(out["wins"]) / trades * 100.0
    peak = float(row.get("_peak_pnl") or 0.0)
    if peak > 0:
        out["max_drawdown_pct"] = float(out["max_drawdown"]) / peak * 100.0
    return out


def _record_trade_stats(
    row: dict[str, Any],
    *,
    ts: str,
    purpose: str,
    qty: float,
    entry_price: float | None,
    exit_price: float | None,
    direction: str | None,
    pnl: float,
) -> dict[str, Any]:
    row["trades"] += 1
    row["realised_pnl"] += pnl
    if pnl > 0:
        row["wins"] += 1
    elif pnl < 0:
        row["losses"] += 1
    else:
        row["breakeven"] += 1
    row["best_trade"] = pnl if row["best_trade"] is None else max(float(row["best_trade"]), pnl)
    row["worst_trade"] = pnl if row["worst_trade"] is None else min(float(row["worst_trade"]), pnl)
    row["last_closed_at"] = ts
    row["_running_pnl"] += pnl
    row["_peak_pnl"] = max(float(row["_peak_pnl"]), float(row["_running_pnl"]))
    row["max_drawdown"] = max(
        float(row["max_drawdown"]),
        float(row["_peak_pnl"]) - float(row["_running_pnl"]),
    )
    return {
        "ts": ts,
        **_display_trade_time(ts),
        "symbol": row["symbol"],
        "purpose": purpose,
        "direction": direction,
        "qty": qty,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "pnl": pnl,
    }


def _with_display_trade_time(trade: dict[str, Any]) -> dict[str, Any]:
    out = dict(trade)
    out.update(_display_trade_time(out.get("ts")))
    return out


def _display_trade_time(ts: Any) -> dict[str, str]:
    text = str(ts or "").strip()
    if not text:
        return {"display_date": "n/a", "display_time": ""}
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return {"display_date": text, "display_time": ""}
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(BANGKOK_TZ)
    return {
        "display_date": f"{dt.strftime('%b')} {dt.day}, {dt.year}",
        "display_time": f"{dt.strftime('%H:%M:%S')} ICT",
    }


def _close_open_lots(
    lots: list[dict[str, float | str | None]],
    qty: float,
    exit_price: float,
    direction: str | None,
) -> tuple[float | None, float | None]:
    remaining = qty
    pnl = 0.0
    entry_notional = 0.0
    matched_qty = 0.0

    while remaining > 1e-12 and lots:
        idx = _matching_lot_index(lots, direction)
        if idx is None:
            break
        lot = lots[idx]
        lot_qty = float(lot.get("qty") or 0.0)
        if lot_qty <= 0:
            lots.pop(idx)
            continue
        take = min(remaining, lot_qty)
        entry_price = float(lot.get("price") or 0.0)
        lot_direction = str(lot.get("direction") or direction or "").upper()
        if lot_direction == "SHORT":
            pnl += (entry_price - exit_price) * take
        else:
            pnl += (exit_price - entry_price) * take
        entry_notional += entry_price * take
        matched_qty += take
        remaining -= take
        lot["qty"] = lot_qty - take
        if float(lot["qty"] or 0.0) <= 1e-12:
            lots.pop(idx)

    if matched_qty <= 0:
        return None, None
    return pnl, entry_notional / matched_qty


def _matching_lot_index(
    lots: list[dict[str, float | str | None]],
    direction: str | None,
) -> int | None:
    if direction:
        normalized = direction.upper()
        for idx, lot in enumerate(lots):
            if str(lot.get("direction") or "").upper() == normalized:
                return idx
    return 0 if lots else None


def _is_entry_fill_event(name: str, purpose: str | None) -> bool:
    return (
        name in {"entry_filled", "entry_fill"}
        or ("entry" in name and "filled" in name)
        or (purpose == "entry" and ("execution" in name or "filled" in name))
    )


def _is_exit_fill_event(name: str, purpose: str | None) -> bool:
    exit_events = {
        "tp_filled",
        "tp_fill",
        "merge_filled",
        "merge_fill",
        "trade_closed",
        "position_closed",
        "closed_pnl",
    }
    return (
        name in exit_events
        or (("tp" in name or "merge" in name) and "filled" in name)
        or (purpose in {"tp", "merge"} and ("execution" in name or "filled" in name))
    )


def _entry_direction_from_event(ev: Any) -> str | None:
    side = _event_side(ev)
    if side == "BUY":
        return "LONG"
    if side == "SELL":
        return "SHORT"
    return None


def _exit_direction_from_event(ev: Any) -> str | None:
    side = _event_side(ev)
    if side == "SELL":
        return "LONG"
    if side == "BUY":
        return "SHORT"
    return None


def _event_side(ev: Any) -> str | None:
    side = _field_text(ev.fields, "side", "exec_side", "execSide")
    if side:
        normalized = side.upper()
        if normalized in {"BUY", "B"}:
            return "BUY"
        if normalized in {"SELL", "S"}:
            return "SELL"
    link_id = _field_text(ev.fields, "link_id", "order_link_id", "orderLinkId") or ""
    parts = link_id.split("-")
    if len(parts) >= 2:
        token = parts[1].upper()
        if token == "B":
            return "BUY"
        if token == "S":
            return "SELL"
    return None


def _event_purpose(ev: Any) -> str | None:
    purpose = _field_text(ev.fields, "purpose")
    if purpose:
        return purpose.lower()
    link_id = _field_text(ev.fields, "link_id", "order_link_id", "orderLinkId") or ""
    parts = link_id.split("-")
    if len(parts) >= 3:
        candidate = parts[2].lower()
        if candidate in {"entry", "tp", "merge"}:
            return candidate
    return None


def _field_float(fields: dict[str, Any], *names: str) -> float | None:
    text = _field_text(fields, *names)
    if text is None:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _field_text(fields: dict[str, Any], *names: str) -> str | None:
    for name in names:
        if name not in fields:
            continue
        value = fields.get(name)
        if value is None:
            continue
        text = str(value).strip()
        if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
            text = text[1:-1]
        if text:
            return text
    return None


def _positive_float(value: Any) -> float:
    out = float(value)
    if out <= 0:
        raise ValueError("expected positive number")
    return out


def _nonnegative_float(value: Any) -> float:
    out = float(value)
    if out < 0:
        raise ValueError("expected nonnegative number")
    return out


def _bounded_int(value: Any, low: int, high: int) -> int:
    out = int(value)
    if out < low or out > high:
        raise ValueError(f"expected int between {low} and {high}")
    return out


def _date(value: Any) -> str:
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise ValueError("date must be YYYY-MM-DD")
    return text


def _parse_ts_seconds(ts: str | None) -> float | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def _bucket_label(ts_seconds: float, bucket_size: int) -> str:
    aligned = int(ts_seconds // bucket_size) * bucket_size
    return datetime.fromtimestamp(aligned, tz=timezone.utc).isoformat()


def _seconds_since(ts_seconds: float | None) -> float | None:
    if ts_seconds is None:
        return None
    return max(0.0, time.time() - ts_seconds)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _keep_or_replace(submitted: Any, current: str) -> str:
    """If the submitted value is the masked preview, keep the current secret."""
    if submitted is None:
        return current
    text = str(submitted).strip()
    if text == mask_secret(current):
        return current
    return text


def _collect_symbols(values: dict[str, Any], default: list[str]) -> list[str]:
    parts: list[str] = []
    picked = values.get("symbols_picked")
    if isinstance(picked, list):
        parts.extend(picked)
    elif isinstance(picked, str):
        parts.extend(p.strip() for p in picked.split(",") if p.strip())
    extra = values.get("symbols_extra") or values.get("symbols")
    if extra:
        parts.extend(p.strip() for p in str(extra).split(",") if p.strip())
    if not parts:
        parts = list(default)
    seen: list[str] = []
    for sym in parts:
        u = sym.upper()
        if u and u not in seen:
            seen.append(u)
    return _symbols(",".join(seen), default)


def _optional_positive_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        out = float(text)
    except (TypeError, ValueError):
        raise ValueError(f"expected number, got {text!r}") from None
    if out <= 0:
        raise ValueError(f"expected positive number, got {out}")
    return out


def _optional_bounded_int(value: Any, low: int, high: int) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        out = int(float(text))
    except (TypeError, ValueError):
        raise ValueError(f"expected int, got {text!r}") from None
    if out < low or out > high:
        raise ValueError(f"expected int between {low} and {high}, got {out}")
    return out


def _resolve_optional_positive_float(value: Any, fallback: Any) -> float:
    out = _optional_positive_float(value)
    if out is not None:
        return out
    return _positive_float(fallback)


def _resolve_optional_bounded_int(value: Any, fallback: Any, low: int, high: int) -> int:
    out = _optional_bounded_int(value, low, high)
    if out is not None:
        return out
    return _bounded_int(fallback, low, high)


def _params_to_signal_params_str(params: dict[str, Any]) -> str:
    return ":".join(f"{k}={v}" for k, v in params.items())


def _parse_param_string(value: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in str(value or "").split(":"):
        if not part:
            continue
        if "=" not in part:
            continue
        key, raw = part.split("=", 1)
        key = key.strip()
        if key:
            out[key] = raw.strip()
    return out


_HIDDEN_STRATEGY_NAMES: frozenset[str] = frozenset({
    "trend_grid_a200_e30_s15_t30",
    "realistic_1s",
    "realistic_3s",
    "realistic_5s",
})


def _strategy_is_hidden(name: str) -> bool:
    """Strict deny-list: hide bare names AND any ` / `-suffix variants.

    Keeps `... / naive`, `... / realistic_0.15s`, `... / realistic_0.3s`,
    `... / realistic_0.5s`, and the `trend_grid_a200_e50_s25_t20` family.
    """
    if not name:
        return False
    if name in _HIDDEN_STRATEGY_NAMES:
        return True
    if " / " in name:
        suffix = name.rsplit(" / ", 1)[-1].strip()
        if suffix in _HIDDEN_STRATEGY_NAMES:
            return True
    return False


def _parse_date(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text).replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None


def _coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _coerce_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "on"}:
        return True
    if text in {"false", "0", "no", "n", "off"}:
        return False
    return None


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _extract_config_dir_arg(command: str) -> str | None:
    try:
        parts = shlex.split(command)
    except ValueError:
        return None
    for i, part in enumerate(parts):
        if part == "--config-dir" and i + 1 < len(parts):
            return parts[i + 1]
        if part.startswith("--config-dir="):
            return part.split("=", 1)[1]
    return None


def _symbols(value: Any, default: list[str]) -> list[str]:
    source = str(value or ",".join(default))
    out = [s.strip().upper() for s in source.split(",") if s.strip()]
    if not out or not all(re.fullmatch(r"[A-Z0-9]{2,20}", s) for s in out):
        raise ValueError("invalid symbols")
    return out
