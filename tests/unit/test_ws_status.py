from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest

from bot.exchange import bybit_live
from bot.exchange.bybit_live import (
    BybitLive,
    _log_ws_warning,
    _patch_websocket_bybit_ipv4_preference,
    _summarize_ws_status,
)


def test_summarize_unconfigured_streams_report_disabled():
    out = _summarize_ws_status(
        now_ts=1000.0,
        public_last_msg_ts=None,
        private_last_msg_ts=None,
        public_symbols=[],
        private_subscribed=False,
    )
    assert out["public"]["status"] == "disabled"
    assert out["private"]["status"] == "disabled"
    assert out["public"]["last_msg_age_seconds"] is None
    assert out["public"]["subscribed_symbols"] == []


def test_summarize_recent_messages_report_connected():
    out = _summarize_ws_status(
        now_ts=1000.0,
        public_last_msg_ts=995.0,
        private_last_msg_ts=990.0,
        public_symbols=["BTCUSDT", "ETHUSDT"],
        private_subscribed=True,
    )
    assert out["public"]["status"] == "connected"
    assert out["private"]["status"] == "connected"
    assert out["public"]["last_msg_age_seconds"] == 5.0
    assert out["private"]["last_msg_age_seconds"] == 10.0
    assert out["public"]["subscribed_symbols"] == ["BTCUSDT", "ETHUSDT"]


def test_summarize_stale_public_reports_stale():
    out = _summarize_ws_status(
        now_ts=1000.0,
        public_last_msg_ts=800.0,   # 200s old, public 1m kline → stale
        private_last_msg_ts=995.0,  # fresh
        public_symbols=["BTCUSDT"],
        private_subscribed=True,
    )
    assert out["public"]["status"] == "stale"
    assert out["private"]["status"] == "connected"


def test_summarize_private_idle_reports_connected_idle_not_stale():
    out = _summarize_ws_status(
        now_ts=10_000.0,
        public_last_msg_ts=9_995.0,
        private_last_msg_ts=8_000.0,  # 2000s old, past 900s threshold
        public_symbols=["BTCUSDT"],
        private_subscribed=True,
    )
    assert out["public"]["status"] == "connected"
    assert out["private"]["status"] == "connected_idle"
    assert out["private"]["last_msg_age_seconds"] == 2000.0


def test_summarize_private_thread_dead_reports_stale_even_when_recent():
    out = _summarize_ws_status(
        now_ts=1000.0,
        public_last_msg_ts=995.0,
        private_last_msg_ts=990.0,  # fresh, but thread died
        public_symbols=["BTCUSDT"],
        private_subscribed=True,
        private_thread_alive=False,
    )
    assert out["public"]["status"] == "connected"
    assert out["private"]["status"] == "stale"


def test_summarize_public_thread_dead_reports_stale_even_when_recent():
    out = _summarize_ws_status(
        now_ts=1000.0,
        public_last_msg_ts=995.0,
        private_last_msg_ts=995.0,
        public_symbols=["BTCUSDT"],
        private_subscribed=True,
        public_thread_alive=False,
    )
    assert out["public"]["status"] == "stale"
    assert out["private"]["status"] == "connected"


def test_ws_thread_alive_helper():
    class _FakeAliveThread:
        @staticmethod
        def is_alive() -> bool:
            return True

    class _FakeDeadThread:
        @staticmethod
        def is_alive() -> bool:
            return False

    class _WSWithThread:
        def __init__(self, thread) -> None:
            self.wst = thread

    class _WSNoThread:
        pass

    assert BybitLive._ws_thread_alive(None) is False
    assert BybitLive._ws_thread_alive(_WSWithThread(_FakeAliveThread())) is True
    assert BybitLive._ws_thread_alive(_WSWithThread(_FakeDeadThread())) is False
    # Fresh ws without a `wst` attribute yet → assume alive until reset.
    assert BybitLive._ws_thread_alive(_WSNoThread()) is True


def test_summarize_subscribed_but_never_received_message_reports_connecting():
    out = _summarize_ws_status(
        now_ts=1000.0,
        public_last_msg_ts=None,
        private_last_msg_ts=None,
        public_symbols=["BTCUSDT"],
        private_subscribed=True,
    )
    assert out["public"]["status"] == "connecting"
    assert out["private"]["status"] == "connecting"


