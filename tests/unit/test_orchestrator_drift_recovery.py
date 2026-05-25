"""Tests for the WS-driven drift-recovery path.

The bot can miss ``ExecutionEvent`` messages (WS drops, reconnect gaps).
When that happens, the only remaining truth signal is the exchange
``PositionEvent`` stream. Before this fix, drift was only logged at INFO
and only corrected by the periodic 30s reconcile loop — long enough on
mainnet to leave positions uncovered.

The PositionEvent-driven reconcile is **debounced** by
``RECONCILE_DEBOUNCE_SECONDS`` so the matching ExecutionEvent for the same
fill has a chance to update SM state via the normal flow. If drift
persists past the debounce window, the timer fires and reconcile runs as
the safety net. The tests below use ``orch._fire_drift_reconcile`` to
exercise the post-debounce path without real-time sleeps.

These tests lock down:

1. ``PositionEvent`` drift schedules a debounced reconcile.
2. When fired, the reconcile adopts exchange truth into the SM context.
3. Float-noise PositionEvents do NOT trigger reconcile (no spurious churn).
4. ExecutionEvents that predate the adoption highwater are dropped to
   avoid double-counting fills already baked into the adopted size.
5. A follow-up ExecutionEvent that resolves drift cancels the pending
   reconcile (the race fix for testnet/mainnet happy path).
6. Drift that persists past the debounce window still fires reconcile
   (safety net intact).
"""

from __future__ import annotations

import pytest

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
from bot.models import (
    Direction,
    ExecutionEvent,
    OrderAck,
    Position,
    PositionEvent,
    Side,
)
from bot.risk.manager import RiskManager
from bot.strategy.orchestrator import (
    RECONCILE_NOISE_EPS,
    Orchestrator,
    _SymbolRuntime,
)
from bot.strategy.state_machine import Context
from bot.strategy.states import State


def _settings() -> Settings:
    return Settings(
        env=EnvSettings(mode=Mode.TESTNET),
        bot=BotConfig(
            sizing=Sizing(margin_usd=100, leverage=10),
            offsets=Offsets(entry_offset_bps=5, tp_offset_bps=75),
            merge_timer=MergeTimer(seconds=1800, policy="first_fill"),
            fees=Fees(maker_bps=-1.0, taker_bps=5.5),
            risk=RiskConfig(
                max_notional_per_symbol_usd=4000,
                max_notional_account_usd=12500,
                max_consecutive_losses=5,
                cooldown_minutes=60,
                daily_loss_limit_usd=5000,
            ),
            signal=SignalConfig(engine="placeholder_rsi", params={}),
            loop=LoopConfig(reconcile_every_seconds=30),
        ),
        symbols=SymbolsConfig(active=["XRPUSDT"], overrides={}),
    )


class _Store:
    def __init__(self):
        self.saved = []

    def save(self, ctx):
        self.saved.append(ctx)


class _DriftAdapter:
    """Returns a single canned exchange position and records placements."""

    def __init__(self, position: Position):
        self.position = position
        self.get_position_calls = 0
        self.cancel_all_calls: list[str] = []
        self.place_calls: list[tuple] = []

    async def get_position(self, symbol):
        self.get_position_calls += 1
        return self.position

    async def cancel_all(self, symbol):
        self.cancel_all_calls.append(symbol)

    async def place_limit(self, symbol, side, qty, price, link_id, **kwargs):
        self.place_calls.append((symbol, side, qty, price, link_id, kwargs))
        return OrderAck(link_id=link_id, order_id="OID", accepted=True)

    async def get_open_orders(self, symbol):
        return []


def _build_orch(tmp_path, adapter, ctx: Context) -> tuple[Orchestrator, _SymbolRuntime]:
    settings = _settings()
    risk = RiskManager(settings=settings, state_dir=tmp_path)
    orch = Orchestrator(
        settings=settings,
        adapter=adapter,  # type: ignore[arg-type]
        signal=None,  # type: ignore[arg-type]
        risk=risk,
        store=_Store(),  # type: ignore[arg-type]
    )
    rt = _SymbolRuntime(ctx=ctx)
    orch._runtimes[ctx.symbol] = rt
    return orch, rt


