"""Register batch_optimize_stability shards in the dashboard job registry.

Writes one JSON file per shard under ``data/state/backtests/`` so the dashboard's
``/backtests`` "Recent jobs" table shows live status. Polls the shard processes
and the per-shard markdown report; flips ``status`` to ``finished`` once the
report file exists, or ``failed`` if the process exits without one.

Usage:
    uv run python scripts/track_shard_registry.py \
        --shard-count 8 \
        --csv-prefix logs/batch_optimize_stability_2024_2026_core \
        --report-prefix reports/batch_optimize_stability_2024_2026_core \
        --log-prefix logs/batch_optimize_stability \
        --start 2024-01-01 --end 2026-05-01 \
        --signal trend_filter \
        --symbols BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT \
        --initial-equity 30000
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "data" / "state" / "backtests"


def _registry_path(ts: int, shard_index: int, shard_count: int) -> Path:
    return STATE_DIR / f"{ts}_shard{shard_index:02d}of{shard_count:02d}.json"


def _running_shard_indices() -> set[int]:
    proc = subprocess.run(["ps", "-A", "-o", "args="], capture_output=True, text=True)
    if proc.returncode != 0:
        return set()
    indices: set[int] = set()
    pattern = re.compile(r"batch_optimize_stability\.py.*?--shard-index\s+(\d+)(?!\d)")
    for line in proc.stdout.splitlines():
        match = pattern.search(line)
        if match:
            indices.add(int(match.group(1)))
    return indices


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _initial_payload(args, ts: int, shard_index: int) -> dict:
    csv_path = f"{args.csv_prefix}_shard{shard_index:02d}of{args.shard_count:02d}.csv"
    report_path = f"{args.report_prefix}_shard{shard_index:02d}of{args.shard_count:02d}.md"
    log_path = f"{args.log_prefix}_shard{shard_index}of{args.shard_count}.log"
    return {
        "ts": ts,
        "status": "running",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "started_at": time.time(),
        "signal": args.signal,
        "symbols": args.symbols.split(","),
        "start": args.start,
        "end": args.end,
        "initial_equity": args.initial_equity,
        "shard_index": shard_index,
        "shard_count": args.shard_count,
        "csv_path": csv_path,
        "log_path": log_path,
        "report_path": report_path,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-count", type=int, required=True)
    parser.add_argument("--csv-prefix", required=True)
    parser.add_argument("--report-prefix", required=True)
    parser.add_argument("--log-prefix", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--signal", required=True)
    parser.add_argument("--symbols", required=True)
    parser.add_argument("--initial-equity", type=float, required=True)
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--base-ts", type=int, default=None)
    args = parser.parse_args()

    base_ts = args.base_ts or int(time.time())
    registries: dict[int, Path] = {}
    payloads: dict[int, dict] = {}
    for shard_index in range(args.shard_count):
        ts = base_ts + shard_index
        path = _registry_path(ts, shard_index, args.shard_count)
        payload = _initial_payload(args, ts, shard_index)
        if not path.exists():
            _write(path, payload)
        else:
            payload = json.loads(path.read_text(encoding="utf-8"))
        registries[shard_index] = path
        payloads[shard_index] = payload

    print(f"tracking {args.shard_count} shards; registry dir: {STATE_DIR}", flush=True)

    while True:
        all_done = True
        running_indices = _running_shard_indices()
        for shard_index, path in registries.items():
            payload = payloads[shard_index]
            if payload.get("status") in ("finished", "failed"):
                continue
            all_done = False
            report_path = ROOT / payload["report_path"]
            running = shard_index in running_indices
            if report_path.exists():
                payload["status"] = "finished"
                payload["finished_at"] = time.time()
                payload["duration_s"] = payload["finished_at"] - payload.get("started_at", payload["finished_at"])
                _write(path, payload)
                print(f"shard {shard_index}: finished ({payload['duration_s']:.0f}s)", flush=True)
            elif not running:
                payload["status"] = "failed"
                payload["finished_at"] = time.time()
                payload["duration_s"] = payload["finished_at"] - payload.get("started_at", payload["finished_at"])
                _write(path, payload)
                print(f"shard {shard_index}: failed (process gone, no report)", flush=True)
        if all_done:
            print("all shards terminal; exiting tracker", flush=True)
            return 0
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
