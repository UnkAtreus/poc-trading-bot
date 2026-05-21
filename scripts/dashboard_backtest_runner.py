"""Run a dashboard-launched backtest and write a markdown performance report.

Invoked as:
    python scripts/dashboard_backtest_runner.py <job_spec_path>

The job spec is a JSON file written by the dashboard with this shape:
    {
        "ts": "1700000000",
        "cmd": ["uv", "run", "trading-bot", "backtest", ...],
        "log_path": "logs/dashboard_backtest_<ts>.txt",
        "report_path": "reports/dashboard_backtest_<ts>.md",
        "registry_path": "data/state/backtests/<ts>.json",
        "summary": { ... display-only metadata ... }
    }
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path


def _update_registry(path: Path, **fields) -> None:
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    data.update(fields)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _extract_summary(log_text: str) -> str:
    marker = "BACKTEST REPORT"
    idx = log_text.find(marker)
    if idx < 0:
        tail = log_text.splitlines()[-80:]
        return "\n".join(tail)
    return log_text[idx:].strip()


def _render_report(spec: dict, *, log_text: str, exit_code: int, duration_s: float) -> str:
    summary = spec.get("summary") or {}
    cmd = " ".join(spec.get("cmd") or [])
    title = f"Dashboard Backtest {spec.get('ts', '')}"
    lines = [
        f"# {title}",
        "",
        f"- Started UTC: `{summary.get('started_at_utc', '')}`",
        f"- Duration: `{duration_s:.1f}s`",
        f"- Exit code: `{exit_code}`",
        f"- Signal: `{summary.get('signal_short') or summary.get('signal', '')}`",
        f"- Full signal: `{summary.get('signal_full') or summary.get('signal', '')}`",
        f"- Symbols: `{', '.join(summary.get('symbols', []))}`",
        f"- Window: `{summary.get('start', '')}` to `{summary.get('end', '')}`",
        f"- Initial equity: `{summary.get('initial_equity', '')}`",
        f"- Margin / leverage: `{summary.get('margin_usd', '')}` USDT × `{summary.get('leverage', '')}`",
        f"- TP / caps: TP `{summary.get('tp_offset_bps', '')}` bps, account cap `{summary.get('max_notional_account', '')}`, symbol cap `{summary.get('max_notional_per_symbol', '')}`",
        f"- Daily loss limit: `{summary.get('daily_loss_limit', '')}`",
        f"- Raw log: `{spec.get('log_path', '')}`",
        "",
        "## Command",
        "",
        "```",
        cmd,
        "```",
        "",
        "## Summary",
        "",
        "```",
        _extract_summary(log_text),
        "```",
        "",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: dashboard_backtest_runner.py <job_spec.json>", file=sys.stderr)
        return 2
    spec_path = Path(argv[1])
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    cmd = spec["cmd"]
    log_path = Path(spec["log_path"])
    report_path = Path(spec["report_path"])
    registry_path = Path(spec["registry_path"])

    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    _update_registry(registry_path, status="running", started_at=time.time())

    with log_path.open("w", encoding="utf-8") as f:
        proc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, check=False)
    duration = time.monotonic() - started

    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    report = _render_report(spec, log_text=log_text, exit_code=proc.returncode, duration_s=duration)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    _update_registry(
        registry_path,
        status="finished" if proc.returncode == 0 else "failed",
        finished_at=time.time(),
        duration_s=duration,
        exit_code=proc.returncode,
        report_path=str(report_path),
    )
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv))
