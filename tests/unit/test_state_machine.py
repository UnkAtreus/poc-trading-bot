from __future__ import annotations

import math

import pytest

from bot.models import Direction, OrderPurpose, Side
from bot.strategy import state_machine as sm
from bot.strategy.state_machine import (
    CancelAllTPs,
    CancelEntry,
    CandleClose,
    ClearMergeTimer,
    Context,
    EntryFilled,
    MergeTimerExpired,
    OrderRejected,
    Params,
    PlaceEntry,
    PlaceMergeTP,
    PlaceTP,
    RiskHalt,
    RiskResume,
    StartMergeTimer,
    TPFilled,
)
from bot.strategy.states import State


PARAMS = Params(
    entry_offset_bps=5.0,
    tp_offset_bps=10.0,
    merge_timer_seconds=1800,
    notional_usd=200.0,
)


def ctx(**kw) -> Context:
    base = dict(symbol="BTCUSDT")
    base.update(kw)
    return Context(**base)


def _types(actions):
    return [type(a) for a in actions]


# ---------- IDLE ----------

def test_idle_no_signal_no_action():
    c = ctx()
    d = sm.step(c, CandleClose(timestamp=1000.0, close_price=100.0), PARAMS)
    assert d.ctx.state is State.IDLE
    assert d.actions == ()


def test_idle_long_signal_places_entry_below_close():
    c = ctx()
    ev = CandleClose(timestamp=1000.0, close_price=100.0, signal_direction=Direction.LONG)
    d = sm.step(c, ev, PARAMS)
    assert d.ctx.state is State.ENTRY_PENDING
    assert d.ctx.direction is Direction.LONG
    assert _types(d.actions) == [PlaceEntry]
    a = d.actions[0]
    # 5 bps below 100 = 99.95
    assert math.isclose(a.price, 99.95, rel_tol=1e-9)
    assert math.isclose(a.qty, 200.0 / 99.95, rel_tol=1e-9)
    assert a.direction is Direction.LONG
    assert d.ctx.pending_entry_link_id == a.link_id


def test_idle_signal_size_scale_reduces_entry_qty():
    c = ctx()
    ev = CandleClose(
        timestamp=1000.0,
        close_price=100.0,
        signal_direction=Direction.LONG,
        notional_scale=0.25,
    )
    d = sm.step(c, ev, PARAMS)
    a = d.actions[0]
    assert math.isclose(a.qty, (200.0 * 0.25) / 99.95, rel_tol=1e-9)


def test_idle_signal_can_block_new_position():
    c = ctx()
    ev = CandleClose(
        timestamp=1000.0,
        close_price=100.0,
        signal_direction=Direction.LONG,
        allow_new_position=False,
    )
    d = sm.step(c, ev, PARAMS)
    assert d.ctx.state is State.IDLE
    assert d.actions == ()


def test_idle_short_signal_places_entry_above_close():
    c = ctx()
    ev = CandleClose(timestamp=1000.0, close_price=100.0, signal_direction=Direction.SHORT)
    d = sm.step(c, ev, PARAMS)
    assert d.ctx.state is State.ENTRY_PENDING
    assert d.ctx.direction is Direction.SHORT
    a = d.actions[0]
    assert math.isclose(a.price, 100.05, rel_tol=1e-9)


def test_idle_halted_does_not_enter():
    c = ctx(halted=True)
    ev = CandleClose(timestamp=1000.0, close_price=100.0, signal_direction=Direction.LONG)
    d = sm.step(c, ev, PARAMS)
    assert d.ctx.state is State.IDLE
    assert d.actions == ()


def test_idle_ignores_stray_fill():
    c = ctx()
    d = sm.step(c, EntryFilled("x", 1.0, 100.0, 1000.0), PARAMS)
    assert d.ctx.state is State.IDLE
    assert d.actions == ()


def test_idle_entry_fill_with_side_opens_position_and_places_tp():
    c = ctx()
    d = sm.step(c, EntryFilled("late", 1.0, 100.0, 1000.0, side=Side.BUY), PARAMS)
    assert d.ctx.state is State.IN_POSITION_TP_PENDING
    assert d.ctx.direction is Direction.LONG
    assert d.ctx.position_size == 1.0
    assert _types(d.actions) == [PlaceTP, StartMergeTimer]


