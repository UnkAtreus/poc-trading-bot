"""Daily testnet soak check.

Gathers the last N hours of bot evidence and writes an LLM-ready markdown
pack to reports/soak_check_YYYY-MM-DD.md so you can paste it to your
preferred LLM and ask "is today clean toward the 7-day mainnet checklist?"

Runs deterministic auto checks too. Exit code 0 when all auto checks pass,
non-zero when any fail — handy for cron / launchd.

Usage:
    uv run python scripts/soak_check.py
    uv run python scripts/soak_check.py --window-hours 6 --out reports/soak_now.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from bot.monitoring.ai_context import iter_ai_events, latest_log  # noqa: E402


TRACKED_EVENTS = (
    "reconcile.failed",
    "reconcile_loop_error",
    "reconcile.exit_order_missing",
    "fatal_order_rejection_stopping_bot",
    "place_order_failed",
    "tp_place_rejected",
    "merge_tp_place_rejected",
    "entry_rejected",
    "entry_blocked",
    "dust_stranded",
    "position_drift",
    "on_user_event_error",
    "on_candle_error",
)

# Auto-check thresholds. The LLM still gets the raw evidence and can apply
# stricter judgement; these are the hard floor.
LIMITS = {
    "reconcile.failed": 0,
    "reconcile_loop_error": 0,
    "fatal_order_rejection_stopping_bot": 0,
    "on_user_event_error": 0,
    "on_candle_error": 0,
    "max_heartbeat_gap_seconds": 120.0,
    "max_bot_restarts": 0,
    "stuck_non_terminal_states": 0,  # MERGE_PENDING etc that lingered past the merge timer
}

# State machine states that should NOT be the resting state for a 24h window.
NON_TERMINAL_OPEN_STATES = {"MERGE_PENDING", "ENTRY_PENDING", "IN_POSITION_TP_PENDING"}


@dataclass
class SoakEvidence:
    window_start_utc: str
    window_end_utc: str
    bot_restarts: int
    heartbeats: int
    max_heartbeat_gap_seconds: float | None
    entries_filled: int
    tps_filled: int
    event_counts: dict[str, int]
    stuck_states: list[dict[str, str]]
    monitor_severity: str | None
    bot_alive: bool | None
    kill_active: bool | None
    source_log: str | None = None


def _parse_ts(ts: str) -> float | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def _parse_monitor(monitor_md: Path) -> dict[str, str | bool | None]:
    if not monitor_md.exists():
        return {"severity": None, "bot_alive": None, "kill_active": None}
    text = monitor_md.read_text(encoding="utf-8", errors="replace")
    out: dict[str, str | bool | None] = {
        "severity": None, "bot_alive": None, "kill_active": None,
    }
    m = re.search(r"^- Severity:\s*`?([A-Z]+)`?", text, re.MULTILINE)
    if m:
        out["severity"] = m.group(1)
    m = re.search(r"^- Bot alive:\s*`?(True|False)`?", text, re.MULTILINE)
    if m:
        out["bot_alive"] = m.group(1) == "True"
    m = re.search(r"^- Kill triggered:\s*`?(True|False)`?", text, re.MULTILINE)
    if m:
        out["kill_active"] = m.group(1) == "True"
    return out


def gather_evidence(
    *,
    log_dir: Path,
    state_dir: Path,
    monitor_md: Path,
    window_hours: float = 24.0,
    now: datetime | None = None,
) -> SoakEvidence:
    now = now or datetime.now(tz=timezone.utc)
    window_end = now
    window_start = now - timedelta(hours=window_hours)
    window_start_ts = window_start.timestamp()

    counts: dict[str, int] = {ev: 0 for ev in TRACKED_EVENTS}
    heartbeats = 0
    entries_filled = 0
    tps_filled = 0
    bot_restarts = 0
    heartbeat_ts: list[float] = []
    source: Path | None = None

    try:
        source = latest_log(log_dir, "*.log")
    except FileNotFoundError:
        source = None

    if source is not None:
        for event in iter_ai_events(source):
            ev_ts = _parse_ts(event.ts)
            if ev_ts is None or ev_ts < window_start_ts:
                continue
            if event.event == "heartbeat":
                heartbeats += 1
                heartbeat_ts.append(ev_ts)
            elif event.event == "entry_filled":
                entries_filled += 1
            elif event.event == "tp_filled":
                tps_filled += 1
            elif event.event == "boot.banner":
                bot_restarts += 1
            if event.event in counts:
                counts[event.event] += 1

    max_gap: float | None = None
    if len(heartbeat_ts) >= 2:
        heartbeat_ts.sort()
        gaps = [b - a for a, b in zip(heartbeat_ts, heartbeat_ts[1:])]
        max_gap = max(gaps)

    stuck: list[dict[str, str]] = []
    if state_dir.exists():
        for path in sorted(state_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            state = str(data.get("state", ""))
            if state in NON_TERMINAL_OPEN_STATES or state == "DUST_STRANDED":
                stuck.append({
                    "symbol": str(data.get("symbol", path.stem)),
                    "state": state,
                    "position_size": str(data.get("position_size", 0)),
                    "direction": str(data.get("direction") or ""),
                    "first_fill_ts": str(data.get("first_fill_ts") or ""),
                })

    monitor = _parse_monitor(monitor_md)
    return SoakEvidence(
        window_start_utc=window_start.isoformat(),
        window_end_utc=window_end.isoformat(),
        bot_restarts=bot_restarts,
        heartbeats=heartbeats,
        max_heartbeat_gap_seconds=max_gap,
        entries_filled=entries_filled,
        tps_filled=tps_filled,
        event_counts={k: v for k, v in counts.items() if v > 0},
        stuck_states=stuck,
        monitor_severity=monitor.get("severity"),  # type: ignore[arg-type]
        bot_alive=monitor.get("bot_alive"),  # type: ignore[arg-type]
        kill_active=monitor.get("kill_active"),  # type: ignore[arg-type]
        source_log=str(source) if source else None,
    )


def evaluate(ev: SoakEvidence) -> tuple[bool, list[str]]:
    fails: list[str] = []
    for name, limit in LIMITS.items():
        if name == "max_heartbeat_gap_seconds":
            if ev.max_heartbeat_gap_seconds is not None and ev.max_heartbeat_gap_seconds > limit:
                fails.append(
                    f"heartbeat gap {ev.max_heartbeat_gap_seconds:.0f}s > limit {limit:.0f}s"
                )
            continue
        if name == "max_bot_restarts":
            if ev.bot_restarts > limit:
                fails.append(f"bot restarts {ev.bot_restarts} > limit {limit}")
            continue
        if name == "stuck_non_terminal_states":
            stuck_open = [s for s in ev.stuck_states if s["state"] in NON_TERMINAL_OPEN_STATES]
            if len(stuck_open) > limit:
                syms = ", ".join(f"{s['symbol']}({s['state']})" for s in stuck_open)
                fails.append(f"stuck non-terminal states: {syms}")
            continue
        count = ev.event_counts.get(name, 0)
        if count > limit:
            fails.append(f"{name} count {count} > limit {limit}")
    if ev.monitor_severity not in (None, "OK"):
        fails.append(f"monitor severity is {ev.monitor_severity}")
    if ev.bot_alive is False:
        fails.append("bot not alive in monitor")
    if ev.kill_active:
        fails.append("kill switch is active")
    return (not fails, fails)


PROMPT_PREAMBLE = """\
You are auditing a single soak day for a Bybit USDT-perp testnet trading bot.
The team wants ≥7 consecutive clean days before promoting to mainnet.

