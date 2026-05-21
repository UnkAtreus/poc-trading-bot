from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "soak_check.py"


def _load_module():
    import sys
    spec = importlib.util.spec_from_file_location("soak_check_mod", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["soak_check_mod"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def soak():
    return _load_module()


def _write_log(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _ts(seconds_from_anchor: float, anchor: str = "2026-05-14T04:00:00.000000Z") -> str:
    base = datetime.fromisoformat(anchor.replace("Z", "+00:00"))
    return (base.timestamp() + seconds_from_anchor and
            datetime.fromtimestamp(base.timestamp() + seconds_from_anchor, tz=timezone.utc)
            .isoformat().replace("+00:00", "Z"))


def test_gather_evidence_counts_events_and_filters_window(soak, tmp_path):
    log_dir = tmp_path / "logs"
    state_dir = tmp_path / "state"
    log_dir.mkdir()
    state_dir.mkdir()
    monitor_md = tmp_path / "live_monitor.md"
    monitor_md.write_text(
        "# Live Monitor\n- Severity: `OK`\n- Bot alive: `True`\n- Kill triggered: `False`\n",
        encoding="utf-8",
    )

    inside = [
        "2026-05-14T03:55:00.000000Z [info     ] heartbeat states={}",
        "2026-05-14T03:56:00.000000Z [info     ] heartbeat states={}",
        "2026-05-14T03:57:00.000000Z [warning  ] reconcile.failed symbol=BTCUSDT error='boom'",
        "2026-05-14T03:58:00.000000Z [info     ] entry_filled symbol=BTCUSDT qty=0.001 price=50000",
        "2026-05-14T03:59:00.000000Z [info     ] tp_filled symbol=BTCUSDT qty=0.001 price=50050",
    ]
    outside = [
        "2026-05-13T02:00:00.000000Z [warning  ] reconcile.failed symbol=BTCUSDT error='old'",
    ]
    _write_log(log_dir / "bot.log", outside + inside)

    now = datetime(2026, 5, 14, 4, 0, 0, tzinfo=timezone.utc)
    ev = soak.gather_evidence(
        log_dir=log_dir, state_dir=state_dir, monitor_md=monitor_md,
        window_hours=1.0, now=now,
    )

    assert ev.heartbeats == 2
    assert ev.entries_filled == 1
    assert ev.tps_filled == 1
    assert ev.event_counts["reconcile.failed"] == 1
    assert "reconcile.failed" in ev.event_counts
    assert ev.monitor_severity == "OK"
    assert ev.bot_alive is True
    assert ev.kill_active is False


def test_gather_evidence_detects_bot_restarts_and_heartbeat_gap(soak, tmp_path):
    log_dir = tmp_path / "logs"
    state_dir = tmp_path / "state"
    log_dir.mkdir()
    state_dir.mkdir()
    monitor_md = tmp_path / "live_monitor.md"
    monitor_md.write_text("# Live Monitor\n", encoding="utf-8")

    lines = [
        "2026-05-14T03:00:00.000000Z [info     ] boot.banner mode=testnet",
        "2026-05-14T03:00:30.000000Z [info     ] heartbeat states={}",
        "2026-05-14T03:05:00.000000Z [info     ] heartbeat states={}",  # 270s gap
        "2026-05-14T03:30:00.000000Z [info     ] boot.banner mode=testnet",
    ]
    _write_log(log_dir / "bot.log", lines)

    now = datetime(2026, 5, 14, 4, 0, 0, tzinfo=timezone.utc)
    ev = soak.gather_evidence(
        log_dir=log_dir, state_dir=state_dir, monitor_md=monitor_md,
        window_hours=2.0, now=now,
    )

    assert ev.bot_restarts == 2
    assert ev.max_heartbeat_gap_seconds is not None
    assert ev.max_heartbeat_gap_seconds >= 270.0 - 1


def test_gather_evidence_collects_stuck_states(soak, tmp_path):
    log_dir = tmp_path / "logs"
    state_dir = tmp_path / "state"
    log_dir.mkdir()
    state_dir.mkdir()
    monitor_md = tmp_path / "live_monitor.md"
    monitor_md.write_text("# Live Monitor\n", encoding="utf-8")
    (state_dir / "BTCUSDT.json").write_text(
        json.dumps({"symbol": "BTCUSDT", "state": "IDLE", "position_size": 0}),
        encoding="utf-8",
    )
    (state_dir / "ETHUSDT.json").write_text(
        json.dumps({"symbol": "ETHUSDT", "state": "MERGE_PENDING", "position_size": 0.5,
                    "first_fill_ts": 1000.0}),
        encoding="utf-8",
    )
    (state_dir / "XRPUSDT.json").write_text(
        json.dumps({"symbol": "XRPUSDT", "state": "DUST_STRANDED", "position_size": 0.1}),
        encoding="utf-8",
    )
    _write_log(log_dir / "bot.log", [])

    ev = soak.gather_evidence(
        log_dir=log_dir, state_dir=state_dir, monitor_md=monitor_md,
        window_hours=24.0, now=datetime(2026, 5, 14, 4, 0, 0, tzinfo=timezone.utc),
    )

    stuck_symbols = {s["symbol"] for s in ev.stuck_states}
    assert stuck_symbols == {"ETHUSDT", "XRPUSDT"}


def test_evaluate_passes_clean_window(soak):
    ev = soak.SoakEvidence(
        window_start_utc="2026-05-13T04:00:00+00:00",
        window_end_utc="2026-05-14T04:00:00+00:00",
        bot_restarts=0,
        heartbeats=1440,
        max_heartbeat_gap_seconds=45.0,
        entries_filled=12,
        tps_filled=12,
        event_counts={},
        stuck_states=[],
        monitor_severity="OK",
        bot_alive=True,
        kill_active=False,
    )
    passed, fails = soak.evaluate(ev)
    assert passed is True
    assert fails == []


def test_evaluate_fails_on_reconcile_failed(soak):
    ev = soak.SoakEvidence(
        window_start_utc="x", window_end_utc="y",
        bot_restarts=0, heartbeats=100, max_heartbeat_gap_seconds=10.0,
        entries_filled=1, tps_filled=1,
        event_counts={"reconcile.failed": 3},
        stuck_states=[], monitor_severity="OK", bot_alive=True, kill_active=False,
    )
    passed, fails = soak.evaluate(ev)
    assert passed is False
    assert any("reconcile.failed" in f for f in fails)


def test_evaluate_fails_on_heartbeat_gap_above_threshold(soak):
    ev = soak.SoakEvidence(
        window_start_utc="x", window_end_utc="y",
        bot_restarts=0, heartbeats=10, max_heartbeat_gap_seconds=240.0,
        entries_filled=0, tps_filled=0,
        event_counts={}, stuck_states=[],
        monitor_severity="OK", bot_alive=True, kill_active=False,
    )
    passed, fails = soak.evaluate(ev)
    assert passed is False
    assert any("heartbeat" in f.lower() for f in fails)


def test_render_evidence_pack_contains_expected_sections(soak):
    ev = soak.SoakEvidence(
        window_start_utc="2026-05-13T04:00:00+00:00",
        window_end_utc="2026-05-14T04:00:00+00:00",
        bot_restarts=0, heartbeats=1440, max_heartbeat_gap_seconds=10.0,
        entries_filled=5, tps_filled=5,
        event_counts={"heartbeat": 1440},
        stuck_states=[],
        monitor_severity="OK", bot_alive=True, kill_active=False,
    )
    md = soak.render_evidence_pack(ev, passed=True, fails=[])
    for section in ("# Soak Check", "## Window", "## Auto checks",
                    "## Evidence", "## Question for the LLM"):
        assert section in md
    assert "PASS" in md
