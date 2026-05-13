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
from bot.models import Direction, Order, OrderAck, OrderPurpose, Position, Side
from bot.risk.manager import RiskManager
from bot.strategy.orchestrator import (
    MAX_BYBIT_ORDER_LINK_ID_LEN,
    Orchestrator,
    _SymbolRuntime,
    _is_fatal_order_rejection,
    _link_factory,
)
from bot.strategy.state_machine import Context, PlaceEntry
from bot.strategy.states import State


def _settings(*, per_symbol_cap: float = 600.0) -> Settings:
    return Settings(
        env=EnvSettings(mode=Mode.TESTNET),
        bot=BotConfig(
            sizing=Sizing(margin_usd=20, leverage=10),
            offsets=Offsets(entry_offset_bps=5, tp_offset_bps=10),
            merge_timer=MergeTimer(seconds=1800, policy="first_fill"),
            fees=Fees(maker_bps=-1.0, taker_bps=5.5),
            risk=RiskConfig(
                max_notional_per_symbol_usd=per_symbol_cap,
                max_notional_account_usd=2000,
                max_consecutive_losses=3,
                cooldown_minutes=60,
                daily_loss_limit_usd=100,
            ),
            signal=SignalConfig(engine="placeholder_rsi", params={}),
            loop=LoopConfig(reconcile_every_seconds=30),
        ),
        symbols=SymbolsConfig(active=["BTCUSDT"], overrides={}),
    )


class _RejectingAdapter:
    def __init__(self, reason: str = "rejected"):
        self.place_calls = 0
        self.reason = reason

    async def place_limit(self, symbol, side, qty, price, link_id, **kwargs):
        self.place_calls += 1
        return OrderAck(link_id=link_id, order_id="", accepted=False, reason=self.reason)


class _Store:
    def __init__(self):
        self.saved = []

    def save(self, ctx):
        self.saved.append(ctx)


class _ReconcilingAdapter:
    def __init__(self, positions: dict[str, Position], open_orders: dict[str, list[Order]] | None = None):
        self.positions = positions
        self.open_orders = open_orders or {}
        self.cancel_all_calls = []
        self.place_calls = []

    async def get_position(self, symbol):
        return self.positions[symbol]

    async def cancel_all(self, symbol):
        self.cancel_all_calls.append(symbol)

    async def place_limit(self, symbol, side, qty, price, link_id, **kwargs):
        self.place_calls.append((symbol, side, qty, price, link_id, kwargs))
        return OrderAck(link_id=link_id, order_id="OID", accepted=True)

    async def get_open_orders(self, symbol):
        return self.open_orders.get(symbol, [])


def test_bybit_10024_is_fatal_order_rejection():
    assert _is_fatal_order_rejection(
        "Dear User, product unavailable due to regulatory restrictions. (ErrCode: 10024)"
    )
    assert not _is_fatal_order_rejection(
        "order not exists or too late to cancel (ErrCode: 110001)"
    )


def test_order_link_ids_fit_bybit_limit_and_keep_purpose_segment():
    link_factory = _link_factory()

    for side in Side:
        for purpose in OrderPurpose:
            link_id = link_factory("XAUTUSDT", side, purpose, 0.0)

            assert len(link_id) <= MAX_BYBIT_ORDER_LINK_ID_LEN
            assert link_id.split("-")[2] == purpose.value


@pytest.mark.asyncio
async def test_rejected_entry_ack_resets_pending_state(tmp_path):
    settings = _settings()
    adapter = _RejectingAdapter()
    store = _Store()
    orch = Orchestrator(
        settings=settings,
        adapter=adapter,
        signal=None,  # type: ignore[arg-type]
        risk=RiskManager(settings=settings, state_dir=tmp_path),
        store=store,  # type: ignore[arg-type]
    )
    rt = _SymbolRuntime(
        ctx=Context(
            symbol="BTCUSDT",
            state=State.ENTRY_PENDING,
            direction=Direction.LONG,
            pending_entry_link_id="L1",
        )
    )

    await orch._execute("BTCUSDT", rt, PlaceEntry(Direction.LONG, price=100.0, qty=2.0, link_id="L1"))

    assert adapter.place_calls == 1
    assert rt.ctx.state is State.IDLE
    assert rt.ctx.direction is None
    assert rt.ctx.pending_entry_link_id is None
    assert store.saved[-1].state is State.IDLE


@pytest.mark.asyncio
async def test_reconcile_adopts_exchange_short_position_and_syncs_risk(tmp_path):
    settings = _settings(per_symbol_cap=250.0)
    adapter = _ReconcilingAdapter({"BTCUSDT": Position("BTCUSDT", size=-2.0, avg_price=100.0)})
    store = _Store()
    risk = RiskManager(settings=settings, state_dir=tmp_path)
    orch = Orchestrator(
        settings=settings,
        adapter=adapter,  # type: ignore[arg-type]
        signal=None,  # type: ignore[arg-type]
        risk=risk,
        store=store,  # type: ignore[arg-type]
    )
    rt = _SymbolRuntime(ctx=Context(symbol="BTCUSDT"))
    orch._runtimes["BTCUSDT"] = rt

    await orch._reconcile_all()

    assert rt.ctx.state is State.IN_POSITION_TP_PENDING
    assert rt.ctx.direction is Direction.SHORT
    assert rt.ctx.position_size == 2.0
    assert rt.ctx.bep == 100.0
    assert adapter.cancel_all_calls == ["BTCUSDT"]
    assert len(adapter.place_calls) == 1
    symbol, side, qty, price, link_id, kwargs = adapter.place_calls[0]
    assert symbol == "BTCUSDT"
    assert side is Side.BUY
    assert qty == 2.0
    assert price == 99.9
    assert link_id.split("-")[2] == OrderPurpose.TP.value
    assert kwargs == {"reduce_only": True, "post_only": False}
    assert risk.check_can_place_entry("BTCUSDT", 60.0) == (False, "per_symbol_cap(250.0)")


