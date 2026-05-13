from __future__ import annotations

from pathlib import Path

from bot.config import (
    BotConfig,
    EnvSettings,
    Fees,
    LoopConfig,
    MergeTimer,
    Mode,
    Offsets,
    RiskConfig,
    Settings,
    SignalConfig,
    Sizing,
    SymbolsConfig,
)
from bot.monitoring.ai_context import build_context
from bot.monitoring.live_monitor import (
    MonitorOrder,
    MonitorPosition,
    WalletSnapshot,
    evaluate_snapshot,
    load_local_states,
    run_monitor,
    write_alerts_markdown,
    write_monitor_jsonl,
    write_monitor_markdown,
)


def _settings() -> Settings:
    return Settings(
        env=EnvSettings(mode=Mode.TESTNET),
        bot=BotConfig(
            sizing=Sizing(margin_usd=5, leverage=2),
            offsets=Offsets(entry_offset_bps=5, tp_offset_bps=100),
            merge_timer=MergeTimer(seconds=1800, policy="first_fill"),
            fees=Fees(maker_bps=-1.0, taker_bps=5.5),
            risk=RiskConfig(
                max_notional_per_symbol_usd=100,
                max_notional_account_usd=300,
                max_consecutive_losses=3,
                cooldown_minutes=60,
                daily_loss_limit_usd=20,
            ),
            signal=SignalConfig(engine="placeholder_rsi", params={}),
            loop=LoopConfig(reconcile_every_seconds=30),
        ),
        symbols=SymbolsConfig(active=["BTCUSDT", "ETHUSDT"], overrides={}),
    )


def _log(path: Path, ts: str = "2026-05-12T08:44:14.537084Z") -> Path:
    path.write_text(
        f"{ts} [info     ] heartbeat states={{'BTCUSDT': 'IN_POSITION_TP_PENDING', 'ETHUSDT': 'IDLE'}}\n",
        encoding="utf-8",
    )
    return path


def test_missing_reduce_only_exit_is_critical(tmp_path):
    log_file = _log(tmp_path / "bot.log")
    context = build_context(log_file)
    local_states = {
        "BTCUSDT": {
            "symbol": "BTCUSDT",
            "state": "IN_POSITION_TP_PENDING",
            "direction": "LONG",
            "position_size": 0.01,
            "bep": 80000.0,
        }
    }

    snapshot = evaluate_snapshot(
        settings=_settings(),
        context=context,
        local_states=local_states,
        positions=[MonitorPosition("BTCUSDT", "Buy", 0.01, 80000.0, 80000.0)],
        open_orders=[],
        wallet=None,
        daily_closed_pnl=0.0,
        bot_alive=True,
        heartbeat_stale_seconds=999999999.0,
        repeated_failure_threshold=3,
        now_ts=1778575454.0,
    )

    assert snapshot.severity == "CRITICAL"
    assert any(i.code == "missing_reduce_only_exit" for i in snapshot.issues)


def test_reduce_only_exit_keeps_snapshot_ok(tmp_path):
    log_file = _log(tmp_path / "bot.log")
    context = build_context(log_file)

    snapshot = evaluate_snapshot(
        settings=_settings(),
        context=context,
        local_states={
            "BTCUSDT": {
                "symbol": "BTCUSDT",
                "state": "IN_POSITION_TP_PENDING",
                "direction": "LONG",
                "position_size": 0.001,
                "bep": 80000.0,
            }
        },
        positions=[MonitorPosition("BTCUSDT", "Buy", 0.001, 80000.0, 80000.0)],
        open_orders=[MonitorOrder("BTCUSDT", "Sell", 0.001, 80800.0, "BTCUSDT-S-tp-ABC", True, "tp")],
        wallet=WalletSnapshot(1000.0, 1000.0, 900.0, 1000.0, 0.0, 0.0),
        daily_closed_pnl=0.0,
        bot_alive=True,
        heartbeat_stale_seconds=999999999.0,
        repeated_failure_threshold=3,
        now_ts=1778575454.0,
    )

    assert snapshot.severity == "OK"
    assert snapshot.issues == []


