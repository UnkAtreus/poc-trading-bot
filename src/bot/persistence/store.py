from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from bot.models import Direction
from bot.strategy.state_machine import Context
from bot.strategy.states import State


class StateStore:
    """Atomic per-symbol JSON snapshot. One file per symbol."""

    def __init__(self, root: str | Path = "data/state"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, symbol: str) -> Path:
        return self.root / f"{symbol}.json"

    def save(self, ctx: Context) -> None:
        payload = {
            "symbol": ctx.symbol,
            "state": ctx.state.value,
            "direction": ctx.direction.value if ctx.direction else None,
            "position_size": ctx.position_size,
            "bep": ctx.bep,
            "first_fill_ts": ctx.first_fill_ts,
            "pending_entry_link_id": ctx.pending_entry_link_id,
            "halted": ctx.halted,
        }
        path = self._path(ctx.symbol)
        # Atomic write: tmp file + rename.
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{ctx.symbol}.", suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(payload, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
            raise

    def load(self, symbol: str) -> Context | None:
        path = self._path(symbol)
        if not path.exists():
            return None
        with path.open("r") as f:
            d = json.load(f)
        return Context(
            symbol=d["symbol"],
            state=State(d["state"]),
            direction=Direction(d["direction"]) if d.get("direction") else None,
            position_size=d.get("position_size", 0.0),
            bep=d.get("bep", 0.0),
            first_fill_ts=d.get("first_fill_ts"),
            pending_entry_link_id=d.get("pending_entry_link_id"),
            halted=d.get("halted", False),
        )

    def kill_active(self) -> bool:
        return (self.root / "KILL").exists()
