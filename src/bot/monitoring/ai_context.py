from __future__ import annotations

import ast
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
LINE_RE = re.compile(
    r"^(?P<ts>\S+)\s+\[\s*(?P<level>[A-Za-z]+)\s+\]\s+"
    r"(?P<event>[A-Za-z0-9_.-]+)\s*(?P<kv>.*)$"
)
KV_RE = re.compile(r"(?P<key>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>\{.*?\}|'[^']*'|\"[^\"]*\"|\S+)")

CRITICAL_EVENTS = {
    "fatal_order_rejection_stopping_bot",
    "place_order_failed",
    "tp_place_rejected",
    "merge_tp_place_rejected",
    "reconcile.failed",
    "reconcile_loop_error",
    "on_user_event_error",
    "on_candle_error",
}

IMPORTANT_EVENTS = CRITICAL_EVENTS | {
    "bot.starting",
    "bot.started",
    "bot.stopped",
    "heartbeat",
    "entry_blocked",
    "entry_rejected",
    "cancel_failed",
    "cancel_all_failed",
    "position_drift",
    "reconcile.force_idle",
    "reconcile.size_drift",
    "reconcile.adopt_exchange_position",
    "reconcile.exit_order_missing",
}

MAX_FIELD_CHARS = 220


@dataclass(frozen=True)
class AiEvent:
    ts: str
    level: str
    event: str
    symbol: str | None
    fields: dict[str, str]

    @property
    def is_critical(self) -> bool:
        return self.level in {"error", "critical"} or self.event in CRITICAL_EVENTS


@dataclass(frozen=True)
class AiContext:
    source_log: str
    generated_at_utc: str
    first_ts: str | None
    last_ts: str | None
    current_states: dict[str, str]
    event_counts: dict[str, int]
    critical_events: list[AiEvent]
    recent_events: list[AiEvent]
    monitor_summary: list[str] = field(default_factory=list)


def latest_log(log_dir: Path, pattern: str = "*.log") -> Path:
    candidates = [p for p in log_dir.glob(pattern) if p.is_file()]
    if not candidates:
        raise FileNotFoundError(f"No log files match {pattern!r} under {log_dir}")
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates:
        if _has_bot_event(path):
            return path
    return candidates[0]


def _has_bot_event(path: Path, *, max_lines: int = 200) -> bool:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    return False
                if parse_log_line(line) is not None:
                    return True
    except OSError:
        return False
    return False


def strip_ansi(line: str) -> str:
    return ANSI_RE.sub("", line).strip()


def parse_log_line(line: str) -> AiEvent | None:
    clean = strip_ansi(line)
    match = LINE_RE.match(clean)
    if not match:
        return None

    fields = _parse_fields(match.group("kv"))
    symbol = fields.get("symbol")
    return AiEvent(
        ts=match.group("ts"),
        level=match.group("level").lower(),
        event=match.group("event"),
        symbol=symbol,
        fields=fields,
    )


def build_context(
    source_log: Path,
    *,
    max_recent: int = 80,
    max_critical: int = 40,
    monitor_report: Path | None = None,
) -> AiContext:
    counts: Counter[str] = Counter()
    recent: list[AiEvent] = []
    critical: list[AiEvent] = []
    current_states: dict[str, str] = {}
    first_ts: str | None = None
    last_ts: str | None = None

    for event in iter_ai_events(source_log):
        first_ts = first_ts or event.ts
        last_ts = event.ts
        counts[event.event] += 1

        if event.event == "heartbeat":
            parsed_states = _literal_dict(event.fields.get("states"))
            if parsed_states:
                current_states = {str(k): str(v) for k, v in parsed_states.items()}

        if event.event in IMPORTANT_EVENTS or event.is_critical:
            recent.append(event)
            recent = recent[-max_recent:]

        if event.is_critical:
            critical.append(event)
            critical = critical[-max_critical:]

    return AiContext(
        source_log=str(source_log),
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
        first_ts=first_ts,
        last_ts=last_ts,
        current_states=current_states,
        event_counts=dict(counts.most_common()),
        critical_events=critical,
        recent_events=recent,
        monitor_summary=_read_monitor_summary(monitor_report),
    )