@pytest.mark.asyncio
async def test_position_event_drift_schedules_debounced_reconcile(tmp_path):
    """Reproduces the live XRP case: local=448, exchange=748.7.

    Bot missed several entry execution events. WS PositionEvent reports
    real exchange size of 748.7. PositionEvent schedules a debounced
    reconcile; when the debounce fires (no follow-up ExecutionEvent
    resolves the drift) the reconcile adopts exchange truth.
    """
    exchange_pos = Position("XRPUSDT", size=748.7, avg_price=1.3356)
    adapter = _DriftAdapter(exchange_pos)
    ctx = Context(
        symbol="XRPUSDT",
        state=State.IN_POSITION_TP_PENDING,
        direction=Direction.LONG,
        position_size=448.0,
        bep=1.3356,
    )
    orch, rt = _build_orch(tmp_path, adapter, ctx)

    await orch._on_user_event(
        PositionEvent(symbol="XRPUSDT", size=748.7, avg_price=1.3356, timestamp=1000.0)
    )

    # Debounced — no REST call yet, but timer scheduled.
    assert adapter.get_position_calls == 0
    assert rt.pending_reconcile_handle is not None
    assert rt.pending_reconcile_snapshot_ts == 1000.0
    assert rt.last_seen_exchange_size == 748.7

    # Fire the debounced reconcile (simulates the timer expiring with no
    # resolving ExecutionEvent in between).
    await orch._fire_drift_reconcile("XRPUSDT")

    assert adapter.get_position_calls == 1
    assert rt.ctx.state is State.IN_POSITION_TP_PENDING
    assert rt.ctx.direction is Direction.LONG
    assert rt.ctx.position_size == 748.7
    assert rt.ctx.bep == 1.3356
    # adoption sets the highwater to the snapshot timestamp
    assert rt.last_adopt_ts == 1000.0
    # protective TP was replaced for the new size
    assert adapter.cancel_all_calls == ["XRPUSDT"]
    assert len(adapter.place_calls) == 1
    _, side, qty, _price, _link_id, kwargs = adapter.place_calls[0]
    assert side is Side.SELL  # LONG → TP side = SELL
    assert qty == 748.7
    assert kwargs == {"reduce_only": True, "post_only": False}


@pytest.mark.asyncio
async def test_position_event_drift_reconcile_on_missing_tp_fills(tmp_path):
    """Reproduces the live ETH case: local=0.27, exchange=0.04.

    Bot missed several TP partial-fill execution events. WS PositionEvent
    reports the real (smaller) exchange size. After debounce fires, adopt.
    """
    exchange_pos = Position("XRPUSDT", size=0.04, avg_price=2068.12)
    adapter = _DriftAdapter(exchange_pos)
    ctx = Context(
        symbol="XRPUSDT",
        state=State.IN_POSITION_TP_PENDING,
        direction=Direction.LONG,
        position_size=0.27,
        bep=2068.12,
    )
    orch, rt = _build_orch(tmp_path, adapter, ctx)

    await orch._on_user_event(
        PositionEvent(symbol="XRPUSDT", size=0.04, avg_price=2068.12, timestamp=2000.0)
    )
    await orch._fire_drift_reconcile("XRPUSDT")

    assert rt.ctx.position_size == 0.04
    assert rt.last_adopt_ts == 2000.0


@pytest.mark.asyncio
async def test_position_event_within_noise_does_not_reconcile(tmp_path):
    """Float-precision noise on the WS stream must not trigger churn."""
    adapter = _DriftAdapter(Position("XRPUSDT", size=68.2, avg_price=1.2993))
    ctx = Context(
        symbol="XRPUSDT",
        state=State.IN_POSITION_TP_PENDING,
        direction=Direction.LONG,
        position_size=68.20000000000002,
        bep=1.2992999999999997,
    )
    orch, rt = _build_orch(tmp_path, adapter, ctx)

    # Within NOISE_EPS — should NOT trigger reconcile.
    drift = abs(rt.ctx.position_size - 68.2)
    assert drift < RECONCILE_NOISE_EPS

    await orch._on_user_event(
        PositionEvent(symbol="XRPUSDT", size=68.2, avg_price=1.2993, timestamp=3000.0)
    )

    assert adapter.get_position_calls == 0
    assert rt.pending_reconcile_handle is None
    assert rt.ctx.position_size == 68.20000000000002
    assert rt.last_adopt_ts == 0.0


