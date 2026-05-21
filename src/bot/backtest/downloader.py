"""Download Bybit 1m kline history into per-month parquet files.

Cache layout: `data/klines/{symbol}_{YYYY-MM}.parquet` — one file per UTC month.
A backtest range that touches months already on disk hits cache; only the
months missing on disk are fetched. Re-running with different start/end on the
same data is then free.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pandas as pd

from bot.logger import get_logger

log = get_logger(__name__)

REST_URL = "https://api.bybit.com/v5/market/kline"
TESTNET_URL = "https://api-testnet.bybit.com/v5/market/kline"
BYBIT_RATE_LIMIT_RETCODE = 10006
RATE_LIMIT_MAX_RETRIES = 8
RATE_LIMIT_BASE_SLEEP_SECONDS = 1.0
PAGE_SLEEP_SECONDS = 0.12


# ---------- low-level fetch ----------

def fetch_klines(
    symbol: str,
    start_ms: int,
    end_ms: int,
    interval: str = "1",
    category: str = "linear",
    testnet: bool = False,
    page_size: int = 1000,
) -> pd.DataFrame:
    """Pull klines [start_ms, end_ms) inclusive of start, exclusive of end.
    Bybit returns newest-first; we paginate by `end` walking backwards then sort."""
    url = TESTNET_URL if testnet else REST_URL
    rows: list[list] = []
    cur_end = end_ms
    with httpx.Client(timeout=20.0) as client:
        while True:
            params = {
                "category": category,
                "symbol": symbol,
                "interval": interval,
                "start": start_ms,
                "end": cur_end,
                "limit": page_size,
            }
            retries = 0
            while True:
                r = client.get(url, params=params)
                r.raise_for_status()
                data = r.json()
                if data.get("retCode") == 0:
                    break
                if (
                    data.get("retCode") == BYBIT_RATE_LIMIT_RETCODE
                    and retries < RATE_LIMIT_MAX_RETRIES
                ):
                    delay = min(30.0, RATE_LIMIT_BASE_SLEEP_SECONDS * (2 ** retries))
                    log.warning(
                        "klines.rate_limited",
                        symbol=symbol,
                        retry=retries + 1,
                        sleep_seconds=delay,
                    )
                    time.sleep(delay)
                    retries += 1
                    continue
                raise RuntimeError(f"bybit error: {data}")
            chunk = data["result"]["list"]
            if not chunk:
                break
            rows.extend(chunk)
            oldest_ts = int(chunk[-1][0])
            if oldest_ts <= start_ms:
                break
            cur_end = oldest_ts - 1
            time.sleep(PAGE_SLEEP_SECONDS)
    if not rows:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"])
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"])
    df["timestamp"] = df["timestamp"].astype("int64")
    for col in ("open", "high", "low", "close", "volume", "turnover"):
        df[col] = df[col].astype("float64")
    df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    df = df[(df["timestamp"] >= start_ms) & (df["timestamp"] < end_ms)]
    return df


# ---------- per-month cache ----------

def _month_path(cache_dir: Path, symbol: str, year: int, month: int) -> Path:
    return cache_dir / f"{symbol}_{year:04d}-{month:02d}.parquet"


def _month_bounds_ms(year: int, month: int) -> tuple[int, int]:
    """Returns [start_ms, end_ms) for a UTC calendar month."""
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def _months_in_range(start_ms: int, end_ms: int) -> list[tuple[int, int]]:
    """List of (year, month) tuples covering [start_ms, end_ms)."""
    if end_ms <= start_ms:
        return []
    start = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
    end = datetime.fromtimestamp((end_ms - 1) / 1000, tz=timezone.utc)
    out: list[tuple[int, int]] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def _load_month(
    cache_dir: Path, symbol: str, year: int, month: int, testnet: bool
) -> pd.DataFrame:
    """Return the kline DataFrame for one UTC month, fetching+caching if needed.

    A partial month at the head/tail of "now" is allowed: we fetch what's there
    and cache. We only treat the cache as authoritative for fully-elapsed months;
    for the current month we top up if the cache is older than its end_ms.
    """
    p = _month_path(cache_dir, symbol, year, month)
    start_ms, end_ms = _month_bounds_ms(year, month)
    now_ms = int(time.time() * 1000)

    if p.exists():
        df = pd.read_parquet(p)
        # Fully past month: trust the cache fully.
        if now_ms >= end_ms:
            return df
        # Current/future month: top up if we have less than the latest minute available.
        latest_ts = df["timestamp"].max() if not df.empty else start_ms
        if latest_ts >= now_ms - 60_000:
            return df
        log.info("klines.topup", symbol=symbol, ym=f"{year}-{month:02d}",
                 latest_ts=int(latest_ts), now_ms=now_ms)
        more = fetch_klines(symbol, int(latest_ts) + 1, min(end_ms, now_ms), testnet=testnet)
        if not more.empty:
            df = pd.concat([df, more]).drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
            df.to_parquet(p, index=False)
        return df

    log.info("klines.fetch_month", symbol=symbol, ym=f"{year}-{month:02d}")
    df = fetch_klines(symbol, start_ms, min(end_ms, now_ms), testnet=testnet)
    if not df.empty:
        cache_dir.mkdir(parents=True, exist_ok=True)
        df.to_parquet(p, index=False)
    return df


def load_or_fetch(
    symbol: str,
    start_ms: int,
    end_ms: int,
    cache_dir: str | Path = "data/klines",
    testnet: bool = False,
) -> pd.DataFrame:
    """Return the requested kline range [start_ms, end_ms), assembling from
    per-month cache files. Missing months are fetched and saved on the way."""
    cdir = Path(cache_dir)
    cdir.mkdir(parents=True, exist_ok=True)
    months = _months_in_range(start_ms, end_ms)
    if not months:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"])

    parts: list[pd.DataFrame] = []
    cached = 0
    for y, m in months:
        if _month_path(cdir, symbol, y, m).exists():
            cached += 1
        df = _load_month(cdir, symbol, y, m, testnet=testnet)
        if not df.empty:
            parts.append(df)
    log.info("klines.range_loaded", symbol=symbol,
             months=len(months), cached_months=cached,
             start_ms=start_ms, end_ms=end_ms)
    if not parts:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"])
    df = pd.concat(parts).drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    return df[(df["timestamp"] >= start_ms) & (df["timestamp"] < end_ms)].reset_index(drop=True)


def df_to_candles(df: pd.DataFrame, symbol: str):
    """Convert a kline dataframe into a list of Candle objects."""
    from bot.models import Candle
    out = []
    for row in df.itertuples(index=False):
        out.append(Candle(
            symbol=symbol,
            timestamp=row.timestamp / 1000.0,
            open=float(row.open),
            high=float(row.high),
            low=float(row.low),
            close=float(row.close),
            volume=float(row.volume),
            confirm=True,
        ))
    return out
