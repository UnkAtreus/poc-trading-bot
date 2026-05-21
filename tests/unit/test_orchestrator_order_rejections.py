from __future__ import annotations

import time

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
from bot.models import Direction, ExecutionEvent, Order, OrderAck, OrderPurpose, Position, Side
from bot.risk.manager import RiskManager
from bot.strategy.orchestrator import (
    MAX_BYBIT_ORDER_LINK_ID_LEN,
    Orchestrator,
    _SymbolRuntime,
    _is_fatal_order_rejection,
    _link_factory,
)
from bot.strategy.state_machine import Context, PlaceEntry, PlaceMergeTP, PlaceTP
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
        self.close_calls = []

    async def get_position(self, symbol):
        return self.positions[symbol]

    async def cancel(self, symbol, link_id):
        return None

    async def cancel_all(self, symbol):
        self.cancel_all_calls.append(symbol)

    async def place_limit(self, symbol, side, qty, price, link_id, **kwargs):
        self.place_calls.append((symbol, side, qty, price, link_id, kwargs))
        return OrderAck(link_id=link_id, order_id="OID", accepted=True)

    async def close_position_market(self, symbol, side, link_id):
        self.close_calls.append((symbol, side, link_id))
        return OrderAck(link_id=link_id, order_id="CLOSEOID", accepted=True)

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
async def test_merge_tp_rejection_below_min_notional_parks_in_dust_stranded(tmp_path):
    settings = _settings()
    adapter = _RejectingAdapter(reason="notional_below_min(0.14896 < 5)")
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
            state=State.MERGE_PENDING,
            direction=Direction.SHORT,
            position_size=0.1,
            bep=1.5047,
            first_fill_ts=1.0,
        )
    )
    orch._runtimes["BTCUSDT"] = rt

    await orch._execute(
        "BTCUSDT",
        rt,
        PlaceMergeTP(Direction.SHORT, price=1.49, qty=0.1, link_id="MERGE-1"),
    )

    assert adapter.place_calls == 1  # one rejected attempt, no retry storm
    assert rt.ctx.state is State.DUST_STRANDED
    assert rt.ctx.position_size == 0.1
    assert store.saved[-1].state is State.DUST_STRANDED


@pytest.mark.asyncio
async def test_regular_tp_rejection_below_min_notional_parks_in_dust_stranded(tmp_path):
    settings = _settings()
    adapter = _RejectingAdapter(reason="notional_below_min(0.14896 < 5)")
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
            state=State.IN_POSITION_TP_PENDING,
            direction=Direction.SHORT,
            position_size=0.1,
            bep=1.5047,
            first_fill_ts=1.0,
        )
    )
    orch._runtimes["BTCUSDT"] = rt

    await orch._execute(
        "BTCUSDT",
        rt,
        PlaceTP(Direction.SHORT, price=1.49, qty=0.1, link_id="TP-1"),
    )

    assert adapter.place_calls == 1
    assert rt.ctx.state is State.DUST_STRANDED
    assert rt.ctx.position_size == 0.1
    assert store.saved[-1].state is State.DUST_STRANDED


@pytest.mark.asyncio
async def test_regular_tp_rejection_bybit_110017_parks_in_dust_stranded(tmp_path):
    settings = _settings()
    adapter = _RejectingAdapter(
        reason="orderQty will be truncated to zero. (ErrCode: 110017)"
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
            state=State.IN_POSITION_TP_PENDING,
            direction=Direction.LONG,
            position_size=5.4,
            bep=89.97,
            first_fill_ts=1.0,
        )
    )
    orch._runtimes["BTCUSDT"] = rt

    await orch._execute(
        "BTCUSDT",
        rt,
        PlaceTP(Direction.LONG, price=90.86, qty=5.4, link_id="TP-1"),
    )

    assert adapter.place_calls == 1
    assert rt.ctx.state is State.DUST_STRANDED
    assert store.saved[-1].state is State.DUST_STRANDED


@pytest.mark.asyncio
async def test_reconcile_does_not_recreate_exit_when_dust_stranded(tmp_path):
    settings = _settings()
    adapter = _ReconcilingAdapter({"BTCUSDT": Position("BTCUSDT", size=-0.1, avg_price=1.5047)})
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
            state=State.DUST_STRANDED,
            direction=Direction.SHORT,
            position_size=0.1,
            bep=1.5047,
            first_fill_ts=1.0,
        )
    )
    orch._runtimes["BTCUSDT"] = rt

    await orch._reconcile_all()

    assert rt.ctx.state is State.DUST_STRANDED
    # No placement attempts, no spammy reconcile.exit_order_missing-driven retries.
    assert adapter.place_calls == []
    assert adapter.cancel_all_calls == []
    assert adapter.close_calls == []


