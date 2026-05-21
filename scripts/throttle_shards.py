"""Pause/resume batch_optimize_stability shards on a time-of-day schedule.

Asia/Bangkok local time:
  01:00 - 10:00  -> heavy window, keep `--heavy-count` shards active
  otherwise      -> light window, keep `--light-count` shards active

Picks which shards to pause by index: keeps the lowest-numbered ones active,
pauses the highest. Sends SIGSTOP/SIGCONT to the python child of each shard
(not the `uv run` wrapper). Exits when no shard processes remain.

Usage:
    uv run python scripts/throttle_shards.py --light-count 4 --heavy-count 8
"""
from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

TZ_BANGKOK = ZoneInfo("Asia/Bangkok")

SHARD_ARG_PATTERN = re.compile(
    r"python.*batch_optimize_stability\.py.*?--shard-index\s+(\d+)(?!\d)"
)


def _desired_active_count(now: datetime, *, light_count: int, heavy_count: int) -> int:
    if 1 <= now.hour < 10:
        return heavy_count
    return light_count


def _shard_pids() -> dict[int, int]:
    out = subprocess.run(
        ["ps", "-A", "-o", "pid=,args="],
        capture_output=True,
        text=True,
    ).stdout
    pids: dict[int, int] = {}
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        pid_str, _, args = line.partition(" ")
        if args.lstrip().startswith("uv "):
            continue
        match = SHARD_ARG_PATTERN.search(args)
        if match:
            pids[int(match.group(1))] = int(pid_str)
    return pids


def _is_stopped(pid: int) -> bool:
    out = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)],
        capture_output=True,
        text=True,
    ).stdout.strip()
    return out.startswith("T")


def _apply(active_target: int, pids: dict[int, int], *, log_prefix: str) -> None:
    sorted_indices = sorted(pids.keys())
    keep_active = set(sorted_indices[:active_target])
    for idx in sorted_indices:
        pid = pids[idx]
        stopped = _is_stopped(pid)
        if idx in keep_active and stopped:
            os.kill(pid, signal.SIGCONT)
            print(f"{log_prefix} CONT shard {idx} pid {pid}", flush=True)
        elif idx not in keep_active and not stopped:
            os.kill(pid, signal.SIGSTOP)
            print(f"{log_prefix} STOP shard {idx} pid {pid}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--light-count", type=int, default=4)
    parser.add_argument("--heavy-count", type=int, default=8)
    parser.add_argument("--poll-seconds", type=float, default=60.0)
    args = parser.parse_args()

    print(
        f"throttle_shards: light={args.light_count} heavy={args.heavy_count} "
        f"poll={args.poll_seconds}s tz=Asia/Bangkok",
        flush=True,
    )

    while True:
        now = datetime.now(TZ_BANGKOK)
        log_prefix = f"[{now.strftime('%Y-%m-%d %H:%M:%S %Z')}]"
        active_target = _desired_active_count(
            now, light_count=args.light_count, heavy_count=args.heavy_count
        )
        pids = _shard_pids()
        if not pids:
            print(f"{log_prefix} no shards left; exiting", flush=True)
            return 0
        window = "heavy" if 1 <= now.hour < 10 else "light"
        print(
            f"{log_prefix} window={window} target={active_target} of {len(pids)} live shards",
            flush=True,
        )
        _apply(active_target, pids, log_prefix=log_prefix)
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