Read the evidence below and answer:

1. Does this day count as CLEAN toward the 7-day window? (yes / no)
2. If no, which specific signal(s) disqualify it?
3. Anything else worth investigating before tomorrow's check?

A clean day means: no CRITICAL alerts; zero reconcile.failed / fatal order
rejections; heartbeat continuous (gaps < 2 min); no symbols stuck in
ENTRY_PENDING / MERGE_PENDING / IN_POSITION_TP_PENDING past the merge timer;
no kill switch trip; ≥ a few real round-trip trades (silence with zero
trades doesn't validate the lifecycle).
"""


def render_evidence_pack(ev: SoakEvidence, *, passed: bool, fails: list[str]) -> str:
    parts: list[str] = []
    parts.append("# Soak Check")
    parts.append("")
    parts.append(PROMPT_PREAMBLE)
    parts.append("")
    parts.append("## Window")
    parts.append("")
    parts.append(f"- Start UTC: `{ev.window_start_utc}`")
    parts.append(f"- End UTC: `{ev.window_end_utc}`")
    if ev.source_log:
        parts.append(f"- Source log: `{ev.source_log}`")
    parts.append("")
    parts.append("## Auto checks")
    parts.append("")
    parts.append(f"- Verdict: **{'PASS' if passed else 'FAIL'}**")
    if fails:
        for fail in fails:
            parts.append(f"  - FAIL: {fail}")
    else:
        parts.append("  - All deterministic checks within thresholds.")
    parts.append("")
    parts.append("## Evidence")
    parts.append("")
    parts.append(f"- Bot restarts in window: `{ev.bot_restarts}`")
    parts.append(f"- Heartbeats in window: `{ev.heartbeats}`")
    if ev.max_heartbeat_gap_seconds is not None:
        parts.append(f"- Max heartbeat gap: `{ev.max_heartbeat_gap_seconds:.1f}s`")
    else:
        parts.append("- Max heartbeat gap: `n/a (need ≥2 heartbeats)`")
    parts.append(f"- Entries filled: `{ev.entries_filled}`")
    parts.append(f"- TPs filled: `{ev.tps_filled}`")
    parts.append(f"- Monitor severity: `{ev.monitor_severity or 'n/a'}`")
    parts.append(f"- Bot alive (per monitor): `{ev.bot_alive}`")
    parts.append(f"- Kill switch: `{ev.kill_active}`")
    parts.append("")
    parts.append("### Tracked event counts (window)")
    parts.append("")
    if ev.event_counts:
        for name, count in sorted(ev.event_counts.items(), key=lambda kv: (-kv[1], kv[0])):
            parts.append(f"- `{name}`: {count}")
    else:
        parts.append("- All tracked events: 0")
    parts.append("")
    parts.append("### Per-symbol resting state (non-IDLE)")
    parts.append("")
    if ev.stuck_states:
        for s in ev.stuck_states:
            extra = f", first_fill_ts=`{s['first_fill_ts']}`" if s['first_fill_ts'] else ""
            parts.append(
                f"- `{s['symbol']}` state=`{s['state']}` size=`{s['position_size']}` "
                f"direction=`{s['direction']}`{extra}"
            )
    else:
        parts.append("- All symbols IDLE.")
    parts.append("")
    parts.append("## Question for the LLM")
    parts.append("")
    parts.append("Apply the criteria from the preamble and emit the three answers requested.")
    parts.append("")
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-hours", type=float, default=24.0)
    parser.add_argument("--log-dir", type=Path, default=ROOT / "logs")
    parser.add_argument("--state-dir", type=Path, default=ROOT / "data" / "state")
    parser.add_argument("--monitor", type=Path, default=ROOT / "reports" / "live_monitor.md")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output markdown path. Defaults to reports/soak_check_YYYY-MM-DD.md")
    parser.add_argument("--quiet", action="store_true", help="Suppress evidence print to stdout")
    args = parser.parse_args(argv)

    now = datetime.now(tz=timezone.utc)
    ev = gather_evidence(
        log_dir=args.log_dir,
        state_dir=args.state_dir,
        monitor_md=args.monitor,
        window_hours=args.window_hours,
        now=now,
    )
    passed, fails = evaluate(ev)
    md = render_evidence_pack(ev, passed=passed, fails=fails)

    out_path = args.out or (ROOT / "reports" / f"soak_check_{now.strftime('%Y-%m-%d')}.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")

    if not args.quiet:
        print(md)
    print(f"\nwrote {out_path}")
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
