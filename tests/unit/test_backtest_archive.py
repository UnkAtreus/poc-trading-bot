from __future__ import annotations

import csv
import json

from bot.backtest.archive import archive_record, settings_snapshot
from bot.config import load_settings


def test_settings_snapshot_redacts_api_secrets():
    settings = load_settings()
    settings = settings.model_copy(
        update={
            "env": settings.env.model_copy(
                update={
                    "bybit_api_key": "key-secret",
                    "bybit_api_secret": "secret-secret",
                }
            )
        }
    )

    snapshot = settings_snapshot(settings)
    encoded = json.dumps(snapshot)

    assert "key-secret" not in encoded
    assert "secret-secret" not in encoded
    assert snapshot["env"]["has_api_key"] is True
    assert snapshot["env"]["has_api_secret"] is True


def test_archive_record_writes_json_jsonl_and_csv_index(tmp_path):
    path = archive_record(
        {
            "kind": "unit_backtest",
            "label": "sample",
            "scope": {"start": "2024-01-01", "end": "2024-02-01", "symbols": ["BTCUSDT"]},
            "strategy": {"signal_name": "grid", "signal_params": {"entry_bps": 50}},
            "metrics": {
                "initial_equity": 30000,
                "trades": 12,
                "win_rate_pct": 75.0,
                "net_pnl": 123.45,
                "roi_pct": 0.41,
                "max_drawdown_pct": 2.0,
                "liquidated": False,
                "near_liquidation": False,
                "final_open_exposure": 0.0,
            },
            "outputs": {"csv_path": "logs/sample.csv", "report_path": "reports/sample.md"},
        },
        root=tmp_path,
    )

    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["kind"] == "unit_backtest"
    assert payload["archive"]["json_path"] == str(path)

    jsonl = tmp_path / "data" / "backtests" / "index.jsonl"
    assert jsonl.is_file()
    assert len(jsonl.read_text(encoding="utf-8").splitlines()) == 1

    with (tmp_path / "data" / "backtests" / "index.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["kind"] == "unit_backtest"
    assert rows[0]["symbols"] == "BTCUSDT"
    assert rows[0]["signal"] == "grid_e50"
    assert rows[0]["roi_pct"] == "0.41"
