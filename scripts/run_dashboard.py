"""Launch the dashboard with uvicorn.

Usage:
    DASHBOARD_PASSWORD=devpass uv run python scripts/run_dashboard.py \\
        --host 127.0.0.1 --port 8080

Hot reload is on by default — Python, template, and static-file changes restart
the server (the browser still has to refresh). Pass `--no-reload` to disable it
for production-style runs.
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
    parser.add_argument(
        "--no-reload",
        dest="reload",
        action="store_false",
        help="Disable uvicorn auto-reload (default: enabled for dev).",
    )
    parser.add_argument(
        "--reload",
        dest="reload",
        action="store_true",
        help="Force-enable uvicorn auto-reload (this is the default).",
    )
    parser.set_defaults(reload=True)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    args = parser.parse_args()

    if not os.environ.get("DASHBOARD_PASSWORD"):
        print(
            "WARNING: DASHBOARD_PASSWORD is not set. Dashboard pages will return 503.",
            flush=True,
        )

    if args.reload:
        root = Path(args.root).resolve()
        os.environ["DASHBOARD_ROOT"] = str(root)
        pkg_dir = root / "src" / "bot" / "dashboard"
        # Watch Python sources (for code reload) plus templates + static so HTML/CSS/JS
        # edits also trigger a restart and the browser sees them on next refresh.
        reload_dirs = [str(root / "src" / "bot"), str(pkg_dir)]
        reload_includes = ["*.py", "*.html", "*.css", "*.js"]
        print(
            f"Dashboard starting with hot reload on {args.host}:{args.port}\n"
            f"  watching: {', '.join(reload_dirs)}\n"
            f"  patterns: {', '.join(reload_includes)}\n"
            f"  pass --no-reload to disable.",
            flush=True,
        )
        uvicorn.run(
            "bot.dashboard.app:app",
            host=args.host,
            port=args.port,
            reload=True,
            reload_dirs=reload_dirs,
            reload_includes=reload_includes,
        )
    else:
        app = create_app(args.root)
        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