# ---------- ENTRY_PENDING ----------

def test_entry_pending_fill_transitions_and_starts_timer():
    c = ctx(state=State.ENTRY_PENDING, direction=Direction.LONG, pending_entry_link_id="L1")
    d = sm.step(c, EntryFilled("L1", 2.0, 99.95, 1010.0), PARAMS)
    assert d.ctx.state is State.IN_POSITION_TP_PENDING
    assert d.ctx.position_size == 2.0
    assert math.isclose(d.ctx.bep, 99.95, rel_tol=1e-9)
    assert d.ctx.first_fill_ts == 1010.0
    assert d.ctx.pending_entry_link_id is None
    assert _types(d.actions) == [PlaceTP, StartMergeTimer]
    tp, timer = d.actions
    assert tp.qty == 2.0
    # +10bps on 99.95 = 100.04995
    assert math.isclose(tp.price, 99.95 * 1.001, rel_tol=1e-9)
    assert timer.deadline == 1010.0 + PARAMS.merge_timer_seconds


def test_entry_pending_unfilled_next_candle_no_signal_cancels_to_idle():
    c = ctx(state=State.ENTRY_PENDING, direction=Direction.LONG, pending_entry_link_id="L1")
    d = sm.step(c, CandleClose(timestamp=1060.0, close_price=101.0), PARAMS)
    assert d.ctx.state is State.IDLE
    assert d.ctx.direction is None
    assert d.ctx.pending_entry_link_id is None
    assert _types(d.actions) == [CancelEntry]


def test_entry_pending_unfilled_next_candle_new_signal_cancels_and_replaces():
    c = ctx(state=State.ENTRY_PENDING, direction=Direction.LONG, pending_entry_link_id="L1")
    ev = CandleClose(timestamp=1060.0, close_price=101.0, signal_direction=Direction.LONG)
    d = sm.step(c, ev, PARAMS)
    assert d.ctx.state is State.ENTRY_PENDING
    assert _types(d.actions) == [CancelEntry, PlaceEntry]
    assert d.actions[0].link_id == "L1"
    assert d.actions[1].link_id != "L1"
    assert d.ctx.pending_entry_link_id == d.actions[1].link_id


def test_entry_pending_rejection_returns_to_idle():
    c = ctx(state=State.ENTRY_PENDING, direction=Direction.LONG, pending_entry_link_id="L1")
    d = sm.step(c, OrderRejected("L1", OrderPurpose.ENTRY, 1010.0), PARAMS)
    assert d.ctx.state is State.IDLE
    assert d.ctx.pending_entry_link_id is None


# ---------- IN_POSITION_TP_PENDING ----------

def _in_pos(direction=Direction.LONG, size=1.0, bep=100.0, first_fill_ts=1000.0) -> Context:
    return ctx(
        state=State.IN_POSITION_TP_PENDING,
        direction=direction,
        position_size=size,
        bep=bep,
        first_fill_ts=first_fill_ts,
    )


def test_tp_filled_returns_to_idle_and_clears_timer():
    c = _in_pos()
    d = sm.step(c, TPFilled("TP1", 1.0, 100.1, 1500.0), PARAMS)
    assert d.ctx.state is State.IDLE
    assert d.ctx.position_size == 0.0
    assert d.ctx.bep == 0.0
    assert d.ctx.first_fill_ts is None
    assert _types(d.actions) == [ClearMergeTimer]


def test_partial_tp_fill_reduces_size_without_clearing_timer():
    c = _in_pos(size=2.0)
    d = sm.step(c, TPFilled("TP1", 0.75, 100.1, 1500.0), PARAMS)
    assert d.ctx.state is State.IN_POSITION_TP_PENDING
    assert d.ctx.position_size == 1.25
    assert d.ctx.bep == 100.0
    assert d.actions == ()


def test_in_position_layered_signal_places_new_entry():
    c = _in_pos()
    ev = CandleClose(timestamp=1100.0, close_price=99.0, signal_direction=Direction.LONG)
    d = sm.step(c, ev, PARAMS)
    # Must stay in IN_POSITION_TP_PENDING so the layered fill keeps weighted BEP.
    assert d.ctx.state is State.IN_POSITION_TP_PENDING
    assert d.ctx.position_size == 1.0  # unchanged until fill
    assert d.ctx.pending_entry_link_id is not None
    assert _types(d.actions) == [PlaceEntry]