@pytest.mark.asyncio
async def test_reconcile_submits_market_close_for_dust_when_cleanup_enabled(tmp_path):
    settings = _settings()
    settings.bot.dust_cleanup.enabled = True
    settings.bot.dust_cleanup.retry_seconds = 0
    adapter = _ReconcilingAdapter({"BTCUSDT": Position("BTCUSDT", size=-0.1, avg_price=1.5047)})
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
            state=State.DUST_STRANDED,
            direction=Direction.SHORT,
            position_size=0.1,
            bep=1.5047,
            first_fill_ts=1.0,
        )
    )
    orch._runtimes["BTCUSDT"] = rt

    await orch._reconcile_all()

    assert rt.ctx.state is State.DUST_STRANDED
    assert adapter.place_calls == []
    assert adapter.cancel_all_calls == ["BTCUSDT"]
    assert len(adapter.close_calls) == 1
    symbol, side, link_id = adapter.close_calls[0]
    assert symbol == "BTCUSDT"
    assert side is Side.BUY
    assert link_id.split("-")[2] == OrderPurpose.TP.value


@pytest.mark.asyncio
async def test_reconcile_respects_dust_cleanup_attempt_limit(tmp_path):
    settings = _settings()
    settings.bot.dust_cleanup.enabled = True
    settings.bot.dust_cleanup.max_attempts = 1
    settings.bot.dust_cleanup.retry_seconds = 0
    adapter = _ReconcilingAdapter({"BTCUSDT": Position("BTCUSDT", size=0.1, avg_price=1.5047)})
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
            state=State.DUST_STRANDED,
            direction=Direction.LONG,
            position_size=0.1,
            bep=1.5047,
            first_fill_ts=1.0,
        )
    )
    orch._runtimes["BTCUSDT"] = rt

    await orch._reconcile_all()
    await orch._reconcile_all()

    assert adapter.place_calls == []
    assert adapter.cancel_all_calls == ["BTCUSDT"]
    assert len(adapter.close_calls) == 1
    assert adapter.close_calls[0][1] is Side.SELL


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


@pytest.mark.asyncio
async def test_external_close_execution_is_classified_by_side_and_releases_risk(tmp_path):
    settings = _settings(per_symbol_cap=250.0)
    store = _Store()
    risk = RiskManager(settings=settings, state_dir=tmp_path)
    risk.sync_open_notional("BTCUSDT", 200.0)
    orch = Orchestrator(
        settings=settings,
        adapter=None,  # type: ignore[arg-type]
        signal=None,  # type: ignore[arg-type]
        risk=risk,
        store=store,  # type: ignore[arg-type]
    )
    rt = _SymbolRuntime(
        ctx=Context(
            symbol="BTCUSDT",
            state=State.IN_POSITION_TP_PENDING,
            direction=Direction.LONG,
            position_size=2.0,
            bep=100.0,
            first_fill_ts=1.0,
        )
    )
    orch._runtimes["BTCUSDT"] = rt

    await orch._on_user_event(
        ExecutionEvent(
            link_id="",
            symbol="BTCUSDT",
            side=Side.SELL,
            qty=2.0,
            price=101.0,
            timestamp=2.0,
            fee=0.1,
        )
    )

    assert rt.ctx.state is State.IDLE
    assert rt.ctx.position_size == 0.0
    assert risk.check_can_place_entry("BTCUSDT", 200.0) == (True, None)
    assert store.saved[-1].state is State.IDLE


@pytest.mark.asyncio
async def test_reconcile_restores_merge_timer_when_exit_order_already_exists(tmp_path):
    settings = _settings()
    open_orders = {
        "BTCUSDT": [
            Order(
                link_id="BTCUSDT-S-tp-existing",
                symbol="BTCUSDT",
                side=Side.SELL,
                purpose=OrderPurpose.TP,
                qty=1.5,
                price=100.1,
            )
        ]
    }
    adapter = _ReconcilingAdapter(
        {"BTCUSDT": Position("BTCUSDT", size=1.5, avg_price=100.0)},
        open_orders=open_orders,
    )
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
            first_fill_ts=time.time() - 60.0,
        )
    )
    orch._runtimes["BTCUSDT"] = rt

    await orch._reconcile_all()

    assert adapter.place_calls == []
    assert rt.merge_handle is not None
    rt.merge_handle.cancel()
