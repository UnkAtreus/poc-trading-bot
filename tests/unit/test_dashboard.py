from __future__ import annotations

import json
import os
import stat
import sys
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
import yaml
from fastapi.testclient import TestClient

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
from bot.dashboard.app import create_app
from bot.dashboard.service import DashboardService
from bot.monitoring.alerting import (
    AlertingConfig,
    AlertSecrets,
    deliver_if_new,
    load_alert_secrets,
    load_alerting,
    save_alert_secrets,
    save_alerting,
)
from bot.monitoring.ai_context import build_context
from bot.monitoring.live_monitor import (
    MonitorIssue,
    MonitorPosition,
    WalletSnapshot,
    append_monitor_history,
    evaluate_snapshot,
)


BOT_YAML = {
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
    "account": {"initial_equity": 30000, "margin_mode": "cross"},
    "liquidation": {
        "enabled": True,
        "maintenance_margin_rate": 0.005,
        "near_liq_buffer_pct": 10,
        "funding_stress_bps": 0,
    },
    "optimizer": {
        "safety_gates": {
            "reject_liquidated": True,
            "reject_near_liquidation": True,
            "max_drawdown_pct": 25,
            "max_final_open_exposure_usd": 5000,
        }
    },
    "regime_router": {"enabled": False, "no_trade_on_unsafe": True},
    "signal": {
        "engine": "trend_filter",
        "params": {
            "inner": "grid",
            "inner_anchor_period": 200,
            "inner_entry_bps": 30,
            "inner_step_bps": 15,
            "max_trend_bps": 30,
        },
    },
    "loop": {"reconcile_every_seconds": 30},
}

SYMBOLS_YAML = {"active": ["BTCUSDT", "ETHUSDT"], "overrides": {}}


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / "logs").mkdir()
    (tmp_path / "reports").mkdir()
    (tmp_path / "data" / "state").mkdir(parents=True)
    (tmp_path / "config" / "bot.yaml").write_text(yaml.safe_dump(BOT_YAML), encoding="utf-8")
    (tmp_path / "config" / "symbols.yaml").write_text(yaml.safe_dump(SYMBOLS_YAML), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)
    monkeypatch.delenv("BYBIT_API_KEY", raising=False)
    monkeypatch.delenv("BYBIT_API_SECRET", raising=False)
    monkeypatch.delenv("MODE", raising=False)
    return tmp_path


@pytest.fixture
def client(repo: Path) -> TestClient:
    app = create_app(repo)
    return TestClient(app)


def test_healthz_no_auth_required(client: TestClient) -> None:
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json() == {"ok": "true"}


def test_dashboard_returns_503_when_password_missing(client: TestClient) -> None:
    res = client.get("/", auth=("admin", "anything"))
    assert res.status_code == 503


