#!/usr/bin/env python
"""Standalone Bybit latency probe.

Periodically pings REST `/v5/market/time` and subscribes to a public kline
WebSocket topic to measure:

  - REST round-trip time (local perf_counter delta)
  - WS event age (local arrival - server emit timestamp)

Writes a JSONL stream + a rolling markdown summary. Safe to run alongside the
live bot — uses its own pybit clients and never touches order state.

Run:
    uv run python scripts/probe_latency.py
    uv run python scripts/probe_latency.py --symbol BTCUSDT --interval 5

Stop with Ctrl-C; final summary is flushed on shutdown.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import signal as posix_signal
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bot.config import Mode, load_settings
from bot.logger import configure as configure_logging, get_logger


@dataclass
class RollingWindow:
    name: str
    samples: deque[float] = field(default_factory=lambda: deque(maxlen=200))

    def push(self, ms: float) -> None:
        self.samples.append(ms)

    def percentiles(self) -> dict[str, float]:
        if not self.samples:
            return {"count": 0}
        arr = sorted(self.samples)
        n = len(arr)
        def pct(p: float) -> float:
            if n == 1:
                return arr[0]
            k = max(0, min(n - 1, int(round(p * (n - 1)))))
            return arr[k]
        return {
            "count": n,
            "min": round(arr[0], 2),
            "p50": round(pct(0.50), 2),
            "p90": round(pct(0.90), 2),
            "p99": round(pct(0.99), 2),
            "max": round(arr[-1], 2),
            "mean": round(sum(arr) / n, 2),
        }


class LatencyProbe:
    def __init__(
        self,
        *,
        testnet: bool,
        symbol: str,
        interval_seconds: float,
        window_size: int,
        md_interval_seconds: float,
        output_jsonl: Path,
        output_md: Path,
    ) -> None:
        self.testnet = testnet
        self.symbol = symbol
        self.interval = interval_seconds
        self.md_interval = md_interval_seconds
        self.output_jsonl = output_jsonl
        self.output_md = output_md
        self.log = get_logger("probe")
        self.windows: dict[str, RollingWindow] = {
            "rest_server_time_ms": RollingWindow("rest.server_time", deque(maxlen=window_size)),
            "ws_kline_age_ms": RollingWindow("ws.kline_age", deque(maxlen=window_size)),
        }
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop = asyncio.Event()
        self._ws = None
        self._http = None
        self._jsonl_fp = None
        self._started_at = time.time()

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        from pybit.unified_trading import HTTP, WebSocket

        self._http = HTTP(testnet=self.testnet)

        self.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
        self.output_md.parent.mkdir(parents=True, exist_ok=True)
        self._jsonl_fp = self.output_jsonl.open("a", buffering=1)

        self.log.info(
            "probe.start",
            mode=("testnet" if self.testnet else "mainnet"),
            symbol=self.symbol,
            interval_s=self.interval,
            md_interval_s=self.md_interval,
            jsonl=str(self.output_jsonl),
            md=str(self.output_md),
        )

        self._ws = await asyncio.to_thread(
            WebSocket, testnet=self.testnet, channel_type="linear", retries=2, restart_on_error=False
        )
        await asyncio.to_thread(
            self._ws.kline_stream, interval=1, symbol=self.symbol, callback=self._on_kline,
        )

    async def stop(self) -> None:
        self._stop.set()
        if self._ws is not None:
            try:
                await asyncio.to_thread(self._ws.exit)
            except Exception as e:
                self.log.warning("probe.ws_exit_error", error=str(e))
        if self._jsonl_fp is not None:
            try:
                self._write_markdown()
            except Exception as e:
                self.log.warning("probe.md_write_error", error=str(e))
            self._jsonl_fp.close()

    def _emit(self, record: dict[str, Any]) -> None:
        if self._jsonl_fp is None:
            return
        try:
            self._jsonl_fp.write(json.dumps(record, separators=(",", ":")) + "\n")
        except Exception as e:
            self.log.warning("probe.jsonl_write_error", error=str(e))

    def _on_kline(self, msg: dict[str, Any]) -> None:
        try:
            data = msg.get("data") or []
            for k in data:
                if not k.get("confirm"):
                    continue
                server_end_ms = float(k["end"])
                age_ms = (time.time() * 1000.0) - server_end_ms
                self.windows["ws_kline_age_ms"].push(age_ms)
                self._emit({
                    "ts": time.time(),
                    "kind": "ws_kline_age",
                    "symbol": k.get("symbol", self.symbol),
                    "ms": round(age_ms, 2),
                })
        except Exception as e:
            self.log.warning("probe.kline_error", error=str(e))

    async def rest_loop(self) -> None:
        while not self._stop.is_set():
            try:
                t0 = time.perf_counter()
                _ = await asyncio.to_thread(self._http.get_server_time)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                self.windows["rest_server_time_ms"].push(elapsed_ms)
                self._emit({
                    "ts": time.time(),
                    "kind": "rest_server_time",
                    "ms": round(elapsed_ms, 2),
                })
            except Exception as e:
                self.log.warning("probe.rest_error", error=str(e))
                self._emit({
                    "ts": time.time(),
                    "kind": "rest_server_time_error",
                    "error": str(e),
                })
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval)
            except asyncio.TimeoutError:
                pass

    async def md_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._write_markdown()
            except Exception as e:
                self.log.warning("probe.md_write_error", error=str(e))
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.md_interval)
            except asyncio.TimeoutError:
                pass

    def _write_markdown(self) -> None:
        now = time.time()
        uptime_s = now - self._started_at
        from datetime import datetime, timezone
        updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

        lines: list[str] = []
        lines.append("# Latency probe — live rolling stats")
        lines.append("")
        lines.append(f"- Updated: `{updated}`")
        lines.append(f"- Uptime: `{uptime_s:.0f}s`")
        lines.append(f"- Mode: `{'testnet' if self.testnet else 'mainnet'}`")
        lines.append(f"- Symbol: `{self.symbol}`")
        lines.append(f"- REST probe interval: `{self.interval}s`")
        lines.append(f"- Rolling window size: `{max(w.samples.maxlen for w in self.windows.values())}`")
        lines.append("")
        lines.append("## Latency (ms)")
        lines.append("")
        lines.append("| Metric | n | min | p50 | p90 | p99 | max | mean |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
        for key, win in self.windows.items():
            p = win.percentiles()
            if p["count"] == 0:
                lines.append(f"| `{key}` | 0 | — | — | — | — | — | — |")
            else:
                lines.append(
                    f"| `{key}` | {p['count']} | {p['min']} | {p['p50']} | "
                    f"{p['p90']} | {p['p99']} | {p['max']} | {p['mean']} |"
                )
        lines.append("")
        lines.append("## Reference profiles (from `src/bot/backtest/execution.py`)")
        lines.append("")
        lines.append("| Profile | latency | cancel | slippage | min partial |")
        lines.append("|---|---:|---:|---:|---:|")
        lines.append("| `mainnet-like` | 0.30s | 0.50s | 1.0 bps | 50% |")
        lines.append("| `conservative` | 1.00s | 3.00s | 2.0 bps | 25% |")
        lines.append("")
        lines.append("- If observed `rest_server_time_ms.p90` stays under ~200ms and `ws_kline_age_ms.p90` under ~500ms, the live path matches the `mainnet-like` assumptions.")
        lines.append("- If either p90 exceeds 1000ms regularly, real execution is closer to the `conservative` profile and the strategy may underperform vs the mainnet-like backtest.")

        self.output_md.write_text("\n".join(lines) + "\n")


async def amain(args: argparse.Namespace) -> int:
    settings = load_settings()
    configure_logging(settings.env.log_level)
    log = get_logger("probe")

    if settings.env.mode is Mode.MAINNET and not args.allow_mainnet:
        log.error(
            "refusing_mainnet_probe",
            hint="Pass --allow-mainnet to probe against mainnet. By default we probe testnet only.",
        )
        return 2

    testnet = args.testnet
    if testnet is None:
        testnet = settings.env.mode is not Mode.MAINNET

    symbol = args.symbol or (settings.symbols.active[0] if settings.symbols.active else "BTCUSDT")

    probe = LatencyProbe(
        testnet=testnet,
        symbol=symbol,
        interval_seconds=args.interval,
        window_size=args.window,
        md_interval_seconds=args.md_interval,
        output_jsonl=args.output_jsonl,
        output_md=args.output_md,
    )

    loop = asyncio.get_running_loop()
    stop_signals = (posix_signal.SIGINT, posix_signal.SIGTERM)
    for sig in stop_signals:
        loop.add_signal_handler(sig, lambda: asyncio.create_task(probe.stop()))

    await probe.start()

    tasks = [
        asyncio.create_task(probe.rest_loop(), name="rest_loop"),
        asyncio.create_task(probe.md_loop(), name="md_loop"),
    ]
    try:
        await probe._stop.wait()
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await probe.stop()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bybit REST + WS latency probe. Safe to run alongside the live bot."
    )
    parser.add_argument(
        "--symbol", default=None,
        help="Public kline symbol to subscribe to. Defaults to first active in symbols.yaml.",
    )
    parser.add_argument(
        "--interval", type=float, default=5.0,
        help="REST probe interval in seconds (default: 5).",
    )
    parser.add_argument(
        "--window", type=int, default=200,
        help="Rolling window size for percentiles (default: 200 samples).",
    )
    parser.add_argument(
        "--md-interval", type=float, default=30.0,
        help="Markdown summary refresh interval in seconds (default: 30).",
    )
    parser.add_argument(
        "--output-jsonl", type=Path, default=Path("logs/latency_probe.jsonl"),
        help="Append per-sample records to this JSONL file.",
    )
    parser.add_argument(
        "--output-md", type=Path, default=Path("reports/latency_probe.md"),
        help="Rewrite this markdown summary every --md-interval seconds.",
    )
    parser.add_argument(
        "--testnet", dest="testnet", action="store_true", default=None,
        help="Force testnet (default: derived from .env MODE).",
    )
    parser.add_argument(
        "--mainnet", dest="testnet", action="store_false",
        help="Force mainnet (requires --allow-mainnet).",
    )
    parser.add_argument(
        "--allow-mainnet", action="store_true",
        help="Required to probe against mainnet endpoints.",
    )
    args = parser.parse_args()

    try:
        return asyncio.run(amain(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
