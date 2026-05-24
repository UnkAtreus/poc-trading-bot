"""Tests for the orchestrator-level min-qty / min-notional pre-flight check.

The Bybit live adapter already rejects dust at ``_normalize_order``, but the
27 ``orderQty will be truncated to zero`` errors in the testnet log show that
some dust still slips into Bybit's order endpoint. The orchestrator-level
pre-check short-circuits the round-trip: it consults the cached Instrument
metadata, decides locally whether the order is dust, and feeds the rejection
back into the state machine without ever calling ``place_limit``.

These tests lock down:

1. ``PlaceTP`` with ``qty < min_qty`` is not sent to the adapter; SM parks
   the position in ``DUST_STRANDED``.
2. ``PlaceTP`` with ``qty * price < min_notional`` is also caught locally.
3. ``PlaceTP`` with healthy qty passes through to ``place_limit``.
4. ``PlaceMergeTP`` follows the same rules.
5. ``PlaceEntry`` below min is treated as a rejected entry (reset to IDLE).
"""

from __future__ import annotations

from decimal import Decimal

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
from bot.models import Direction, Instrument, OrderAck, Side
from bot.risk.manager import RiskManager
from bot.strategy.orchestrator import Orchestrator, _SymbolRuntime
from bot.strategy.state_machine import (
    Context,
    PlaceEntry,
    PlaceMergeTP,
    PlaceTP,
)
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


class _InstrumentAdapter:
    """Adapter that exposes a controllable Instrument + tracks place_limit calls."""

    def __init__(self, instrument: Instrument):
        self.instrument = instrument
        self.place_calls: list[tuple] = []
        self.get_instrument_calls = 0

    async def get_instrument(self, symbol: str) -> Instrument:
        self.get_instrument_calls += 1
        return self.instrument

    async def place_limit(self, symbol, side, qty, price, link_id, **kwargs):
        self.place_calls.append((symbol, side, qty, price, link_id, kwargs))
        return OrderAck(link_id=link_id, order_id="OID", accepted=True)


def _xrp_instrument(*, min_qty: str = "1", min_notional: str = "5") -> Instrument:
    return Instrument(
        symbol="XRPUSDT",
        tick_size=Decimal("0.0001"),
        qty_step=Decimal("0.1"),
        min_notional=Decimal(min_notional),
        min_qty=Decimal(min_qty),
    )


def _build_orch(tmp_path, adapter, ctx: Context) -> tuple[Orchestrator, _SymbolRuntime]:
    settings = _settings()
    orch = Orchestrator(
        settings=settings,
        adapter=adapter,  # type: ignore[arg-type]
        signal=None,  # type: ignore[arg-type]
        risk=RiskManager(settings=settings, state_dir=tmp_path),
        store=_Store(),  # type: ignore[arg-type]
    )
    rt = _SymbolRuntime(ctx=ctx)
    orch._runtimes[ctx.symbol] = rt
    return orch, rt


@pytest.mark.asyncio
async def test_place_tp_below_min_qty_skips_adapter_and_parks_dust(tmp_path):
    """Qty below the symbol's min_qty must short-circuit without hitting Bybit
    and transition the SM to DUST_STRANDED so the bot does not loop on the
    same losing TP every reconcile cycle.
    """
    adapter = _InstrumentAdapter(_xrp_instrument(min_qty="1"))
    ctx = Context(
        symbol="XRPUSDT",
        state=State.IN_POSITION_TP_PENDING,
        direction=Direction.LONG,
        position_size=0.5,
        bep=1.5,
        first_fill_ts=1.0,
    )
    orch, rt = _build_orch(tmp_path, adapter, ctx)

    await orch._execute(
        "XRPUSDT",
        rt,
        PlaceTP(Direction.LONG, price=1.5, qty=0.5, link_id="TP-1"),
    )

    # No order ever reached the adapter.
    assert adapter.place_calls == []
    # SM parked in DUST_STRANDED via the dust-rejection path.
    assert rt.ctx.state is State.DUST_STRANDED


@pytest.mark.asyncio
async def test_place_tp_below_min_notional_skips_adapter(tmp_path):
    """Qty above min_qty but qty*price below min_notional must also be caught."""
    adapter = _InstrumentAdapter(_xrp_instrument(min_qty="1", min_notional="50"))
    ctx = Context(
        symbol="XRPUSDT",
        state=State.IN_POSITION_TP_PENDING,
        direction=Direction.LONG,
        position_size=10.0,
        bep=1.5,
        first_fill_ts=1.0,
    )
    orch, rt = _build_orch(tmp_path, adapter, ctx)

    # 10 * 1.5 = 15 < 50 min_notional.
    await orch._execute(
        "XRPUSDT",
        rt,
        PlaceTP(Direction.LONG, price=1.5, qty=10.0, link_id="TP-1"),
    )

    assert adapter.place_calls == []
    assert rt.ctx.state is State.DUST_STRANDED