def test_dashboard_requires_auth(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHBOARD_PASSWORD", "secret")
    client = TestClient(create_app(repo))
    res = client.get("/")
    assert res.status_code == 401
    res = client.get("/", auth=("admin", "wrong"))
    assert res.status_code == 401
    res = client.get("/", auth=("admin", "secret"))
    assert res.status_code == 200


def test_status_payload_redacts_secrets(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHBOARD_PASSWORD", "secret")
    monkeypatch.setenv("BYBIT_API_KEY", "REAL_KEY")
    monkeypatch.setenv("BYBIT_API_SECRET", "REAL_SECRET")
    client = TestClient(create_app(repo))
    res = client.get("/api/status", auth=("admin", "secret"))
    assert res.status_code == 200
    body = res.text
    assert "REAL_KEY" not in body
    assert "REAL_SECRET" not in body
    payload = res.json()
    assert payload["settings"]["has_api_key"] is True
    assert payload["settings"]["has_api_secret"] is True
    assert "bybit_api_key" not in payload["settings"]
    assert "bybit_api_secret" not in payload["settings"]


def test_kill_switch_create_and_clear(repo: Path) -> None:
    service = DashboardService(repo)
    kill_path = repo / "data" / "state" / "KILL"
    assert not kill_path.exists()
    service.create_kill()
    assert kill_path.exists()
    assert service.kill_active()
    service.clear_kill()
    assert not kill_path.exists()
    service.clear_kill()


def test_log_events_filter_by_event_and_symbol(repo: Path) -> None:
    log = repo / "logs" / "bot.log"
    log.write_text(
        "\n".join(
            [
                "2026-05-12T08:44:14.537084Z [info     ] heartbeat states={'BTCUSDT': 'IDLE'}",
                "2026-05-12T08:45:00.442999Z [warning  ] entry_rejected reason=cap symbol=BTCUSDT",
                "2026-05-12T08:46:00.218178Z [warning  ] entry_rejected reason=cap symbol=ETHUSDT",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    service = DashboardService(repo)

    all_rows = service.log_events()
    assert len(all_rows) == 3

    rejected = service.log_events(event="entry_rejected")
    assert len(rejected) == 2
    assert {r["symbol"] for r in rejected} == {"BTCUSDT", "ETHUSDT"}

    eth_only = service.log_events(symbol="ETHUSDT")
    assert len(eth_only) == 1
    assert eth_only[0]["symbol"] == "ETHUSDT"

    limited = service.log_events(limit=1)
    assert len(limited) == 1


def test_backtest_rejects_unsupported_signal(repo: Path) -> None:
    service = DashboardService(repo)
    with pytest.raises(ValueError, match="unsupported signal"):
        service.start_backtest(
            {
                "start": "2024-01-01",
                "end": "2024-01-02",
                "symbols_picked": ["BTCUSDT"],
                "initial_equity": "3000",
                "signal_engine": "evil_signal",
            }
        )


def test_backtest_rejects_unsafe_symbols(repo: Path) -> None:
    service = DashboardService(repo)
    with pytest.raises(ValueError, match="invalid symbols"):
        service.start_backtest(
            {
                "start": "2024-01-01",
                "end": "2024-01-02",
                "symbols_extra": "BTC; rm -rf /",
                "initial_equity": "3000",
                "signal_engine": "",
            }
        )


def test_backtest_rejects_bad_date(repo: Path) -> None:
    service = DashboardService(repo)
    with pytest.raises(ValueError, match="date must be"):
        service.start_backtest(
            {
                "start": "not-a-date",
                "end": "2024-01-02",
                "symbols_picked": ["BTCUSDT"],
                "initial_equity": "3000",
                "signal_engine": "",
            }
        )


def test_report_text_rejects_path_outside_repo(repo: Path, tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.md"
    outside.write_text("secret", encoding="utf-8")
    service = DashboardService(repo)
    with pytest.raises(ValueError):
        service.report_text("../" + outside.name)


def test_report_text_reads_repo_file(repo: Path) -> None:
    target = repo / "reports" / "sample.md"
    target.write_text("# hello", encoding="utf-8")
    service = DashboardService(repo)
    assert service.report_text("reports/sample.md").startswith("# hello")


def test_preview_config_round_trip(repo: Path) -> None:
    service = DashboardService(repo)
    preview = service.preview_config(
        {
            "margin_usd": "70",
            "leverage": "10",
            "entry_offset_bps": "5",
            "tp_offset_bps": "100",
            "max_notional_per_symbol_usd": "10000",
            "max_notional_account_usd": "50000",
            "daily_loss_limit_usd": "5000",
            "active_symbols": "BTCUSDT, ETHUSDT",
        }
    )
    bot_yaml = yaml.safe_load(preview["bot_yaml"])
    sym_yaml = yaml.safe_load(preview["symbols_yaml"])
    assert bot_yaml["sizing"]["margin_usd"] == 70
    assert sym_yaml["active"] == ["BTCUSDT", "ETHUSDT"]


def test_preview_config_rejects_empty_symbols(repo: Path) -> None:
    service = DashboardService(repo)
    with pytest.raises(ValueError, match="active_symbols must not be empty"):
        service.preview_config(
            {
                "margin_usd": "70",
                "leverage": "10",
                "entry_offset_bps": "5",
                "tp_offset_bps": "100",
                "max_notional_per_symbol_usd": "10000",
                "max_notional_account_usd": "50000",
                "daily_loss_limit_usd": "5000",
                "active_symbols": "",
            }
        )


def test_log_events_route_filters(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = repo / "logs" / "bot.log"
    log.write_text(
        "2026-05-12T08:44:14.537084Z [info     ] heartbeat states={'BTCUSDT': 'IDLE'}\n"
        "2026-05-12T08:45:00.442999Z [warning  ] entry_rejected reason=cap symbol=BTCUSDT\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DASHBOARD_PASSWORD", "secret")
    client = TestClient(create_app(repo))
    res = client.get("/api/log-events?event=heartbeat", auth=("admin", "secret"))
    assert res.status_code == 200
    body = res.json()
    assert len(body["events"]) == 1
    assert body["events"][0]["event"] == "heartbeat"


def test_kill_action_requires_typed_confirmation(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHBOARD_PASSWORD", "secret")
    client = TestClient(create_app(repo))
    res = client.post("/actions/kill", data={"confirm": "nope"}, auth=("admin", "secret"))
    assert res.status_code == 400
    assert not (repo / "data" / "state" / "KILL").exists()

    res = client.post(
        "/actions/kill",
        data={"confirm": "KILL"},
        auth=("admin", "secret"),
        follow_redirects=False,
    )
    assert res.status_code == 303
    assert (repo / "data" / "state" / "KILL").exists()


# ---------- Alerting / history / charts ----------


def _make_snapshot(*, tmp_path: Path, issues=None, total_equity: float = 1000.0, daily_pnl: float = 12.5):
    settings = Settings(
        env=EnvSettings(mode=Mode.TESTNET),
        bot=BotConfig(
            sizing=Sizing(margin_usd=66, leverage=10),
            offsets=Offsets(entry_offset_bps=5, tp_offset_bps=100),
            merge_timer=MergeTimer(seconds=1800, policy="first_fill"),
            fees=Fees(maker_bps=-1.0, taker_bps=5.5),
            risk=RiskConfig(
                max_notional_per_symbol_usd=10000,
                max_notional_account_usd=50000,
                max_consecutive_losses=5,
                cooldown_minutes=60,
                daily_loss_limit_usd=5000,
            ),
            signal=SignalConfig(engine="placeholder_rsi", params={}),
            loop=LoopConfig(reconcile_every_seconds=30),
        ),
        symbols=SymbolsConfig(active=["BTCUSDT"]),
    )
    wallet = WalletSnapshot(
        total_equity=total_equity,
        total_wallet_balance=total_equity,
        total_available_balance=total_equity,
        usdt_equity=total_equity,
        usdt_unrealised_pnl=0.0,
        usdt_cum_realised_pnl=0.0,
    )
    empty_log = tmp_path / "empty.log"
    if not empty_log.exists():
        empty_log.write_text("", encoding="utf-8")
    context = build_context(empty_log)
    snapshot = evaluate_snapshot(
        settings=settings,
        context=context,
        local_states={},
        positions=[],
        open_orders=[],
        wallet=wallet,
        daily_closed_pnl=daily_pnl,
        bot_alive=True,
        heartbeat_stale_seconds=180,
        now_ts=1_700_000_000.0,
        repeated_failure_threshold=3,
    )
    if issues:
        snapshot = replace(snapshot, issues=list(issues), severity="CRITICAL")
    return snapshot


def test_alerting_config_load_default(tmp_path: Path) -> None:
    cfg = load_alerting(tmp_path / "missing.yaml")
    assert cfg.enabled is True
    assert cfg.heartbeat_stale_seconds == 180.0
    assert cfg.delivery.telegram.enabled is False


def test_alerting_save_and_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "alerting.yaml"
    cfg = AlertingConfig(heartbeat_stale_seconds=99)
    save_alerting(path, cfg)
    assert load_alerting(path).heartbeat_stale_seconds == 99


def test_alert_secrets_save_writes_0600(tmp_path: Path) -> None:
    path = tmp_path / "secrets.json"
    save_alert_secrets(path, AlertSecrets(telegram_bot_token="abc1234"))
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600
    loaded = load_alert_secrets(path)
    assert loaded.telegram_bot_token == "abc1234"


def test_alert_secrets_masked_on_api(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHBOARD_PASSWORD", "secret")
    save_alert_secrets(repo / "data" / "secrets" / "alerting.json", AlertSecrets(discord_webhook_url="https://discord.example/webhook/SUPER_SECRET_TOKEN"))
    client = TestClient(create_app(repo))
    res = client.get("/alerting", auth=("admin", "secret"))
    assert res.status_code == 200
    assert "SUPER_SECRET_TOKEN" not in res.text
    assert "OKEN" in res.text  # last 4 of token still shown


def test_deliver_if_new_skips_when_no_critical(tmp_path: Path) -> None:
    snapshot = _make_snapshot(tmp_path=tmp_path)
    result = deliver_if_new(
        snapshot,
        config=AlertingConfig(delivery={"telegram": {"enabled": True}, "discord": {"enabled": True}}),
        secrets=AlertSecrets(telegram_bot_token="t", telegram_chat_id="c", discord_webhook_url="https://discord/x"),
        fingerprint_path=tmp_path / "fp.txt",
    )
    assert result["delivered"] is False
    assert result["reason"] == "no_critical_issues"


def test_deliver_if_new_sends_then_dedupes(tmp_path: Path) -> None:
    snapshot = _make_snapshot(tmp_path=tmp_path, issues=[MonitorIssue("CRITICAL", "account_cap_exceeded", "x"), MonitorIssue("CRITICAL", "fatal_api_error", "y")])
    config = AlertingConfig(delivery={"telegram": {"enabled": True}, "discord": {"enabled": True}})
    secrets = AlertSecrets(telegram_bot_token="bot", telegram_chat_id="42", discord_webhook_url="https://discord.example/webhook/x")
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={"ok": True})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    fp_path = tmp_path / "fp.txt"

    first = deliver_if_new(snapshot, config=config, secrets=secrets, fingerprint_path=fp_path, client=client)
    assert first["delivered"] is True
    assert any("api.telegram.org" in c for c in calls)
    assert any("discord.example" in c for c in calls)
    assert fp_path.exists()

    calls.clear()
    second = deliver_if_new(snapshot, config=config, secrets=secrets, fingerprint_path=fp_path, client=client)
    assert second["delivered"] is False
    assert second["reason"] == "duplicate_fingerprint"
    assert calls == []
    client.close()


def test_deliver_if_new_skips_when_disabled(tmp_path: Path) -> None:
    snapshot = _make_snapshot(tmp_path=tmp_path, issues=[MonitorIssue("CRITICAL", "code", "msg")])
    result = deliver_if_new(
        snapshot,
        config=AlertingConfig(enabled=False),
        secrets=AlertSecrets(),
        fingerprint_path=tmp_path / "fp.txt",
    )
    assert result["delivered"] is False
    assert result["reason"] == "alerting_disabled"


def test_history_appends_one_row_per_call(repo: Path, tmp_path: Path) -> None:
    service = DashboardService(repo)
    snap1 = _make_snapshot(tmp_path=tmp_path, total_equity=1000)
    snap2 = _make_snapshot(tmp_path=tmp_path, total_equity=1050)
    append_monitor_history(snap1, service.history_path)
    append_monitor_history(snap2, service.history_path)
    rows = service.equity_history()
    assert len(rows) == 2
    assert rows[0]["total_equity"] == 1000
    assert rows[1]["total_equity"] == 1050


def test_balance_route_renders(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHBOARD_PASSWORD", "secret")
    client = TestClient(create_app(repo))
    res = client.get("/balance", auth=("admin", "secret"))
    assert res.status_code == 200
    assert "Equity over time" in res.text


def test_alerting_route_renders(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHBOARD_PASSWORD", "secret")
    client = TestClient(create_app(repo))
    res = client.get("/alerting", auth=("admin", "secret"))
    assert res.status_code == 200
    assert "Alert thresholds" in res.text


def test_alerting_save_requires_confirm(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHBOARD_PASSWORD", "secret")
    client = TestClient(create_app(repo))
    res = client.post(
        "/alerting/save",
        data={
            "enabled": "1",
            "heartbeat_stale_seconds": "120",
            "repeated_failure_threshold": "3",
            "failure_window_seconds": "900",
            "daily_loss_alert_usd": "5000",
            "confirm": "nope",
        },
        auth=("admin", "secret"),
    )
    assert res.status_code == 400

    res = client.post(
        "/alerting/save",
        data={
            "enabled": "1",
            "heartbeat_stale_seconds": "120",
            "repeated_failure_threshold": "3",
            "failure_window_seconds": "900",
            "daily_loss_alert_usd": "5000",
            "confirm": "SAVE",
        },
        auth=("admin", "secret"),
        follow_redirects=False,
    )
    assert res.status_code == 303
    assert (repo / "config" / "alerting.yaml").exists()


def test_backtest_csv_rejects_path_outside_repo(repo: Path, tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.csv"
    outside.write_text("a,b\n1,2\n", encoding="utf-8")
    service = DashboardService(repo)
    with pytest.raises(ValueError):
        service.backtest_csv("../" + outside.name)


def test_backtest_csv_reads_repo_file(repo: Path) -> None:
    target = repo / "logs" / "sample.csv"
    target.write_text("period,net_pnl,roi_pct\n2024-01,100,1.0\n2024-02,150,1.5\n", encoding="utf-8")
    service = DashboardService(repo)
    data = service.backtest_csv("logs/sample.csv")
    assert data["headers"] == ["period", "net_pnl", "roi_pct"]
    assert len(data["rows"]) == 2


# ---------- Backtest form, registry, runner ----------


def test_available_signals_lists_safe_set(repo: Path) -> None:
    service = DashboardService(repo)
    signals = service.available_signals()
    assert "bollinger_bands" in signals
    assert "ema_crossover" in signals
    assert "evil_signal" not in signals


def test_start_backtest_writes_spec_and_registry(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    class FakeProc:
        pid = 4242

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return FakeProc()

    monkeypatch.setattr("bot.dashboard.service.subprocess.Popen", fake_popen)

    service = DashboardService(repo)
    result = service.start_backtest(
        {
            "start": "2024-01-01",
            "end": "2024-02-01",
            "symbols_picked": ["BTCUSDT", "ETHUSDT"],
            "symbols_extra": "SOLUSDT",
            "initial_equity": "3000",
            "signal_engine": "bollinger_bands",
            "signal_params": "period=20:num_std=2.0",
        }
    )
    assert result["pid"] == 4242
    assert Path(repo / result["registry"]).exists()
    spec_path = repo / "data" / "state" / "backtests" / f"{result['ts']}.spec.json"
    assert spec_path.exists()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    assert spec["summary"]["signal"] == "bollinger_bands:period=20:num_std=2.0"
    assert spec["summary"]["symbols"] == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    assert "--by-month" in spec["cmd"]
    assert "--with-risk" in spec["cmd"]


def test_list_backtest_jobs_returns_recent(repo: Path) -> None:
    directory = repo / "data" / "state" / "backtests"
    directory.mkdir(parents=True)
    (directory / "1700000001.json").write_text(json.dumps({"ts": 1700000001, "status": "finished"}), encoding="utf-8")
    (directory / "1700000002.json").write_text(json.dumps({"ts": 1700000002, "status": "running"}), encoding="utf-8")
    (directory / "1700000003.spec.json").write_text("{}", encoding="utf-8")
    service = DashboardService(repo)
    jobs = service.list_backtest_jobs()
    assert {j["ts"] for j in jobs} == {1700000001, 1700000002}


def test_dashboard_backtest_runner_writes_report(tmp_path: Path) -> None:
    log_path = tmp_path / "out.txt"
    report_path = tmp_path / "report.md"
    registry_path = tmp_path / "registry.json"
    spec = {
        "ts": "1700000000",
        "cmd": [sys.executable, "-c", "print('BACKTEST REPORT\\nnet PnL : 100\\nmax DD  : 5')"],
        "log_path": str(log_path),
        "report_path": str(report_path),
        "registry_path": str(registry_path),
        "summary": {
            "started_at_utc": "2024-01-01T00:00:00",
            "signal": "bollinger_bands",
            "symbols": ["BTCUSDT"],
            "start": "2024-01-01",
            "end": "2024-01-02",
            "initial_equity": 3000,
        },
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")

    import importlib.util
    runner_path = Path(__file__).resolve().parents[2] / "scripts" / "dashboard_backtest_runner.py"
    module_spec = importlib.util.spec_from_file_location("runner_mod", runner_path)
    runner_mod = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(runner_mod)  # type: ignore[union-attr]

    rc = runner_mod.main(["dashboard_backtest_runner.py", str(spec_path)])
    assert rc == 0
    assert report_path.exists()
    text = report_path.read_text(encoding="utf-8")
    assert "Dashboard Backtest" in text
    assert "BACKTEST REPORT" in text
    assert "net PnL" in text
    reg = json.loads(registry_path.read_text(encoding="utf-8"))
    assert reg["status"] == "finished"
    assert reg["exit_code"] == 0


def test_api_backtests_lists_jobs(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    directory = repo / "data" / "state" / "backtests"
    directory.mkdir(parents=True)
    (directory / "1700000001.json").write_text(json.dumps({"ts": 1700000001, "status": "finished", "report_path": "reports/x.md"}), encoding="utf-8")
    monkeypatch.setenv("DASHBOARD_PASSWORD", "secret")
    client = TestClient(create_app(repo))
    res = client.get("/api/backtests", auth=("admin", "secret"))
    assert res.status_code == 200
    body = res.json()
    assert len(body["jobs"]) == 1
    assert body["jobs"][0]["status"] == "finished"


def test_api_report_returns_markdown_text(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (repo / "reports" / "demo.md").write_text("# Hello\n\nWorld", encoding="utf-8")
    monkeypatch.setenv("DASHBOARD_PASSWORD", "secret")
    client = TestClient(create_app(repo))
    res = client.get("/api/report?path=reports/demo.md", auth=("admin", "secret"))
    assert res.status_code == 200
    body = res.json()
    assert body["path"] == "reports/demo.md"
    assert body["text"].startswith("# Hello")


def test_api_report_rejects_outside_repo(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHBOARD_PASSWORD", "secret")
    client = TestClient(create_app(repo))
    res = client.get("/api/report?path=../../etc/passwd", auth=("admin", "secret"))
    assert res.status_code == 400


def test_balance_summary_drawdown_and_deltas(repo: Path) -> None:
    history_path = repo / "logs" / "live_monitor_history.jsonl"
    # Simulate 3 snapshots: 1000 -> 1100 (peak) -> 990 (drawdown).
    rows = [
        {"ts": "2026-05-12T00:00:00+00:00", "total_equity": 1000, "total_available_balance": 800, "usdt_cum_realised_pnl": 0, "daily_closed_pnl": 0},
        {"ts": "2026-05-12T06:00:00+00:00", "total_equity": 1100, "total_available_balance": 850, "usdt_cum_realised_pnl": 50, "daily_closed_pnl": 50},
        {"ts": "2026-05-12T12:00:00+00:00", "total_equity": 990, "total_available_balance": 700, "usdt_cum_realised_pnl": 40, "daily_closed_pnl": 40},
    ]
    history_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    monitor_payload = {
        "wallet": {
            "total_equity": 990,
            "total_available_balance": 700,
            "total_wallet_balance": 1000,
            "usdt_equity": 990,
            "usdt_unrealised_pnl": -10,
            "usdt_cum_realised_pnl": 40,
        },
        "positions": [
            {"symbol": "BTCUSDT", "side": "Buy", "size": 0.01, "mark_price": 50000, "avg_price": 50500, "unrealised_pnl": -5.0},
        ],
    }
    (repo / "logs" / "live_monitor.jsonl").write_text(json.dumps(monitor_payload) + "\n", encoding="utf-8")
    service = DashboardService(repo)
    s = service.balance_summary()
    assert s["current_equity"] == 990
    assert s["margin_in_use"] == pytest.approx(290)
    assert s["margin_utilization_pct"] == pytest.approx(290 / 990 * 100)
    assert s["peak_equity"] == 1100
    assert s["current_drawdown"] == pytest.approx(110)
    assert s["current_drawdown_pct"] == pytest.approx(10.0)
    assert s["max_drawdown"] == pytest.approx(110)
    assert s["max_drawdown_pct"] == pytest.approx(10.0)
    assert s["snapshots"] == 3
    assert s["per_symbol_unrealised"][0]["symbol"] == "BTCUSDT"
    assert len(s["daily_pnl"]) == 1
    assert s["daily_pnl"][0]["realised_delta"] == pytest.approx(40)


def test_balance_summary_empty_history(repo: Path) -> None:
    service = DashboardService(repo)
    s = service.balance_summary()
    assert s["snapshots"] == 0
    assert s["peak_equity"] == 0
    assert s["max_drawdown"] == 0


def test_api_balance_summary_route(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHBOARD_PASSWORD", "secret")
    client = TestClient(create_app(repo))
    res = client.get("/api/balance-summary", auth=("admin", "secret"))
    assert res.status_code == 200
    body = res.json()
    assert "current_equity" in body and "peak_equity" in body


def test_log_analysis_aggregates_events(repo: Path) -> None:
    log = repo / "logs" / "bot.log"
    log.write_text(
        "\n".join(
            [
                "2026-05-12T08:44:14.537084Z [info     ] heartbeat states={'BTCUSDT': 'IDLE'}",
                "2026-05-12T08:44:30.000000Z [info     ] entry_placed symbol=BTCUSDT link_id=BTC-B-entry-1",
                "2026-05-12T08:45:00.442999Z [warning  ] entry_rejected symbol=BTCUSDT reason=cap",
                "2026-05-12T08:46:00.218178Z [error    ] place_order_failed symbol=ETHUSDT error='rejected'",
                "2026-05-12T08:47:00.000000Z [error    ] tp_place_rejected symbol=BTCUSDT reason=PostOnly",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    service = DashboardService(repo)
    a = service.log_analysis(bucket_minutes=15)
    assert a["available"] is True
    assert a["total"] == 5
    assert a["critical"] == 2  # place_order_failed + tp_place_rejected
    assert a["warning"] == 1   # entry_rejected
    top = {e["event"]: e["count"] for e in a["top_events"]}
    assert top["entry_rejected"] == 1
    assert top["place_order_failed"] == 1
    assert any(e["event"] == "tp_place_rejected" and e["is_critical"] for e in a["top_events"])
    syms = {r["symbol"]: r for r in a["per_symbol"]}
    assert syms["BTCUSDT"]["count"] == 3
    assert syms["BTCUSDT"]["critical"] == 1
    assert syms["ETHUSDT"]["critical"] == 1
    assert a["last_heartbeat_ts"] == "2026-05-12T08:44:14.537084Z"
    assert any(ev["event"] == "tp_place_rejected" for ev in a["recent_critical"])
    assert len(a["timeline"]) >= 1


def test_log_analysis_returns_unavailable_when_no_log(repo: Path) -> None:
    service = DashboardService(repo)
    a = service.log_analysis()
    assert a["available"] is False


def test_api_log_analysis_route(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (repo / "logs" / "bot.log").write_text(
        "2026-05-12T08:44:14.537084Z [info     ] heartbeat states={'BTCUSDT': 'IDLE'}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DASHBOARD_PASSWORD", "secret")
    client = TestClient(create_app(repo))
    res = client.get("/api/log-analysis", auth=("admin", "secret"))
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is True
    assert body["total"] >= 1


def test_trading_overview_joins_tps_and_totals(repo: Path) -> None:
    monitor_payload = {
        "positions": [
            {"symbol": "BTCUSDT", "side": "Buy", "size": 0.01, "avg_price": 50000, "mark_price": 50500, "unrealised_pnl": 5.0},
            {"symbol": "ETHUSDT", "side": "Sell", "size": 0.5, "avg_price": 3000, "mark_price": 3050, "unrealised_pnl": -25.0},
        ],
        "open_orders": [
            {"symbol": "BTCUSDT", "side": "Sell", "qty": 0.01, "price": 50600, "purpose": "tp", "reduce_only": True, "link_id": "x"},
            {"symbol": "ETHUSDT", "side": "Buy", "qty": 0.5, "price": 2950, "purpose": "merge", "reduce_only": True, "link_id": "y"},
            {"symbol": "SOLUSDT", "side": "Buy", "qty": 1, "price": 100, "purpose": "entry", "reduce_only": False, "link_id": "z"},
        ],
        "daily_closed_pnl": 12.34,
    }
    (repo / "logs" / "live_monitor.jsonl").write_text(json.dumps(monitor_payload) + "\n", encoding="utf-8")
    service = DashboardService(repo)
    overview = service.trading_overview()
    assert len(overview["rows"]) == 2
    totals = overview["totals"]
    assert totals["longs"] == 1
    assert totals["shorts"] == 1
    assert totals["winners"] == 1
    assert totals["losers"] == 1
    assert totals["pending_tps"] == 2  # one TP + one merge order joined
    assert totals["entries"] == 1
    assert totals["merges"] == 1
    assert overview["daily_closed_pnl"] == pytest.approx(12.34)
    btc = next(r for r in overview["rows"] if r["symbol"] == "BTCUSDT")
    assert btc["tp_price"] == pytest.approx(50600.0)
    assert btc["tp_distance_pct"] == pytest.approx((50600 - 50500) / 50500 * 100)
    # leverage from bot.yaml fixture is 10x; margin = notional / 10
    assert btc["margin"] == pytest.approx(btc["notional"] / 10.0)
    assert btc["roi_pct"] == pytest.approx(btc["unrealised_pnl"] / btc["margin"] * 100.0)
    eth = next(r for r in overview["rows"] if r["symbol"] == "ETHUSDT")
    # short with price up = price_diff_pct negative
    assert eth["price_diff_pct"] < 0


def test_trading_overview_no_positions(repo: Path) -> None:
    service = DashboardService(repo)
    overview = service.trading_overview()
    assert overview["rows"] == []
    assert overview["totals"]["open_notional"] == 0
    assert overview["best"] is None
    assert overview["worst"] is None


def test_api_trading_overview_route(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHBOARD_PASSWORD", "secret")
    client = TestClient(create_app(repo))
    res = client.get("/api/trading-overview", auth=("admin", "secret"))
    assert res.status_code == 200
    body = res.json()
    assert "rows" in body and "totals" in body


def test_positions_breakdown_filters_zero(repo: Path) -> None:
    monitor_payload = {
        "positions": [
            {"symbol": "BTCUSDT", "size": 0.01, "mark_price": 50000, "avg_price": 49000, "side": "Buy"},
            {"symbol": "ETHUSDT", "size": 0.0, "mark_price": 3000, "avg_price": 3000, "side": "Buy"},
        ]
    }
    (repo / "logs" / "live_monitor.jsonl").write_text(json.dumps(monitor_payload) + "\n", encoding="utf-8")
    service = DashboardService(repo)
    breakdown = service.positions_breakdown()
    assert len(breakdown) == 1
    assert breakdown[0]["symbol"] == "BTCUSDT"
    assert breakdown[0]["notional"] == pytest.approx(500.0)