def test_ws_warning_logger_throttles_repeated_messages(monkeypatch):
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(bybit_live, "_WS_WARNING_LAST_TS", {})
    monkeypatch.setattr(bybit_live, "WS_WARNING_THROTTLE_SECONDS", 60.0)
    times = iter([1000.0, 1010.0, 1070.0])
    monkeypatch.setattr(bybit_live.time, "time", lambda: next(times))
    monkeypatch.setattr(
        bybit_live.log,
        "warning",
        lambda event, **fields: calls.append((event, fields)),
    )

    _log_ws_warning("public_ws_connect_failed", key="public", error="timeout")
    _log_ws_warning("public_ws_connect_failed", key="public", error="timeout")
    _log_ws_warning("public_ws_connect_failed", key="public", error="timeout")

    assert [event for event, _ in calls] == [
        "public_ws_connect_failed",
        "public_ws_connect_failed",
    ]


def test_bybit_ws_addrinfo_patch_prefers_ipv4(monkeypatch):
    import socket
    import websocket._http

    monkeypatch.setattr(bybit_live, "_WEBSOCKET_IPV4_PATCHED", False)

    def fake_original(hostname, port, is_secure, proxy):
        return [
            (socket.AF_INET6, socket.SOCK_STREAM, socket.SOL_TCP, "", ("::1", port, 0, 0)),
            (socket.AF_INET, socket.SOCK_STREAM, socket.SOL_TCP, "", ("127.0.0.1", port)),
        ], False, None

    monkeypatch.setattr(websocket._http, "_get_addrinfo_list", fake_original)

    _patch_websocket_bybit_ipv4_preference()

    out, _, _ = websocket._http._get_addrinfo_list("stream-testnet.bybit.com", 443, True, None)
    assert [addr[0] for addr in out] == [socket.AF_INET]

    other, _, _ = websocket._http._get_addrinfo_list("example.com", 443, True, None)
    assert [addr[0] for addr in other] == [socket.AF_INET6, socket.AF_INET]


def test_dashboard_status_includes_ws_status_when_file_present(tmp_path: Path, monkeypatch):
    from bot.dashboard.service import DashboardService
    (tmp_path / "config").mkdir()
    (tmp_path / "data" / "state" / "system").mkdir(parents=True)
    (tmp_path / "logs").mkdir()
    (tmp_path / "reports").mkdir()
    import yaml
    (tmp_path / "config" / "bot.yaml").write_text(
        yaml.safe_dump({
            "sizing": {"margin_usd": 66, "leverage": 10},
            "offsets": {"entry_offset_bps": 5, "tp_offset_bps": 100},
            "merge_timer": {"seconds": 1800, "policy": "first_fill"},
            "fees": {"maker_bps": -1.0, "taker_bps": 5.5},
            "risk": {
                "max_notional_per_symbol_usd": 10000,
                "max_notional_account_usd": 50000,
                "max_consecutive_losses": 5,
                "cooldown_minutes": 60,
                "daily_loss_limit_usd": 5000,
            },
            "signal": {"engine": "placeholder_rsi", "params": {}},
            "loop": {"reconcile_every_seconds": 30},
        }),
        encoding="utf-8",
    )
    (tmp_path / "config" / "symbols.yaml").write_text(
        yaml.safe_dump({"active": ["BTCUSDT"]}),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)
    payload = {
        "generated_at_utc": "2026-05-14T04:00:00+00:00",
        "public": {"status": "connected", "last_msg_age_seconds": 3.1, "subscribed_symbols": ["BTCUSDT"]},
        "private": {"status": "stale", "last_msg_age_seconds": 180.5, "subscribed": True},
    }
    (tmp_path / "data" / "state" / "system" / "ws_status.json").write_text(
        json.dumps(payload), encoding="utf-8",
    )

    status = DashboardService(tmp_path).status()
    assert status["ws_status"] == payload


class _SlowWS:
    """Mimics pybit WebSocket: constructor sleeps to simulate a slow network init."""

    def __init__(self, *args, **kwargs):
        time.sleep(0.5)
        self.subs: list[tuple] = []

    def kline_stream(self, *, interval, symbol, callback):
        time.sleep(0.2)
        self.subs.append(("kline", interval, symbol))

    def order_stream(self, *, callback):
        time.sleep(0.2)
        self.subs.append(("order",))

    def execution_stream(self, *, callback):
        time.sleep(0.2)
        self.subs.append(("execution",))

    def position_stream(self, *, callback):
        time.sleep(0.2)
        self.subs.append(("position",))

    def exit(self):
        pass


class _ImmediateKlineWS:
    """Subscribes successfully and immediately emits one confirmed candle."""

    def __init__(self):
        self.subs: list[tuple] = []

    def kline_stream(self, *, interval, symbol, callback):
        self.subs.append(("kline", interval, symbol))
        callback({
            "topic": f"kline.{interval}.{symbol}",
            "data": [{
                "confirm": True,
                "end": 1_000,
                "open": "100",
                "high": "101",
                "low": "99",
                "close": "100.5",
                "volume": "12",
            }],
        })

    def exit(self):
        pass


