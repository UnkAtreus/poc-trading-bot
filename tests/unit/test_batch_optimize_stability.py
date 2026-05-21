from __future__ import annotations

import argparse
import csv
import importlib.util
import sys
from pathlib import Path

from bot.config import load_settings


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "batch_optimize_stability.py"
SPEC = importlib.util.spec_from_file_location("batch_optimize_stability", SCRIPT_PATH)
batch = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = batch
assert SPEC.loader is not None
SPEC.loader.exec_module(batch)


def _args(**overrides):
    values = {
        "start": "2024-01-01",
        "end": "2024-02-01",
        "symbols": "BTCUSDT,ETHUSDT",
        "signal": "",
        "margins": "10,10,20",
        "leverages": "3",
        "account_caps": "5000",
        "symbol_caps": "500",
        "tp_offsets": "30,30",
        "max_candidates": None,
        "shard_count": 1,
        "shard_index": 0,
        "stop_bep_bps": None,
        "stop_symbol_loss": None,
        "stop_account_dd_pct": None,
        "stop_max_hold_hours": None,
        "stop_monthly_profit_lock_pct": None,
        "stop_monthly_dd_pct": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_build_candidates_dedupes_by_candidate_id():
    settings = load_settings()

    candidates = batch._build_candidates(_args(), settings)

    assert len(candidates) == 2
    assert len({candidate.candidate_id for candidate in candidates}) == 2
    assert [candidate.margin_usd for candidate in candidates] == [10.0, 20.0]


def test_select_shard_splits_candidates_deterministically():
    settings = load_settings()
    candidates = batch._build_candidates(
        _args(margins="10,20,30,40", tp_offsets="30"),
        settings,
    )

    shard_0 = batch._select_shard(candidates, _args(shard_count=2, shard_index=0))
    shard_1 = batch._select_shard(candidates, _args(shard_count=2, shard_index=1))

    assert [candidate.margin_usd for candidate in shard_0] == [10.0, 30.0]
    assert [candidate.margin_usd for candidate in shard_1] == [20.0, 40.0]


def test_format_shard_path_avoids_csv_write_conflicts():
    path = batch._format_shard_path(
        Path("logs/batch.csv"),
        _args(shard_count=8, shard_index=3),
    )

    assert path == Path("logs/batch_shard03of08.csv")


def test_format_shard_path_supports_templates():
    path = batch._format_shard_path(
        Path("logs/batch_{shard_index}_of_{shard_count}.csv"),
        _args(shard_count=8, shard_index=3),
    )

    assert path == Path("logs/batch_3_of_8.csv")


def test_prune_rejects_order_notional_above_symbol_cap():
    settings = load_settings()
    candidate = batch._build_candidates(
        _args(margins="200", leverages="3", symbol_caps="500", account_caps="5000", tp_offsets="30"),
        settings,
    )[0]

    assert batch._prune_reason(candidate) == "notional_gt_symbol_cap"


def test_report_decision_prefers_launch_pass_then_reduce_size_then_no_trade():
    base_row = {
        "candidate_id": "id",
        "start": "2024-01-01",
        "end": "2024-02-01",
        "symbols": "BTCUSDT",
        "margin_usd": "10",
        "leverage": "3",
        "account_cap": "5000",
        "symbol_cap": "500",
        "tp_offset_bps": "30",
        "stability_score": "1.0",
        "roi_pct": "0.5",
        "max_drawdown_pct": "2",
        "final_open_exposure": "100",
        "error": "",
    }

    trade_report = batch._render_report(
        [{**base_row, "safe": "True", "stable": "True", "launch_pass": "True"}],
        Path("out.csv"),
    )
    reduce_report = batch._render_report(
        [{**base_row, "safe": "True", "stable": "False", "launch_pass": "False"}],
        Path("out.csv"),
    )
    no_trade_report = batch._render_report(
        [{**base_row, "safe": "False", "stable": "False", "launch_pass": "False"}],
        Path("out.csv"),
    )

    assert "`trade`" in trade_report
    assert "`reduce_size`" in reduce_report
    assert "`no_trade`" in no_trade_report


def test_progress_line_shows_finish_estimate(monkeypatch):
    settings = load_settings()
    candidate = batch._build_candidates(_args(margins="10", tp_offsets="30"), settings)[0]
    monkeypatch.setattr(batch.time, "monotonic", lambda: 130.0)

    line = batch._progress_line(
        2,
        10,
        candidate,
        {"safe": True, "stable": False},
        started_at=100.0,
        processed_this_run=2,
    )

    assert "[2/10 20.0%]" in line
    assert "avg=15.0s/candidate" in line
    assert "remaining=8" in line
    assert "eta=00:02:00" in line
    assert "finish_at=" in line


def test_merge_csv_rows_dedupes_by_candidate_id(tmp_path):
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    for path, rows in [
        (first, [{"candidate_id": "same", "net_pnl": "1"}, {"candidate_id": "a", "net_pnl": "2"}]),
        (second, [{"candidate_id": "same", "net_pnl": "3"}, {"candidate_id": "b", "net_pnl": "4"}]),
    ]:
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["candidate_id", "net_pnl"])
            writer.writeheader()
            writer.writerows(rows)

    rows = batch._merge_csv_rows([first, second])

    assert len(rows) == 3
    assert {row["candidate_id"] for row in rows} == {"same", "a", "b"}
    assert [row for row in rows if row["candidate_id"] == "same"][0]["net_pnl"] == "3"
