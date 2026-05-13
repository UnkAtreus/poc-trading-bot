from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx
import yaml
from pydantic import BaseModel, Field

from bot.monitoring.live_monitor import MonitorSnapshot


class DeliveryChannel(BaseModel, extra="forbid"):
    enabled: bool = False


class DeliveryConfig(BaseModel, extra="forbid"):
    telegram: DeliveryChannel = Field(default_factory=DeliveryChannel)
    discord: DeliveryChannel = Field(default_factory=DeliveryChannel)


class AlertingConfig(BaseModel, extra="forbid"):
    enabled: bool = True
    heartbeat_stale_seconds: float = Field(default=180.0, gt=0)
    repeated_failure_threshold: int = Field(default=3, ge=1)
    failure_window_seconds: float = Field(default=900.0, gt=0)
    daily_loss_alert_usd: float = Field(default=5000.0, gt=0)
    delivery: DeliveryConfig = Field(default_factory=DeliveryConfig)


class AlertSecrets(BaseModel, extra="forbid"):
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    discord_webhook_url: str = ""


def load_alerting(path: Path) -> AlertingConfig:
    if not path.exists():
        return AlertingConfig()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return AlertingConfig.model_validate(raw)


def save_alerting(path: Path, config: AlertingConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(config.model_dump(), sort_keys=False), encoding="utf-8")


def load_alert_secrets(path: Path) -> AlertSecrets:
    if not path.exists():
        return AlertSecrets()
    raw = json.loads(path.read_text(encoding="utf-8") or "{}")
    return AlertSecrets.model_validate(raw)


def save_alert_secrets(path: Path, secrets: AlertSecrets) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(secrets.model_dump(), indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return "*" * (len(value) - 4) + value[-4:]


def fingerprint(snapshot: MonitorSnapshot) -> str:
    codes = sorted({issue.code for issue in snapshot.issues if issue.severity == "CRITICAL"})
    if not codes:
        return ""
    return hashlib.sha256("|".join(codes).encode("utf-8")).hexdigest()


def deliver_if_new(
    snapshot: MonitorSnapshot,
    *,
    config: AlertingConfig,
    secrets: AlertSecrets,
    fingerprint_path: Path,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    result = {"delivered": False, "skipped": True, "reason": "", "fingerprint": ""}
    if not config.enabled:
        result["reason"] = "alerting_disabled"
        return result
    critical = [i for i in snapshot.issues if i.severity == "CRITICAL"]
    if not critical:
        result["reason"] = "no_critical_issues"
        return result

    fp = fingerprint(snapshot)
    result["fingerprint"] = fp
    last = ""
    if fingerprint_path.exists():
        last = fingerprint_path.read_text(encoding="utf-8").strip()
    if fp == last:
        result["reason"] = "duplicate_fingerprint"
        return result

    message = _format_message(snapshot, critical)
    posts: list[str] = []

    owns_client = client is None
    client = client or httpx.Client(timeout=10.0)
    try:
        if config.delivery.telegram.enabled and secrets.telegram_bot_token and secrets.telegram_chat_id:
            url = f"https://api.telegram.org/bot{secrets.telegram_bot_token}/sendMessage"
            resp = client.post(url, json={"chat_id": secrets.telegram_chat_id, "text": message})
            posts.append(f"telegram:{resp.status_code}")
        if config.delivery.discord.enabled and secrets.discord_webhook_url:
            resp = client.post(secrets.discord_webhook_url, json={"content": message})
            posts.append(f"discord:{resp.status_code}")
    finally:
        if owns_client:
            client.close()

    if posts:
        fingerprint_path.parent.mkdir(parents=True, exist_ok=True)
        fingerprint_path.write_text(fp, encoding="utf-8")
        result.update(delivered=True, skipped=False, reason="sent", posts=posts)
    else:
        result["reason"] = "no_channel_configured"
    return result


def _format_message(snapshot: MonitorSnapshot, critical: list) -> str:
    lines = [
        f"[{snapshot.severity}] Trading bot alert ({snapshot.mode})",
        f"Generated UTC: {snapshot.generated_at_utc}",
        "",
    ]
    for issue in critical[:10]:
        sym = f" {issue.symbol}" if issue.symbol else ""
        lines.append(f"- {issue.code}{sym}: {issue.message}")
    if len(critical) > 10:
        lines.append(f"... and {len(critical) - 10} more")
    return "\n".join(lines)


def snapshot_summary(snapshot: MonitorSnapshot) -> dict[str, Any]:
    raw = asdict(snapshot)
    wallet = raw.get("wallet") or {}
    return {
        "ts": snapshot.generated_at_utc,
        "severity": snapshot.severity,
        "total_equity": wallet.get("total_equity"),
        "usdt_unrealised_pnl": wallet.get("usdt_unrealised_pnl"),
        "daily_closed_pnl": snapshot.daily_closed_pnl,
        "open_positions": len(snapshot.positions),
        "open_orders": len(snapshot.open_orders),
    }