def test_partial_reduce_only_exit_is_critical(tmp_path):
    log_file = _log(tmp_path / "bot.log")
    context = build_context(log_file)

    snapshot = evaluate_snapshot(
        settings=_settings(),
        context=context,
        local_states={
            "BTCUSDT": {
                "symbol": "BTCUSDT",
                "state": "IN_POSITION_TP_PENDING",
                "direction": "LONG",
                "position_size": 0.01,
                "bep": 80000.0,
            }
        },
        positions=[MonitorPosition("BTCUSDT", "Buy", 0.01, 80000.0, 80000.0)],
        open_orders=[MonitorOrder("BTCUSDT", "Sell", 0.005, 80800.0, "BTCUSDT-S-tp-ABC", True, "tp")],
        wallet=None,
        daily_closed_pnl=0.0,
        bot_alive=True,
        heartbeat_stale_seconds=999999999.0,
        repeated_failure_threshold=3,
        now_ts=1778575454.0,
    )

    assert snapshot.severity == "CRITICAL"
    assert any(i.code == "missing_reduce_only_exit" for i in snapshot.issues)


def test_repeated_exit_failures_are_critical(tmp_path):
    log_file = tmp_path / "bot.log"
    log_file.write_text(
        "\n".join(
            [
                "2026-05-12T08:44:14.537084Z [info     ] heartbeat states={'BTCUSDT': 'IDLE'}",
                "2026-05-12T08:45:00.000000Z [warning  ] tp_place_rejected symbol=BTCUSDT link_id=L1 reason='bad'",
                "2026-05-12T08:45:01.000000Z [warning  ] tp_place_rejected symbol=BTCUSDT link_id=L2 reason='bad'",
                "2026-05-12T08:45:02.000000Z [warning  ] tp_place_rejected symbol=BTCUSDT link_id=L3 reason='bad'",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    snapshot = evaluate_snapshot(
        settings=_settings(),
        context=build_context(log_file),
        local_states={},
        positions=[],
        open_orders=[],
        wallet=None,
        daily_closed_pnl=0.0,
        bot_alive=True,
        heartbeat_stale_seconds=999999999.0,
        repeated_failure_threshold=3,
        now_ts=1778575454.0,
    )

    assert snapshot.severity == "CRITICAL"
    assert any(i.code == "repeated_log_failure" for i in snapshot.issues)


def test_run_monitor_writes_kill_file_on_critical(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = _log(log_dir / "bot.log")
    state_dir = tmp_path / "state"
    state_dir.mkdir()

    class FakeClient:
        def get_positions(self, symbols):
            return [MonitorPosition("BTCUSDT", "Buy", 0.01, 80000.0, 80000.0)]

        def get_open_orders(self, symbols):
            return []

        def get_wallet(self):
            return None

        def get_daily_closed_pnl(self, symbols):
            return 0.0

    snapshot = run_monitor(
        _settings(),
        log_file=log_file,
        state_dir=state_dir,
        process_pattern=None,
        heartbeat_stale_seconds=999999999.0,
        write_kill=True,
        client=FakeClient(),  # type: ignore[arg-type]
    )

    assert snapshot.severity == "KILL_TRIGGERED"
    assert (state_dir / "KILL").exists()


def test_report_writers_create_compact_files(tmp_path):
    log_file = _log(tmp_path / "bot.log")
    snapshot = evaluate_snapshot(
        settings=_settings(),
        context=build_context(log_file),
        local_states={},
        positions=[],
        open_orders=[],
        wallet=None,
        daily_closed_pnl=0.0,
        bot_alive=True,
        heartbeat_stale_seconds=999999999.0,
        repeated_failure_threshold=3,
        now_ts=1778575454.0,
    )

    monitor_md = tmp_path / "live_monitor.md"
    alerts_md = tmp_path / "live_alerts.md"
    monitor_jsonl = tmp_path / "live_monitor.jsonl"
    write_monitor_markdown(snapshot, monitor_md)
    write_alerts_markdown(snapshot, alerts_md)
    write_monitor_jsonl(snapshot, monitor_jsonl)

    assert "Live Monitor" in monitor_md.read_text(encoding="utf-8")
    assert "Live Alerts" in alerts_md.read_text(encoding="utf-8")
    assert monitor_jsonl.read_text(encoding="utf-8").startswith("{")


def test_load_local_states_ignores_bad_json(tmp_path):
    (tmp_path / "BTCUSDT.json").write_text('{"symbol":"BTCUSDT","state":"IDLE"}', encoding="utf-8")
    (tmp_path / "bad.json").write_text("{bad", encoding="utf-8")

    states = load_local_states(tmp_path)

    assert states["BTCUSDT"]["state"] == "IDLE"
    assert "bad" not in states
