"""Pure per-symbol state machine. No I/O, no asyncio, no globals.

Inputs are plain Events; outputs are (new_state, [Action]). The orchestrator
executes the actions against the exchange adapter.

Timer policy is `first_fill`: a 30-min timer is set when the symbol leaves
IDLE on the first un-TP'd fill, never reset by layered fills, cleared only
when position returns to flat.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Union

from bot.models import Direction, OrderPurpose, Side
from bot.strategy.states import State


# ---------- Events ----------

@dataclass(frozen=True)
class CandleClose:
    timestamp: float
    close_price: float
    signal_direction: Direction | None = None  # None = no signal


@dataclass(frozen=True)
class EntryFilled:
    link_id: str
    qty: float
    price: float
    timestamp: float


@dataclass(frozen=True)
class TPFilled:
    link_id: str
    qty: float
    price: float
    timestamp: float


@dataclass(frozen=True)
class OrderRejected:
    link_id: str
    purpose: OrderPurpose
    timestamp: float


@dataclass(frozen=True)
class MergeTimerExpired:
    timestamp: float


@dataclass(frozen=True)
class RiskHalt:
    timestamp: float


@dataclass(frozen=True)
class RiskResume:
    timestamp: float


Event = Union[
    CandleClose,
    EntryFilled,
    TPFilled,
    OrderRejected,
    MergeTimerExpired,
    RiskHalt,
    RiskResume,
]


# ---------- Actions ----------

@dataclass(frozen=True)
class PlaceEntry:
    direction: Direction
    price: float
    qty: float
    link_id: str


@dataclass(frozen=True)
class CancelEntry:
    link_id: str


@dataclass(frozen=True)
class PlaceTP:
    direction: Direction
    price: float
    qty: float
    link_id: str


@dataclass(frozen=True)
class CancelAllTPs:
    pass


@dataclass(frozen=True)
class PlaceMergeTP:
    direction: Direction
    price: float
    qty: float
    link_id: str


@dataclass(frozen=True)
class StartMergeTimer:
    deadline: float  # absolute timestamp


@dataclass(frozen=True)
class ClearMergeTimer:
    pass


Action = Union[
    PlaceEntry,
    CancelEntry,
    PlaceTP,
    CancelAllTPs,
    PlaceMergeTP,
    StartMergeTimer,
    ClearMergeTimer,
]


# ---------- Context ----------

@dataclass(frozen=True)
class Params:
    """Strategy parameters needed by the SM, derived from BotConfig."""

    entry_offset_bps: float
    tp_offset_bps: float
    merge_timer_seconds: int
    notional_usd: float


@dataclass(frozen=True)
class Context:
    """Per-symbol mutable context (treated immutably; new instances returned)."""

    symbol: str
    state: State = State.IDLE
    direction: Direction | None = None  # active direction when in position
    position_size: float = 0.0  # always non-negative magnitude
    bep: float = 0.0
    first_fill_ts: float | None = None
    pending_entry_link_id: str | None = None
    halted: bool = False

    def with_(self, **kw) -> "Context":
        return replace(self, **kw)


@dataclass(frozen=True)
class Decision:
    ctx: Context
    actions: tuple[Action, ...]


# ---------- Helpers ----------

def _entry_price(close: float, direction: Direction, bps: float) -> float:
    delta = close * (bps / 10_000.0)
    return close - delta if direction is Direction.LONG else close + delta


def _tp_price(fill: float, direction: Direction, bps: float) -> float:
    delta = fill * (bps / 10_000.0)
    return fill + delta if direction is Direction.LONG else fill - delta


def _qty(notional: float, price: float) -> float:
    if price <= 0:
        return 0.0
    return notional / price


def _link(symbol: str, side: Side, purpose: OrderPurpose, ts: float, seq: int = 0) -> str:
    # Deterministic, replayable. Real adapter swaps the suffix for a ULID.
    return f"{symbol}-{side.value}-{purpose.value}-{int(ts)}-{seq}"


# ---------- Reducer ----------

def step(ctx: Context, event: Event, params: Params, *, link_id_factory=None) -> Decision:
    """Pure reducer: (ctx, event) -> (new ctx, actions).

    `link_id_factory(symbol, side, purpose, ts) -> str` lets callers inject
    real ULID generation; defaults to a deterministic helper for tests.
    """
    factory = link_id_factory or (lambda sym, side, purp, ts: _link(sym, side, purp, ts))

    if isinstance(event, RiskHalt):
        return Decision(ctx.with_(halted=True), ())
    if isinstance(event, RiskResume):
        return Decision(ctx.with_(halted=False), ())

    if ctx.state is State.IDLE:
        return _from_idle(ctx, event, params, factory)
    if ctx.state is State.ENTRY_PENDING:
        return _from_entry_pending(ctx, event, params, factory)
    if ctx.state is State.IN_POSITION_TP_PENDING:
        return _from_in_position(ctx, event, params, factory)
    if ctx.state is State.MERGE_PENDING:
        return _from_merge_pending(ctx, event, params, factory)
    if ctx.state is State.HALTED:
        # Halted is a terminal "no new entries" mode; let TPs resolve naturally.
        # We model HALTED as just the `halted` flag in other states; reaching
        # State.HALTED explicitly is reserved for tests/manual.
        return Decision(ctx, ())

    raise AssertionError(f"unhandled state: {ctx.state}")


def _from_idle(ctx, event, params, factory) -> Decision:
    if isinstance(event, CandleClose):
        if event.signal_direction is None or ctx.halted:
            return Decision(ctx, ())
        direction = event.signal_direction
        price = _entry_price(event.close_price, direction, params.entry_offset_bps)
        qty = _qty(params.notional_usd, price)
        link = factory(ctx.symbol, direction.entry_side, OrderPurpose.ENTRY, event.timestamp)
        new_ctx = ctx.with_(
            state=State.ENTRY_PENDING,
            direction=direction,
            pending_entry_link_id=link,
        )
        return Decision(new_ctx, (PlaceEntry(direction, price, qty, link),))
    # Stray fills/timer events ignored from IDLE.
    return Decision(ctx, ())


def _from_entry_pending(ctx, event, params, factory) -> Decision:
    if isinstance(event, EntryFilled):
        # First fill: we now have a position. Set BEP, start merge timer.
        new_size = event.qty
        new_bep = event.price
        direction = ctx.direction
        assert direction is not None, "ENTRY_PENDING without direction"
        tp_price = _tp_price(event.price, direction, params.tp_offset_bps)
        tp_link = factory(ctx.symbol, direction.tp_side, OrderPurpose.TP, event.timestamp)
        new_ctx = ctx.with_(
            state=State.IN_POSITION_TP_PENDING,
            position_size=new_size,
            bep=new_bep,
            first_fill_ts=event.timestamp,
            pending_entry_link_id=None,
        )
        deadline = event.timestamp + params.merge_timer_seconds
        actions: tuple[Action, ...] = (
            PlaceTP(direction, tp_price, new_size, tp_link),
            StartMergeTimer(deadline),
        )
        return Decision(new_ctx, actions)

    if isinstance(event, OrderRejected):
        if event.purpose is OrderPurpose.ENTRY:
            return Decision(
                ctx.with_(state=State.IDLE, direction=None, pending_entry_link_id=None),
                (),
            )
        return Decision(ctx, ())

    if isinstance(event, CandleClose):
        # Cancel the unfilled entry first.
        actions: list[Action] = []
        if ctx.pending_entry_link_id:
            actions.append(CancelEntry(ctx.pending_entry_link_id))
        # Re-evaluate signal on this candle close.
        if event.signal_direction is None or ctx.halted:
            new_ctx = ctx.with_(state=State.IDLE, direction=None, pending_entry_link_id=None)
            return Decision(new_ctx, tuple(actions))
        direction = event.signal_direction
        price = _entry_price(event.close_price, direction, params.entry_offset_bps)
        qty = _qty(params.notional_usd, price)
        link = factory(ctx.symbol, direction.entry_side, OrderPurpose.ENTRY, event.timestamp)
        actions.append(PlaceEntry(direction, price, qty, link))
        new_ctx = ctx.with_(direction=direction, pending_entry_link_id=link)
        return Decision(new_ctx, tuple(actions))

    return Decision(ctx, ())


def _from_in_position(ctx, event, params, factory) -> Decision:
    direction = ctx.direction
    assert direction is not None, "IN_POSITION_TP_PENDING without direction"

    if isinstance(event, TPFilled):
        # Position flat (we don't model partial TPs in v1).
        new_ctx = ctx.with_(
            state=State.IDLE,
            direction=None,
            position_size=0.0,
            bep=0.0,
            first_fill_ts=None,
            pending_entry_link_id=None,
        )
        return Decision(new_ctx, (ClearMergeTimer(),))

    if isinstance(event, EntryFilled):
        # Layered fill: roll BEP, cancel existing TPs, replace with one TP at new BEP.
        total = ctx.position_size + event.qty
        if total <= 0:
            return Decision(ctx, ())
        new_bep = (ctx.bep * ctx.position_size + event.price * event.qty) / total
        tp_price = _tp_price(new_bep, direction, params.tp_offset_bps)
        tp_link = factory(ctx.symbol, direction.tp_side, OrderPurpose.TP, event.timestamp)
        new_ctx = ctx.with_(
            position_size=total,
            bep=new_bep,
            pending_entry_link_id=None,
        )
        return Decision(
            new_ctx,
            (CancelAllTPs(), PlaceTP(direction, tp_price, total, tp_link)),
        )

    if isinstance(event, MergeTimerExpired):
        merge_price = _tp_price(ctx.bep, direction, params.tp_offset_bps)
        merge_link = factory(ctx.symbol, direction.tp_side, OrderPurpose.MERGE, event.timestamp)
        new_ctx = ctx.with_(state=State.MERGE_PENDING, pending_entry_link_id=None)
        return Decision(
            new_ctx,
            (
                CancelAllTPs(),
                PlaceMergeTP(direction, merge_price, ctx.position_size, merge_link),
            ),
        )

    if isinstance(event, CandleClose):
        # New layered entry only if signal in same direction and not halted.
        # Stay in IN_POSITION_TP_PENDING — the EntryFilled handler in this
        # state computes weighted-avg BEP; transitioning to ENTRY_PENDING
        # would incorrectly treat the layered fill as a fresh first entry.
        actions: list[Action] = []
        new_ctx = ctx
        # First: a previously-placed layered entry that never filled must be
        # cancelled at this next candle close (same rule as ENTRY_PENDING).
        if ctx.pending_entry_link_id is not None:
            actions.append(CancelEntry(ctx.pending_entry_link_id))
            new_ctx = new_ctx.with_(pending_entry_link_id=None)
        if event.signal_direction is None or ctx.halted:
            return Decision(new_ctx, tuple(actions))
        if event.signal_direction is not direction:
            return Decision(new_ctx, tuple(actions))
        price = _entry_price(event.close_price, direction, params.entry_offset_bps)
        qty = _qty(params.notional_usd, price)
        link = factory(ctx.symbol, direction.entry_side, OrderPurpose.ENTRY, event.timestamp)
        actions.append(PlaceEntry(direction, price, qty, link))
        new_ctx = new_ctx.with_(pending_entry_link_id=link)
        return Decision(new_ctx, tuple(actions))

    if isinstance(event, OrderRejected):
        if event.purpose is OrderPurpose.ENTRY:
            return Decision(ctx.with_(pending_entry_link_id=None), ())
        return Decision(ctx, ())

    return Decision(ctx, ())


def _from_merge_pending(ctx, event, params, factory) -> Decision:
    direction = ctx.direction
    assert direction is not None, "MERGE_PENDING without direction"

    if isinstance(event, TPFilled):
        new_ctx = ctx.with_(
            state=State.IDLE,
            direction=None,
            position_size=0.0,
            bep=0.0,
            first_fill_ts=None,
            pending_entry_link_id=None,
        )
        return Decision(new_ctx, (ClearMergeTimer(),))

    if isinstance(event, EntryFilled):
        # Layered fill arrived after merge was placed: re-merge at new BEP.
        total = ctx.position_size + event.qty
        if total <= 0:
            return Decision(ctx, ())
        new_bep = (ctx.bep * ctx.position_size + event.price * event.qty) / total
        merge_price = _tp_price(new_bep, direction, params.tp_offset_bps)
        merge_link = factory(ctx.symbol, direction.tp_side, OrderPurpose.MERGE, event.timestamp)
        new_ctx = ctx.with_(
            position_size=total,
            bep=new_bep,
            pending_entry_link_id=None,
        )
        return Decision(
            new_ctx,
            (CancelAllTPs(), PlaceMergeTP(direction, merge_price, total, merge_link)),
        )

    if isinstance(event, CandleClose):
        # In merge pending we do NOT layer new entries; just wait for the merge to fill.
        return Decision(ctx, ())

    if isinstance(event, MergeTimerExpired):
        # Already merged; no-op. Could re-arm a back-off timer in a future revision.
        return Decision(ctx, ())

    if isinstance(event, OrderRejected):
        # If the merge itself was rejected, retry by re-emitting placement.
        if event.purpose is OrderPurpose.MERGE:
            merge_price = _tp_price(ctx.bep, direction, params.tp_offset_bps)
            merge_link = factory(ctx.symbol, direction.tp_side, OrderPurpose.MERGE, event.timestamp)
            return Decision(ctx, (PlaceMergeTP(direction, merge_price, ctx.position_size, merge_link),))
        return Decision(ctx, ())

    return Decision(ctx, ())