def test_in_position_block_new_still_allows_layering():
    c = _in_pos()
    ev = CandleClose(
        timestamp=1100.0,
        close_price=99.0,
        signal_direction=Direction.LONG,
        allow_new_position=False,
    )
    d = sm.step(c, ev, PARAMS)
    assert _types(d.actions) == [PlaceEntry]


def test_in_position_signal_can_block_layering():
    c = _in_pos()
    ev = CandleClose(
        timestamp=1100.0,
        close_price=99.0,
        signal_direction=Direction.LONG,
        allow_layering=False,
    )
    d = sm.step(c, ev, PARAMS)
    assert d.actions == ()


def test_in_position_unfilled_layered_entry_cancelled_on_next_candle():
    """A stale unfilled layered entry must be cancelled at the next candle close,
    same rule as ENTRY_PENDING — otherwise the bot stalls forever in IN_POSITION."""
    c = _in_pos().with_(pending_entry_link_id="L_PENDING")
    ev = CandleClose(timestamp=1100.0, close_price=99.0, signal_direction=Direction.LONG)
    d = sm.step(c, ev, PARAMS)
    # Old entry cancelled, new one placed.
    assert _types(d.actions) == [CancelEntry, PlaceEntry]
    assert d.actions[0].link_id == "L_PENDING"
    assert d.ctx.pending_entry_link_id == d.actions[1].link_id


def test_in_position_unfilled_layered_entry_cancel_only_if_no_signal():
    c = _in_pos().with_(pending_entry_link_id="L_PENDING")
    ev = CandleClose(timestamp=1100.0, close_price=99.0)
    d = sm.step(c, ev, PARAMS)
    # Only cancel; no new entry since no signal.
    assert _types(d.actions) == [CancelEntry]
    assert d.ctx.pending_entry_link_id is None


def test_in_position_layered_fill_recomputes_bep_and_replaces_tp():
    c = _in_pos(size=1.0, bep=100.0)
    d = sm.step(c, EntryFilled("L2", 1.0, 98.0, 1200.0), PARAMS)
    # New BEP = (100*1 + 98*1)/2 = 99
    assert d.ctx.position_size == 2.0
    assert math.isclose(d.ctx.bep, 99.0, rel_tol=1e-9)
    # First-fill timestamp must NOT change (first_fill policy)
    assert d.ctx.first_fill_ts == 1000.0
    assert _types(d.actions) == [CancelAllTPs, PlaceTP]
    tp = d.actions[1]
    assert tp.qty == 2.0
    assert math.isclose(tp.price, 99.0 * 1.001, rel_tol=1e-9)


def test_in_position_opposite_signal_ignored_no_flip():
    c = _in_pos(direction=Direction.LONG)
    ev = CandleClose(timestamp=1100.0, close_price=99.0, signal_direction=Direction.SHORT)
    d = sm.step(c, ev, PARAMS)
    assert d.ctx.state is State.IN_POSITION_TP_PENDING
    assert d.actions == ()


def test_in_position_halted_no_new_entries_but_tp_unchanged():
    c = _in_pos()
    c = c.with_(halted=True)
    ev = CandleClose(timestamp=1100.0, close_price=99.0, signal_direction=Direction.LONG)
    d = sm.step(c, ev, PARAMS)
    assert d.ctx.state is State.IN_POSITION_TP_PENDING
    assert d.actions == ()


def test_in_position_merge_timer_expired_cancels_and_places_merge():
    c = _in_pos(size=2.0, bep=99.0)
    d = sm.step(c, MergeTimerExpired(timestamp=2810.0), PARAMS)
    assert d.ctx.state is State.MERGE_PENDING
    assert _types(d.actions) == [CancelAllTPs, PlaceMergeTP]
    merge = d.actions[1]
    assert merge.qty == 2.0
    assert math.isclose(merge.price, 99.0 * 1.001, rel_tol=1e-9)


def test_in_position_tp_rejection_below_min_notional_flips_to_dust_stranded():
    c = _in_pos(size=0.1, bep=1.5047)
    reason = "notional_below_min(0.14896 < 5)"
    d = sm.step(c, OrderRejected("TP1", OrderPurpose.TP, 2900.0, reason=reason), PARAMS)
    assert d.ctx.state is State.DUST_STRANDED
    assert d.actions == ()
    assert d.ctx.position_size == 0.1
    assert math.isclose(d.ctx.bep, 1.5047, rel_tol=1e-9)