@pytest.mark.asyncio
async def test_execution_event_predating_adopt_is_skipped(tmp_path):
    """An execution event delivered after we adopted the exchange truth must
    be dropped if its timestamp predates the adoption — its qty is already
    baked into the adopted position_size.
    """
    adapter = _DriftAdapter(Position("XRPUSDT", size=748.7, avg_price=1.3356))
    ctx = Context(
        symbol="XRPUSDT",
        state=State.IN_POSITION_TP_PENDING,
        direction=Direction.LONG,
        position_size=448.0,
        bep=1.3356,
    )
    orch, rt = _build_orch(tmp_path, adapter, ctx)

    # 1. Drift event drives the adoption (debounce + fire), sets last_adopt_ts.
    await orch._on_user_event(
        PositionEvent(symbol="XRPUSDT", size=748.7, avg_price=1.3356, timestamp=1000.0)
    )
    await orch._fire_drift_reconcile("XRPUSDT")
    assert rt.ctx.position_size == 748.7
    assert rt.last_adopt_ts == 1000.0
    place_calls_after_adopt = len(adapter.place_calls)

    # 2. A late ExecutionEvent for one of the missed entry fills arrives
    #    AFTER the adopt. Its execTime predates the snapshot — drop it.
    await orch._on_user_event(
        ExecutionEvent(
            link_id="XRPUSDT-B-entry-LATE",
            symbol="XRPUSDT",
            side=Side.BUY,
            qty=150.0,
            price=1.3356,
            timestamp=999.0,  # before adopt
            fee=0.0,
            is_maker=True,
        )
    )

    # Skipped: no SM transition, no new orders, position unchanged.
    assert rt.ctx.position_size == 748.7
    assert len(adapter.place_calls) == place_calls_after_adopt


@pytest.mark.asyncio
async def test_execution_event_after_adopt_is_still_applied(tmp_path):
    """An execution event with timestamp > adopt highwater must still be
    processed — it represents a genuinely new fill that the adopted
    snapshot did not contain.
    """
    adapter = _DriftAdapter(Position("XRPUSDT", size=748.7, avg_price=1.3356))
    ctx = Context(
        symbol="XRPUSDT",
        state=State.IN_POSITION_TP_PENDING,
        direction=Direction.LONG,
        position_size=448.0,
        bep=1.3356,
    )
    orch, rt = _build_orch(tmp_path, adapter, ctx)

    await orch._on_user_event(
        PositionEvent(symbol="XRPUSDT", size=748.7, avg_price=1.3356, timestamp=1000.0)
    )
    await orch._fire_drift_reconcile("XRPUSDT")
    assert rt.ctx.position_size == 748.7

    # A genuinely-new fill that arrived after adoption. Should be applied
    # as a layered entry → position_size grows.
    await orch._on_user_event(
        ExecutionEvent(
            link_id="XRPUSDT-B-entry-NEW",
            symbol="XRPUSDT",
            side=Side.BUY,
            qty=100.0,
            price=1.34,
            timestamp=1001.0,  # after adopt
            fee=0.0,
            is_maker=True,
        )
    )

    assert rt.ctx.position_size == pytest.approx(848.7)


