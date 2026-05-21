from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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

SAFE_SIGNALS = (
    "trend_filter",
    "grid",
    "placeholder_rsi",
    "bollinger_bands",
    "ema_crossover",
    "zscore",
    "dual_signal",
    "crash_guard",
)


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
        }

    def safe_settings(self) -> dict[str, Any]:
        settings = load_settings(config_dir=self.config_dir)
        bot_yaml = self._read_yaml(self.config_dir / "bot.yaml")
        symbols_yaml = self._read_yaml(self.config_dir / "symbols.yaml")
        return {
            "mode": settings.env.mode.value,
            "has_api_key": bool(settings.env.bybit_api_key),
            "has_api_secret": bool(settings.env.bybit_api_secret),
            "sizing": bot_yaml.get("sizing", {}),
            "offsets": bot_yaml.get("offsets", {}),
            "risk": bot_yaml.get("risk", {}),
            "account": bot_yaml.get("account", {}),
            "signal": bot_yaml.get("signal", {}),
            "loop": bot_yaml.get("loop", {}),
            "symbols": symbols_yaml,
        }

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
        settings = load_settings(config_dir=self.config_dir)
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
        }

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

    def regenerate_ai_context(self) -> None:
        source_log = latest_log(self.logs_dir, "*.log")
        from bot.monitoring.ai_context import build_context, write_jsonl, write_markdown

        context = build_context(source_log, monitor_report=self.reports_dir / "live_monitor.md")
        write_markdown(context, self.reports_dir / "live_ai_context.md")
        write_jsonl(context, self.logs_dir / "ai_context.jsonl")

    def preview_config(self, values: dict[str, Any]) -> dict[str, Any]:
        bot_yaml = self._read_yaml(self.config_dir / "bot.yaml")
        symbols_yaml = self._read_yaml(self.config_dir / "symbols.yaml")
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
            "bot_yaml": yaml.safe_dump(updated_bot, sort_keys=False),
            "symbols_yaml": yaml.safe_dump(updated_symbols, sort_keys=False),
        }

    def save_config(self, values: dict[str, Any]) -> None:
        preview = self.preview_config(values)
        (self.config_dir / "bot.yaml").write_text(preview["bot_yaml"], encoding="utf-8")
        (self.config_dir / "symbols.yaml").write_text(preview["symbols_yaml"], encoding="utf-8")

    def start_backtest(self, values: dict[str, Any]) -> dict[str, Any]:
        start = _date(values.get("start"))
        end = _date(values.get("end"))
        active_default = self.safe_settings()["symbols"]["active"]
        symbols = _collect_symbols(values, active_default)
        initial_equity = _positive_float(values.get("initial_equity"))
        signal_engine = str(values.get("signal_engine") or "").strip()
        signal_params = str(values.get("signal_params") or "").strip().lstrip(":")
        raw_signal = str(values.get("signal") or "").strip()
        if not signal_engine and raw_signal:
            signal_engine = raw_signal.split(":", 1)[0]
            signal_params = signal_params or raw_signal.split(":", 1)[1] if ":" in raw_signal else signal_params
        if signal_engine and signal_engine not in SAFE_SIGNALS:
            raise ValueError("unsupported signal")
        signal = signal_engine
        if signal_engine and signal_params:
            signal = f"{signal_engine}:{signal_params}"

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
        if signal:
            cmd.extend(["--signal", signal])

        spec = {
            "ts": str(ts),
            "cmd": cmd,
            "log_path": str(log_path.relative_to(self.root)),
            "report_path": str(report_path.relative_to(self.root)),
            "registry_path": str(registry_path.relative_to(self.root)),
            "summary": {
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "signal": signal,
                "symbols": symbols,
                "start": start,
                "end": end,
                "initial_equity": initial_equity,
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

    def list_backtest_jobs(self, *, limit: int = 30) -> list[dict[str, Any]]:
        directory = self.state_dir / "backtests"
        if not directory.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            if path.name.endswith(".spec.json"):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            data["ts"] = data.get("ts") or path.stem
            data["registry"] = str(path.relative_to(self.root))
            rows.append(data)
            if len(rows) >= limit:
                break
        return rows

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


def _symbols(value: Any, default: list[str]) -> list[str]:
    source = str(value or ",".join(default))
    out = [s.strip().upper() for s in source.split(",") if s.strip()]
    if not out or not all(re.fullmatch(r"[A-Z0-9]{2,20}", s) for s in out):
        raise ValueError("invalid symbols")
    return out