def test_in_position_tp_rejection_bybit_110017_flips_to_dust_stranded():
    c = _in_pos(size=5.4, bep=89.97)
    reason = "orderQty will be truncated to zero. (ErrCode: 110017)"
    d = sm.step(c, OrderRejected("TP1", OrderPurpose.TP, 2900.0, reason=reason), PARAMS)
    assert d.ctx.state is State.DUST_STRANDED
    assert d.actions == ()


# ---------- MERGE_PENDING ----------

def _merge(size=2.0, bep=99.0) -> Context:
    return ctx(
        state=State.MERGE_PENDING,
        direction=Direction.LONG,
        position_size=size,
        bep=bep,
        first_fill_ts=1000.0,
    )


def test_merge_filled_returns_to_idle():
    c = _merge()
    d = sm.step(c, TPFilled("M1", 2.0, 99.099, 3000.0), PARAMS)
    assert d.ctx.state is State.IDLE
    assert _types(d.actions) == [ClearMergeTimer]


def test_partial_merge_fill_stays_merge_pending():
    c = _merge(size=2.0)
    d = sm.step(c, TPFilled("M1", 0.5, 99.099, 3000.0), PARAMS)
    assert d.ctx.state is State.MERGE_PENDING
    assert d.ctx.position_size == 1.5
    assert d.actions == ()


def test_merge_pending_layered_fill_remerges():
    c = _merge(size=2.0, bep=99.0)
    d = sm.step(c, EntryFilled("L3", 1.0, 98.0, 2900.0), PARAMS)
    assert d.ctx.state is State.MERGE_PENDING
    assert d.ctx.position_size == 3.0
    # New BEP = (99*2 + 98*1)/3 = 98.6666...
    assert math.isclose(d.ctx.bep, (99 * 2 + 98) / 3, rel_tol=1e-9)
    assert _types(d.actions) == [CancelAllTPs, PlaceMergeTP]


def test_merge_pending_no_layering_on_signal():
    c = _merge()
    ev = CandleClose(timestamp=2900.0, close_price=99.0, signal_direction=Direction.LONG)
    d = sm.step(c, ev, PARAMS)
    assert d.actions == ()


def test_merge_rejected_retries():
    c = _merge()
    d = sm.step(c, OrderRejected("M1", OrderPurpose.MERGE, 2900.0), PARAMS)
    assert d.ctx.state is State.MERGE_PENDING
    assert _types(d.actions) == [PlaceMergeTP]


def test_merge_rejection_with_notional_below_min_flips_to_dust_stranded():
    c = _merge(size=0.1, bep=1.5047)
    reason = "notional_below_min(0.14896 < 5)"
    d = sm.step(c, OrderRejected("M1", OrderPurpose.MERGE, 2900.0, reason=reason), PARAMS)
    assert d.ctx.state is State.DUST_STRANDED
    assert d.actions == ()
    # Position remains intact so the operator can close it manually.
    assert d.ctx.position_size == 0.1
    assert math.isclose(d.ctx.bep, 1.5047, rel_tol=1e-9)


def test_merge_rejection_with_qty_below_min_also_flips_to_dust_stranded():
    c = _merge(size=0.001, bep=1.5)
    d = sm.step(
        c,
        OrderRejected("M1", OrderPurpose.MERGE, 2900.0, reason="qty_below_min(0.001 < 0.01)"),
        PARAMS,
    )
    assert d.ctx.state is State.DUST_STRANDED


# ---------- DUST_STRANDED ----------

def _dust(size=0.1, bep=1.5047) -> Context:
    return ctx(
        state=State.DUST_STRANDED,
        direction=Direction.SHORT,
        position_size=size,
        bep=bep,
        first_fill_ts=1000.0,
    )


def test_dust_stranded_ignores_candle_close():
    c = _dust()
    ev = CandleClose(timestamp=3000.0, close_price=1.5, signal_direction=Direction.SHORT)
    d = sm.step(c, ev, PARAMS)
    assert d.ctx.state is State.DUST_STRANDED
    assert d.actions == ()


