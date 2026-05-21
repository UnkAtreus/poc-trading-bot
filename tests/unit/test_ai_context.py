from __future__ import annotations

import json

import os

from bot.monitoring.ai_context import (
    build_context,
    latest_log,
    parse_log_line,
    write_jsonl,
    write_markdown,
)


def test_parse_console_log_line_with_ansi_fields():
    line = (
        "\x1b[2m2026-05-12T08:45:00.442999Z\x1b[0m "
        "[\x1b[33m\x1b[1mwarning  \x1b[0m] "
        "\x1b[1mentry_rejected                \x1b[0m "
        "\x1b[36mlink_id\x1b[0m=\x1b[35mHYPEUSDT-B-entry-ABC\x1b[0m "
        "\x1b[36mreason\x1b[0m=\x1b[35mper_symbol_cap(300.0)\x1b[0m "
        "\x1b[36msymbol\x1b[0m=\x1b[35mHYPEUSDT\x1b[0m"
    )

    event = parse_log_line(line)

    assert event is not None
    assert event.ts == "2026-05-12T08:45:00.442999Z"
    assert event.level == "warning"
    assert event.event == "entry_rejected"
    assert event.symbol == "HYPEUSDT"
    assert event.fields["reason"] == "per_symbol_cap(300.0)"


def test_build_context_extracts_heartbeat_critical_and_recent_events(tmp_path):
    log_file = tmp_path / "bot.log"
    log_file.write_text(
        "\n".join(
            [
                "2026-05-12T08:44:14.537084Z [info     ] heartbeat states={'BTCUSDT': 'IDLE', 'ETHUSDT': 'ENTRY_PENDING'}",
                "2026-05-12T08:45:00.442999Z [warning  ] entry_rejected link_id=HYPEUSDT-B-entry-ABC reason=per_symbol_cap(300.0) symbol=HYPEUSDT",
                "2026-05-12T08:46:00.218178Z [warning  ] place_order_failed symbol=BNBUSDT link_id=BNBUSDT-B-entry-XYZ error='rejected'",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    context = build_context(log_file)

    assert context.current_states == {"BTCUSDT": "IDLE", "ETHUSDT": "ENTRY_PENDING"}
    assert context.event_counts["heartbeat"] == 1
    assert context.event_counts["entry_rejected"] == 1
    assert context.critical_events[-1].event == "place_order_failed"
    assert context.recent_events[-1].symbol == "BNBUSDT"


def test_write_outputs_are_compact_ai_context(tmp_path):
    log_file = tmp_path / "bot.log"
    log_file.write_text(
        "2026-05-12T08:44:14.537084Z [info     ] heartbeat states={'BTCUSDT': 'IDLE'}\n",
        encoding="utf-8",
    )
    context = build_context(log_file)
    md = tmp_path / "live_ai_context.md"
    jsonl = tmp_path / "ai_context.jsonl"

    write_markdown(context, md)
    write_jsonl(context, jsonl)

    assert "Use this instead of pasting raw logs" in md.read_text(encoding="utf-8")
    first = json.loads(jsonl.read_text(encoding="utf-8").splitlines()[0])
    assert first["type"] == "summary"
    assert first["current_states"] == {"BTCUSDT": "IDLE"}


def test_ai_context_includes_monitor_summary_when_present(tmp_path):
    log_file = tmp_path / "bot.log"
    log_file.write_text(
        "2026-05-12T08:44:14.537084Z [info     ] heartbeat states={'BTCUSDT': 'IDLE'}\n",
        encoding="utf-8",
    )
    monitor = tmp_path / "live_monitor.md"
    monitor.write_text(
        "\n".join(
            [
                "# Live Monitor",
                "",
                "- Severity: `CRITICAL`",
                "- Kill triggered: `False`",
                "- Bot alive: `True`",
                "- Latest heartbeat: `2026-05-12T08:44:14.537084Z`",
                "",
                "## Issues",
                "",
                "- `CRITICAL` `missing_reduce_only_exit` `BTCUSDT`: Open position has no exit",
                "",
                "## Wallet",
            ]
        ),
        encoding="utf-8",
    )

    context = build_context(log_file, monitor_report=monitor)
    md = tmp_path / "live_ai_context.md"
    write_markdown(context, md)

    text = md.read_text(encoding="utf-8")
    assert "## Monitor Summary" in text
    assert "missing_reduce_only_exit" in text


def test_latest_log_prefers_bot_log_over_newer_non_bot_log(tmp_path):
    bot_log = tmp_path / "bot.log"
    bot_log.write_text(
        "2026-05-12T08:44:14.537084Z [info     ] heartbeat states={'BTCUSDT': 'IDLE'}\n",
        encoding="utf-8",
    )
    server_log = tmp_path / "dashboard_server.log"
    server_log.write_text(
        "INFO:     Started server process [47396]\n"
        "INFO:     Waiting for application startup.\n"
        "INFO:     Application startup complete.\n",
        encoding="utf-8",
    )
    older = bot_log.stat().st_mtime - 3600
    newer = bot_log.stat().st_mtime + 3600
    os.utime(bot_log, (older, older))
    os.utime(server_log, (newer, newer))

    assert latest_log(tmp_path, "*.log") == bot_log


def test_latest_log_falls_back_to_newest_when_no_bot_events(tmp_path):
    a = tmp_path / "a.log"
    b = tmp_path / "b.log"
    a.write_text("nothing parseable here\n", encoding="utf-8")
    b.write_text("also nothing\n", encoding="utf-8")
    os.utime(a, (1000.0, 1000.0))
    os.utime(b, (2000.0, 2000.0))

    assert latest_log(tmp_path, "*.log") == b