@pytest.mark.asyncio
async def test_place_tp_above_min_passes_through(tmp_path):
    """Healthy qty should reach place_limit unchanged."""
    adapter = _InstrumentAdapter(_xrp_instrument(min_qty="1", min_notional="5"))
    ctx = Context(
        symbol="XRPUSDT",
        state=State.IN_POSITION_TP_PENDING,
        direction=Direction.LONG,
        position_size=100.0,
        bep=1.5,
        first_fill_ts=1.0,
    )
    orch, rt = _build_orch(tmp_path, adapter, ctx)

    await orch._execute(
        "XRPUSDT",
        rt,
        PlaceTP(Direction.LONG, price=1.5113, qty=100.0, link_id="TP-1"),
    )

    assert len(adapter.place_calls) == 1
    _, side, qty, price, link_id, kwargs = adapter.place_calls[0]
    assert side is Side.SELL
    assert qty == 100.0
    assert price == 1.5113
    assert link_id == "TP-1"
    assert kwargs == {"reduce_only": True, "post_only": False}
    assert rt.ctx.state is State.IN_POSITION_TP_PENDING


@pytest.mark.asyncio
async def test_place_merge_tp_below_min_skips_adapter(tmp_path):
    adapter = _InstrumentAdapter(_xrp_instrument(min_qty="1"))
    ctx = Context(
        symbol="XRPUSDT",
        state=State.MERGE_PENDING,
        direction=Direction.LONG,
        position_size=0.5,
        bep=1.5,
        first_fill_ts=1.0,
    )
    orch, rt = _build_orch(tmp_path, adapter, ctx)

    await orch._execute(
        "XRPUSDT",
        rt,
        PlaceMergeTP(Direction.LONG, price=1.51, qty=0.5, link_id="MERGE-1"),
    )

    assert adapter.place_calls == []
    assert rt.ctx.state is State.DUST_STRANDED


@pytest.mark.asyncio
async def test_place_entry_below_min_resets_to_idle(tmp_path):
    """Entries below the min must be rejected without touching the adapter so
    the SM doesn't stay stuck in ENTRY_PENDING.
    """
    adapter = _InstrumentAdapter(_xrp_instrument(min_qty="1"))
    ctx = Context(
        symbol="XRPUSDT",
        state=State.ENTRY_PENDING,
        direction=Direction.LONG,
        pending_entry_link_id="E-1",
    )
    orch, rt = _build_orch(tmp_path, adapter, ctx)

    await orch._execute(
        "XRPUSDT",
        rt,
        PlaceEntry(Direction.LONG, price=1.5, qty=0.5, link_id="E-1"),
    )

    assert adapter.place_calls == []
    assert rt.ctx.state is State.IDLE
    assert rt.ctx.direction is None
    assert rt.ctx.pending_entry_link_id is None


@pytest.mark.asyncio
async def test_instrument_lookup_failure_falls_back_to_adapter(tmp_path):
    """If get_instrument blows up, the pre-check returns None and we let the
    adapter's own validation run. This preserves backwards compatibility
    with adapters that don't implement get_instrument (e.g. unit-test mocks).
    """

    class _NoInstrumentAdapter:
        def __init__(self):
            self.place_calls: list[tuple] = []

        async def get_instrument(self, symbol):
            raise RuntimeError("instrument metadata unavailable")

        async def place_limit(self, symbol, side, qty, price, link_id, **kwargs):
            self.place_calls.append((symbol, side, qty, price, link_id, kwargs))
            return OrderAck(link_id=link_id, order_id="OID", accepted=True)

    adapter = _NoInstrumentAdapter()
    ctx = Context(
        symbol="XRPUSDT",
        state=State.IN_POSITION_TP_PENDING,
        direction=Direction.LONG,
        position_size=0.5,
        bep=1.5,
        first_fill_ts=1.0,
    )
    orch, rt = _build_orch(tmp_path, adapter, ctx)

    await orch._execute(
        "XRPUSDT",
        rt,
        PlaceTP(Direction.LONG, price=1.5113, qty=0.5, link_id="TP-1"),
    )

    # Pre-check failed → adapter still got the call.
    assert len(adapter.place_calls) == 1