def test_dust_stranded_ignores_merge_timer_and_rejections():
    c = _dust()
    d1 = sm.step(c, MergeTimerExpired(timestamp=3000.0), PARAMS)
    assert d1.ctx.state is State.DUST_STRANDED
    assert d1.actions == ()
    d2 = sm.step(c, OrderRejected("M2", OrderPurpose.MERGE, 3000.0, reason="anything"), PARAMS)
    assert d2.ctx.state is State.DUST_STRANDED
    assert d2.actions == ()


def test_dust_stranded_manual_close_via_tp_fill_returns_to_idle():
    c = _dust()
    d = sm.step(c, TPFilled("M1", 0.1, 1.5, 3500.0), PARAMS)
    assert d.ctx.state is State.IDLE
    assert d.ctx.position_size == 0.0
    assert _types(d.actions) == [ClearMergeTimer]


def test_dust_stranded_partial_manual_close_keeps_dust_state():
    c = _dust(size=0.1)
    d = sm.step(c, TPFilled("M1", 0.04, 1.5, 3500.0), PARAMS)
    assert d.ctx.state is State.DUST_STRANDED
    assert d.ctx.position_size == pytest.approx(0.06)
    assert d.actions == ()


def test_dust_stranded_layered_fill_recovers_to_merge_pending():
    # An EntryFilled large enough to push the position above min notional
    # should re-arm the merge with a fresh PlaceMergeTP at the new BEP.
    c = _dust(size=0.1, bep=1.5047)
    d = sm.step(c, EntryFilled("L9", 10.0, 1.49, 3600.0), PARAMS)
    assert d.ctx.state is State.MERGE_PENDING
    assert d.ctx.position_size == 10.1
    expected_bep = (1.5047 * 0.1 + 1.49 * 10.0) / 10.1
    assert math.isclose(d.ctx.bep, expected_bep, rel_tol=1e-9)
    assert _types(d.actions) == [CancelAllTPs, PlaceMergeTP]


# ---------- Risk halt ----------

def test_risk_halt_sets_flag_no_actions():
    c = ctx()
    d = sm.step(c, RiskHalt(timestamp=1000.0), PARAMS)
    assert d.ctx.halted is True
    assert d.actions == ()


def test_risk_resume_clears_flag():
    c = ctx(halted=True)
    d = sm.step(c, RiskResume(timestamp=1000.0), PARAMS)
    assert d.ctx.halted is False


# ---------- Short-side mirror ----------

def test_short_entry_then_fill_then_tp_below():
    c = ctx()
    d1 = sm.step(c, CandleClose(1000.0, 100.0, Direction.SHORT), PARAMS)
    assert d1.ctx.direction is Direction.SHORT
    assert math.isclose(d1.actions[0].price, 100.05, rel_tol=1e-9)
    d2 = sm.step(d1.ctx, EntryFilled(d1.actions[0].link_id, 2.0, 100.05, 1010.0), PARAMS)
    tp = d2.actions[0]
    assert math.isclose(tp.price, 100.05 * 0.999, rel_tol=1e-9)


def test_short_layered_fill_recomputes_bep_higher():
    c = ctx(
        state=State.IN_POSITION_TP_PENDING,
        direction=Direction.SHORT,
        position_size=1.0,
        bep=100.0,
        first_fill_ts=1000.0,
    )
    d = sm.step(c, EntryFilled("L2", 1.0, 102.0, 1200.0), PARAMS)
    assert math.isclose(d.ctx.bep, 101.0, rel_tol=1e-9)
    tp = d.actions[1]
    assert math.isclose(tp.price, 101.0 * 0.999, rel_tol=1e-9)


# ---------- Restart-from-snapshot ----------

def test_restart_in_position_can_continue():
    """Replays a state restored from snapshot; SM behaves identically."""
    c = ctx(
        state=State.IN_POSITION_TP_PENDING,
        direction=Direction.LONG,
        position_size=1.5,
        bep=100.0,
        first_fill_ts=1000.0,
    )
    # Add a layered fill -> should re-merge BEP correctly.
    d = sm.step(c, EntryFilled("X", 0.5, 98.0, 2000.0), PARAMS)
    assert math.isclose(d.ctx.bep, (100 * 1.5 + 98 * 0.5) / 2.0, rel_tol=1e-9)