def _bare_adapter() -> BybitLive:
    adapter = BybitLive.__new__(BybitLive)
    adapter._testnet = True
    adapter._leverage = 10
    adapter._public_ws = None
    adapter._private_ws = None
    adapter._public_symbols = []
    adapter._private_subscribed = False
    adapter._public_last_msg_ts = None
    adapter._private_last_msg_ts = None
    adapter._public_connected_ts = None
    adapter._private_connected_ts = None
    adapter._public_last_error = None
    adapter._private_last_error = None
    adapter._kline_q = asyncio.Queue()
    adapter._user_q = asyncio.Queue()
    adapter._loop = asyncio.get_running_loop()
    adapter._stopping = False
    adapter._instruments = {}
    return adapter


@pytest.mark.asyncio
async def test_stream_klines_does_not_block_event_loop(monkeypatch):
    """Slow WS init must not freeze other asyncio tasks."""
    adapter = _bare_adapter()

    monkeypatch.setattr(adapter, "_make_public_ws", lambda: _SlowWS())

    ticks: list[float] = []

    async def heartbeat():
        for _ in range(10):
            ticks.append(time.monotonic())
            await asyncio.sleep(0.05)

    async def consume_one():
        gen = adapter.stream_klines(["BTCUSDT", "ETHUSDT"], interval="1")
        await gen.__anext__.__self__.aclose() if False else None  # type: ignore[func-returns-value]
        # Drive init by starting the generator, then cancel the consume.
        agen = gen
        try:
            await asyncio.wait_for(agen.__anext__(), timeout=2.0)
        except asyncio.TimeoutError:
            pass
        finally:
            await agen.aclose()

    start = time.monotonic()
    await asyncio.gather(heartbeat(), consume_one())
    elapsed = time.monotonic() - start

    # Heartbeat ticked 10 times at 50ms each, so should finish in well under 1s.
    # Slow WS init alone is ~0.5s + 2×0.2s = 0.9s; if it blocked the loop
    # heartbeat would also take ~0.9s+. Confirm both ran concurrently:
    assert len(ticks) == 10
    inter_tick = max(b - a for a, b in zip(ticks, ticks[1:]))
    assert inter_tick < 0.30, f"loop was blocked: max inter-tick gap {inter_tick:.3f}s"


@pytest.mark.asyncio
async def test_stream_klines_retries_after_initial_ws_timeout(monkeypatch):
    adapter = _bare_adapter()
    monkeypatch.setattr(bybit_live, "WS_RECONNECT_BASE_SECONDS", 0.01)
    monkeypatch.setattr(bybit_live, "WS_RECONNECT_MAX_SECONDS", 0.01)
    attempts = 0

    def make_public_ws():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutError("[Errno 60] Operation timed out")
        return _ImmediateKlineWS()

    monkeypatch.setattr(adapter, "_make_public_ws", make_public_ws)

    agen = adapter.stream_klines(["BTCUSDT"], interval="1")
    try:
        candle = await asyncio.wait_for(agen.__anext__(), timeout=1.0)
    finally:
        await agen.aclose()

    assert attempts == 2
    assert candle.symbol == "BTCUSDT"
    assert candle.close == 100.5
    assert adapter._public_last_error is None


def test_dashboard_status_ws_status_is_none_when_file_missing(tmp_path: Path, monkeypatch):
    from bot.dashboard.service import DashboardService
    (tmp_path / "config").mkdir()
    (tmp_path / "data" / "state").mkdir(parents=True)
    (tmp_path / "logs").mkdir()
    (tmp_path / "reports").mkdir()
    import yaml
    (tmp_path / "config" / "bot.yaml").write_text(
        yaml.safe_dump({
            "sizing": {"margin_usd": 66, "leverage": 10},
            "offsets": {"entry_offset_bps": 5, "tp_offset_bps": 100},
            "merge_timer": {"seconds": 1800, "policy": "first_fill"},
            "fees": {"maker_bps": -1.0, "taker_bps": 5.5},
            "risk": {
                "max_notional_per_symbol_usd": 10000,
                "max_notional_account_usd": 50000,
                "max_consecutive_losses": 5,
                "cooldown_minutes": 60,
                "daily_loss_limit_usd": 5000,
            },
            "signal": {"engine": "placeholder_rsi", "params": {}},
            "loop": {"reconcile_every_seconds": 30},
        }),
        encoding="utf-8",
    )
    (tmp_path / "config" / "symbols.yaml").write_text(
        yaml.safe_dump({"active": ["BTCUSDT"]}),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)

    status = DashboardService(tmp_path).status()
    assert status["ws_status"] is None
