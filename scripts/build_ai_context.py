#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path

from bot.monitoring.ai_context import build_context, latest_log, write_jsonl, write_markdown


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a compact AI-readable context file from bot logs."
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Raw bot log to summarize. Defaults to newest logs/*.log.",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=Path("logs"),
        help="Directory used when --log-file is not provided.",
    )
    parser.add_argument(
        "--pattern",
        default="*.log",
        help="Log glob pattern used with --log-dir.",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=Path("reports/live_ai_context.md"),
        help="Markdown output for AI/human reading.",
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        default=Path("logs/ai_context.jsonl"),
        help="Compact JSONL output for tools.",
    )
    parser.add_argument(
        "--monitor-report",
        type=Path,
        default=Path("reports/live_monitor.md"),
        help="Optional live monitor report to include when present.",
    )
    parser.add_argument("--max-recent", type=int, default=80)
    parser.add_argument("--max-critical", type=int, default=40)
    args = parser.parse_args()

    source_log = args.log_file or latest_log(args.log_dir, args.pattern)
    context = build_context(
        source_log,
        max_recent=args.max_recent,
        max_critical=args.max_critical,
        monitor_report=args.monitor_report,
    )
    write_markdown(context, args.output_md)
    write_jsonl(context, args.output_jsonl)
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_jsonl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
