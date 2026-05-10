from __future__ import annotations

from bot.models import Direction
from bot.persistence.store import StateStore
from bot.strategy.state_machine import Context
from bot.strategy.states import State


def test_round_trip_idle(tmp_path):
    s = StateStore(tmp_path)
    c = Context(symbol="BTCUSDT")
    s.save(c)
    loaded = s.load("BTCUSDT")
    assert loaded == c


def test_round_trip_in_position(tmp_path):
    s = StateStore(tmp_path)
    c = Context(
        symbol="ETHUSDT",
        state=State.IN_POSITION_TP_PENDING,
        direction=Direction.LONG,
        position_size=2.5,
        bep=3450.5,
        first_fill_ts=1714512000.0,
        pending_entry_link_id=None,
        halted=False,
    )
    s.save(c)
    loaded = s.load("ETHUSDT")
    assert loaded == c


def test_load_missing_returns_none(tmp_path):
    s = StateStore(tmp_path)
    assert s.load("NOPE") is None


def test_kill_file_detection(tmp_path):
    s = StateStore(tmp_path)
    assert not s.kill_active()
    (tmp_path / "KILL").touch()
    assert s.kill_active()