@pytest.mark.asyncio
async def test_position_event_then_execution_event_cancels_debounce(tmp_path):
    """Happy-path race fix.

    Bybit publishes PositionEvent (size=10) and ExecutionEvent (qty=10) for
    the same fill within a few ms. Position event arrives first → drift →
    debounced reconcile scheduled. Execution event arrives → SM transitions
    to IN_POSITION_TP_PENDING with size=10. Drift now resolved; the pending
    reconcile must be cancelled and `get_position` REST never called.

    Before this fix the reconcile would have raced ahead, adopted, and
    then skipped the execution as ``execution_skipped_pre_adopt`` — silently
    bypassing risk.on_trade_closed for every fill.
    """
    adapter = _DriftAdapter(Position("XRPUSDT", size=10.0, avg_price=1.5))
    # Local SM in ENTRY_PENDING (just placed the buy), size still 0.
    ctx = Context(
        symbol="XRPUSDT",
        state=State.ENTRY_PENDING,
        direction=Direction.LONG,
        position_size=0.0,
        bep=0.0,
        pending_entry_link_id="XRPUSDT-B-entry-ABC",
    )
    orch, rt = _build_orch(tmp_path, adapter, ctx)

    # 1. Position WS arrives first (exchange size 10, local 0 → drift).
    await orch._on_user_event(
        PositionEvent(symbol="XRPUSDT", size=10.0, avg_price=1.5, timestamp=1000.0)
    )
    assert rt.pending_reconcile_handle is not None
    assert adapter.get_position_calls == 0  # debounced

    # 2. Matching ExecutionEvent arrives a few ms later. Normal SM flow
    #    updates position_size = 10. Drift now resolved.
    await orch._on_user_event(
        ExecutionEvent(
            link_id="XRPUSDT-B-entry-ABC",
            symbol="XRPUSDT",
            side=Side.BUY,
            qty=10.0,
            price=1.5,
            timestamp=999.99,
            fee=0.0,
            is_maker=True,
        )
    )

    # Pending reconcile cancelled — no adopt path.
    assert rt.pending_reconcile_handle is None
    assert adapter.get_position_calls == 0
    assert adapter.cancel_all_calls == []
    # SM advanced to IN_POSITION_TP_PENDING with the right size.
    assert rt.ctx.state is State.IN_POSITION_TP_PENDING
    assert rt.ctx.position_size == 10.0
    # Adoption highwater untouched, so subsequent executions still flow
    # through the normal path.
    assert rt.last_adopt_ts == 0.0


@pytest.mark.asyncio
async def test_position_event_drift_with_no_matching_execution_still_fires(tmp_path):
    """Safety-net case: position WS reports drift, NO matching execution
    arrives before the debounce expires. Reconcile must still fire to
    adopt exchange truth — same as the legacy behavior, just deferred.
    """
    adapter = _DriftAdapter(Position("XRPUSDT", size=100.0, avg_price=2.0))
    ctx = Context(
        symbol="XRPUSDT",
        state=State.IN_POSITION_TP_PENDING,
        direction=Direction.LONG,
        position_size=50.0,
        bep=2.0,
    )
    orch, rt = _build_orch(tmp_path, adapter, ctx)

    await orch._on_user_event(
        PositionEvent(symbol="XRPUSDT", size=100.0, avg_price=2.0, timestamp=5000.0)
    )
    assert rt.pending_reconcile_handle is not None

    # No follow-up execution → debounce fires → reconcile adopts.
    await orch._fire_drift_reconcile("XRPUSDT")

    assert adapter.get_position_calls == 1
    assert rt.ctx.position_size == 100.0
    assert rt.last_adopt_ts == 5000.0


@pytest.mark.asyncio
async def test_position_event_no_drift_cancels_pending_reconcile(tmp_path):
    """If a follow-up PositionEvent shows the drift cleared (e.g. exchange
    confirms the position matches local SM after a brief mismatch), the
    pending reconcile must be cancelled.
    """
    adapter = _DriftAdapter(Position("XRPUSDT", size=10.0, avg_price=1.5))
    ctx = Context(
        symbol="XRPUSDT",
        state=State.IN_POSITION_TP_PENDING,
        direction=Direction.LONG,
        position_size=10.0,
        bep=1.5,
    )
    orch, rt = _build_orch(tmp_path, adapter, ctx)

    # First event reports drift (size diff).
    await orch._on_user_event(
        PositionEvent(symbol="XRPUSDT", size=12.0, avg_price=1.5, timestamp=1000.0)
    )
    assert rt.pending_reconcile_handle is not None

    # Then SM catches up by some external path → local matches exchange.
    # A fresh position event with matching size arrives.
    rt.ctx = rt.ctx.with_(position_size=12.0)
    await orch._on_user_event(
        PositionEvent(symbol="XRPUSDT", size=12.0, avg_price=1.5, timestamp=1001.0)
    )

    assert rt.pending_reconcile_handle is None
    assert adapter.get_position_calls == 0
