"""One-shot migration: split existing range-keyed parquet files into per-month chunks.

Old format: data/klines/{SYMBOL}_{start_ms}_{end_ms}.parquet
New format: data/klines/{SYMBOL}_{YYYY-MM}.parquet

Usage:
    uv run python scripts/migrate_klines_to_monthly.py
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from bot.backtest.downloader import _month_bounds_ms, _month_path

OLD_PATTERN = re.compile(r"^([A-Z0-9]+USDT)_(\d{13})_(\d{13})\.parquet$")


def main() -> int:
    klines = Path("data/klines")
    if not klines.exists():
        print("no data/klines/ directory")
        return 0

    migrated = 0
    skipped = 0
    for p in sorted(klines.iterdir()):
        m = OLD_PATTERN.match(p.name)
        if not m:
            skipped += 1
            continue
        symbol = m.group(1)
        df = pd.read_parquet(p)
        if df.empty:
            print(f"  empty: {p.name} — removing")
            p.unlink()
            continue

        # Group rows by UTC year-month
        df["_dt"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df["_ym"] = df["_dt"].dt.strftime("%Y-%m")
        groups = df.groupby("_ym")

        wrote_any = False
        for ym, sub in groups:
            year, month = int(ym[:4]), int(ym[5:7])
            target = _month_path(klines, symbol, year, month)
            sub = sub.drop(columns=["_dt", "_ym"]).reset_index(drop=True)
            if target.exists():
                existing = pd.read_parquet(target)
                merged = pd.concat([existing, sub]).drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
                merged.to_parquet(target, index=False)
            else:
                sub.to_parquet(target, index=False)
            wrote_any = True

        if wrote_any:
            print(f"  migrated: {p.name} → {len(groups)} monthly files")
            p.unlink()
            migrated += 1
        else:
            skipped += 1

    print(f"\nDone. migrated={migrated} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
