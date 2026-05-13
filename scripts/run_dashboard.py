"""Launch the dashboard with uvicorn.

Usage:
    DASHBOARD_PASSWORD=devpass uv run python scripts/run_dashboard.py \\
        --host 127.0.0.1 --port 8080
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

from bot.dashboard.app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the trading bot dashboard.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    args = parser.parse_args()

    if not os.environ.get("DASHBOARD_PASSWORD"):
        print(
            "WARNING: DASHBOARD_PASSWORD is not set. Dashboard pages will return 503.",
            flush=True,
        )

    if args.reload:
        os.environ["DASHBOARD_ROOT"] = args.root
        uvicorn.run("bot.dashboard.app:app", host=args.host, port=args.port, reload=True)
    else:
        app = create_app(args.root)
        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
