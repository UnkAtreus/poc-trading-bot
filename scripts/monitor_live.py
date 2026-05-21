#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path

from bot.config import Mode, load_settings
from bot.monitoring.live_monitor import (
    run_monitor,
    write_alerts_markdown,
    write_monitor_jsonl,
    write_monitor_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic live safety monitor for testnet/mainnet bot runs."
    )
    parser.add_argument("--log-file", type=Path, default=None)
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path("config"),
        help="Directory containing bot.yaml and symbols.yaml",
    )
    parser.add_argument("--log-dir", type=Path, default=Path("logs"))
    parser.add_argument("--state-dir", type=Path, default=Path("data/state"))
    parser.add_argument("--output-md", type=Path, default=Path("reports/live_monitor.md"))
    parser.add_argument("--alerts-md", type=Path, default=Path("reports/live_alerts.md"))
    parser.add_argument("--output-jsonl", type=Path, default=Path("logs/live_monitor.jsonl"))
    parser.add_argument("--heartbeat-stale-seconds", type=float, default=180.0)
    parser.add_argument("--repeated-failure-threshold", type=int, default=3)
    parser.add_argument(
        "--failure-window-seconds",
        type=float,
        default=900.0,
        help="Recent log window used for repeated failure counts.",
    )
    parser.add_argument(
        "--process-pattern",
        default="trading-bot run|bot.main run|python -m bot.main run",
        help="pgrep -f pattern used to verify bot process is alive.",
    )
    parser.add_argument(
        "--tmux-session",
        default="",
        help="If set, use `tmux has-session -t` instead of pgrep.",
    )
    parser.add_argument(
        "--skip-process-check",
        action="store_true",
        help="Treat bot process as alive; useful for local report-only dry checks.",
    )
    parser.add_argument(
        "--write-kill",
        action="store_true",
        help="Create data/state/KILL when a CRITICAL safety issue is detected.",
    )
    args = parser.parse_args()

    settings = load_settings(config_dir=args.config_dir)
    if settings.env.mode is Mode.BACKTEST:
        raise SystemExit("monitor_live requires MODE=testnet or MODE=mainnet")
    if not settings.env.bybit_api_key or not settings.env.bybit_api_secret:
        raise SystemExit("missing BYBIT_API_KEY / BYBIT_API_SECRET")

    process_pattern = None if args.skip_process_check else args.process_pattern
    tmux_session = args.tmux_session or None
    snapshot = run_monitor(
        settings,
        log_dir=args.log_dir,
        log_file=args.log_file,
        state_dir=args.state_dir,
        process_pattern=process_pattern,
        tmux_session=tmux_session,
        heartbeat_stale_seconds=args.heartbeat_stale_seconds,
        repeated_failure_threshold=args.repeated_failure_threshold,
        failure_window_seconds=args.failure_window_seconds,
        write_kill=args.write_kill,
    )
    write_monitor_markdown(snapshot, args.output_md)
    write_alerts_markdown(snapshot, args.alerts_md)
    write_monitor_jsonl(snapshot, args.output_jsonl)
    print(f"severity={snapshot.severity} issues={len(snapshot.issues)}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.alerts_md}")
    print(f"Wrote {args.output_jsonl}")
    return 2 if snapshot.severity in {"CRITICAL", "KILL_TRIGGERED"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