def iter_ai_events(source_log: Path) -> Iterable[AiEvent]:
    with source_log.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            event = parse_log_line(line)
            if event is not None:
                yield event


def write_jsonl(context: AiContext, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        header = {
            "type": "summary",
            "source_log": context.source_log,
            "generated_at_utc": context.generated_at_utc,
            "first_ts": context.first_ts,
            "last_ts": context.last_ts,
            "current_states": context.current_states,
            "event_counts": context.event_counts,
            "monitor_summary": context.monitor_summary,
        }
        f.write(json.dumps(header, sort_keys=True) + "\n")
        for event in context.recent_events:
            row = {"type": "event", **asdict(event), "critical": event.is_critical}
            f.write(json.dumps(row, sort_keys=True) + "\n")


def write_markdown(context: AiContext, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Live AI Context",
        "",
        "This file is generated from raw bot logs for AI review. Use this instead of pasting raw logs.",
        "",
        f"- Source log: `{context.source_log}`",
        f"- Generated UTC: `{context.generated_at_utc}`",
        f"- Window: `{context.first_ts or 'n/a'}` to `{context.last_ts or 'n/a'}`",
        "",
        "## Monitor Summary",
        "",
    ]
    if context.monitor_summary:
        lines.extend(context.monitor_summary)
    else:
        lines.append("- No monitor report found.")

    lines.extend([
        "",
        "## Current States",
        "",
    ])
    if context.current_states:
        for symbol, state in sorted(context.current_states.items()):
            lines.append(f"- `{symbol}`: `{state}`")
    else:
        lines.append("- No heartbeat state found.")

    lines.extend(["", "## Critical Events", ""])
    if context.critical_events:
        for event in context.critical_events[-20:]:
            lines.append(_format_event_bullet(event))
    else:
        lines.append("- None found in parsed log window.")

    lines.extend(["", "## Event Counts", ""])
    for name, count in list(context.event_counts.items())[:30]:
        lines.append(f"- `{name}`: `{count}`")

    lines.extend(["", "## Recent Important Events", ""])
    if context.recent_events:
        for event in context.recent_events[-60:]:
            lines.append(_format_event_bullet(event))
    else:
        lines.append("- None found.")

    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for match in KV_RE.finditer(text):
        value = match.group("value").strip()
        if len(value) > MAX_FIELD_CHARS:
            value = value[:MAX_FIELD_CHARS] + "..."
        fields[match.group("key")] = value
    return fields


def _read_monitor_summary(monitor_report: Path | None) -> list[str]:
    if monitor_report is None or not monitor_report.exists():
        return []
    lines = monitor_report.read_text(encoding="utf-8", errors="replace").splitlines()
    summary: list[str] = []
    capture = False
    for line in lines:
        if line.startswith("## Issues"):
            capture = True
        elif line.startswith("## Wallet"):
            capture = False
        if line.startswith("- Severity:") or line.startswith("- Kill triggered:") or line.startswith("- Bot alive:") or line.startswith("- Latest heartbeat:"):
            summary.append(line)
        elif capture and line.startswith("- "):
            summary.append(line)
        if len(summary) >= 30:
            break
    return summary


def _literal_dict(value: str | None) -> dict | None:
    if not value:
        return None
    try:
        parsed = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _format_event_bullet(event: AiEvent) -> str:
    prefix = f"- `{event.ts}` `{event.level}` `{event.event}`"
    if event.symbol:
        prefix += f" `{event.symbol}`"
    details = _compact_fields(event.fields)
    return f"{prefix}: {details}" if details else prefix


def _compact_fields(fields: dict[str, str]) -> str:
    skip = {"states"}
    parts = []
    for key in ("symbol", "reason", "link_id", "local", "exchange", "bep_local", "bep_exchange", "state", "direction", "size", "bep", "error"):
        if key in fields and key not in skip:
            parts.append(f"{key}={fields[key]}")
    if not parts and "states" in fields:
        parts.append(f"states={fields['states']}")
    return ", ".join(parts)