@pytest.mark.asyncio
async def test_reconcile_preserves_merge_pending_when_adopting_same_direction(tmp_path):
    settings = _settings()
    adapter = _ReconcilingAdapter({"BTCUSDT": Position("BTCUSDT", size=3.0, avg_price=110.0)})
    store = _Store()
    orch = Orchestrator(
        settings=settings,
        adapter=adapter,  # type: ignore[arg-type]
        signal=None,  # type: ignore[arg-type]
        risk=RiskManager(settings=settings, state_dir=tmp_path),
        store=store,  # type: ignore[arg-type]
    )
    rt = _SymbolRuntime(
        ctx=Context(
            symbol="BTCUSDT",
            state=State.MERGE_PENDING,
            direction=Direction.LONG,
            position_size=5.0,
            bep=100.0,
        )
    )
    orch._runtimes["BTCUSDT"] = rt

    await orch._reconcile_all()

    assert rt.ctx.state is State.MERGE_PENDING
    assert rt.ctx.direction is Direction.LONG
    assert rt.ctx.position_size == 3.0
    assert rt.ctx.bep == 110.0
    assert len(adapter.place_calls) == 1
    _, side, qty, price, link_id, kwargs = adapter.place_calls[0]
    assert side is Side.SELL
    assert qty == 3.0
    assert price == 110.11
    assert link_id.split("-")[2] == OrderPurpose.MERGE.value
    assert kwargs == {"reduce_only": True, "post_only": False}


@pytest.mark.asyncio
async def test_reconcile_recreates_missing_exit_order_for_synced_position(tmp_path):
    settings = _settings()
    adapter = _ReconcilingAdapter({"BTCUSDT": Position("BTCUSDT", size=1.5, avg_price=100.0)})
    store = _Store()
    orch = Orchestrator(
        settings=settings,
        adapter=adapter,  # type: ignore[arg-type]
        signal=None,  # type: ignore[arg-type]
        risk=RiskManager(settings=settings, state_dir=tmp_path),
        store=store,  # type: ignore[arg-type]
    )
    rt = _SymbolRuntime(
        ctx=Context(
            symbol="BTCUSDT",
            state=State.IN_POSITION_TP_PENDING,
            direction=Direction.LONG,
            position_size=1.5,
            bep=100.0,
        )
    )
    orch._runtimes["BTCUSDT"] = rt

    await orch._reconcile_all()

    assert adapter.cancel_all_calls == []
    assert len(adapter.place_calls) == 1
    _, side, qty, price, link_id, kwargs = adapter.place_calls[0]
    assert side is Side.SELL
    assert qty == 1.5
    assert price == 100.1
    assert link_id.split("-")[2] == OrderPurpose.TP.value
    assert kwargs == {"reduce_only": True, "post_only": False}


@pytest.mark.asyncio
async def test_fatal_entry_rejection_stops_bot(tmp_path):
    settings = _settings()
    adapter = _RejectingAdapter(
        reason="Dear User, product unavailable due to regulatory restrictions. (ErrCode: 10024)"
    )
    store = _Store()
    orch = Orchestrator(
        settings=settings,
        adapter=adapter,
        signal=None,  # type: ignore[arg-type]
        risk=RiskManager(settings=settings, state_dir=tmp_path),
        store=store,  # type: ignore[arg-type]
    )
    rt = _SymbolRuntime(
        ctx=Context(
            symbol="BTCUSDT",
            state=State.ENTRY_PENDING,
            direction=Direction.LONG,
            pending_entry_link_id="L1",
        )
    )
    orch._runtimes["BTCUSDT"] = rt

    await orch._execute(
        "BTCUSDT",
        rt,
        PlaceEntry(Direction.LONG, price=100.0, qty=2.0, link_id="L1"),
    )

    assert adapter.place_calls == 1
    assert orch._stop.is_set()
    assert rt.ctx.state is State.IDLE
    assert rt.ctx.halted is True


@pytest.mark.asyncio
async def test_risk_blocked_entry_resets_pending_state(tmp_path):
    settings = _settings(per_symbol_cap=100.0)
    adapter = _RejectingAdapter()
    store = _Store()
    orch = Orchestrator(
        settings=settings,
        adapter=adapter,
        signal=None,  # type: ignore[arg-type]
        risk=RiskManager(settings=settings, state_dir=tmp_path),
        store=store,  # type: ignore[arg-type]
    )
    rt = _SymbolRuntime(
        ctx=Context(
            symbol="BTCUSDT",
            state=State.ENTRY_PENDING,
            direction=Direction.LONG,
            pending_entry_link_id="L1",
        )
    )

    await orch._execute("BTCUSDT", rt, PlaceEntry(Direction.LONG, price=100.0, qty=2.0, link_id="L1"))

    assert adapter.place_calls == 0
    assert rt.ctx.state is State.IDLE
    assert rt.ctx.direction is None
    assert rt.ctx.pending_entry_link_id is None
    assert store.saved[-1].state is State.IDLE
