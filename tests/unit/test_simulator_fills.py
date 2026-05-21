from __future__ import annotations

from decimal import Decimal

import pytest

from bot.backtest.execution import BacktestExecutionConfig
from bot.exchange.simulator import Simulator
from bot.models import Candle, Instrument, Side


def cdl(o, h, l, c, ts=1.0, sym="BTCUSDT"):
    return Candle(symbol=sym, timestamp=ts, open=o, high=h, low=l, close=c, volume=1.0)


@pytest.mark.asyncio
async def test_buy_limit_fills_when_low_below_price():
    sim = Simulator()
    await sim.place_limit("BTCUSDT", Side.BUY, qty=1.0, price=99.0,
                          link_id="BTCUSDT-Buy-entry-1")
    await sim.feed_candle(cdl(100.0, 100.5, 98.5, 99.5))
    assert len(sim.fills) == 1
    assert sim.fills[0].side is Side.BUY
    assert sim.fills[0].price == 99.0


@pytest.mark.asyncio
async def test_buy_limit_does_not_fill_when_low_above_price():
    sim = Simulator()
    await sim.place_limit("BTCUSDT", Side.BUY, qty=1.0, price=99.0,
                          link_id="BTCUSDT-Buy-entry-1")
    await sim.feed_candle(cdl(100.0, 100.5, 99.5, 100.2))
    assert sim.fills == []


@pytest.mark.asyncio
async def test_sell_limit_fills_when_high_above_price():
    sim = Simulator()
    await sim.place_limit("BTCUSDT", Side.SELL, qty=1.0, price=101.0,
                          link_id="BTCUSDT-Sell-entry-1")
    await sim.feed_candle(cdl(100.0, 101.5, 99.5, 100.5))
    assert len(sim.fills) == 1
    assert sim.fills[0].side is Side.SELL
    assert sim.fills[0].price == 101.0


@pytest.mark.asyncio
async def test_cancel_removes_order():
    sim = Simulator()
    await sim.place_limit("BTCUSDT", Side.BUY, qty=1.0, price=99.0,
                          link_id="BTCUSDT-Buy-entry-1")
    await sim.cancel("BTCUSDT", "BTCUSDT-Buy-entry-1")
    await sim.feed_candle(cdl(100.0, 100.5, 98.5, 99.5))
    assert sim.fills == []


@pytest.mark.asyncio
async def test_position_avg_price_after_layered_fills():
    sim = Simulator()
    await sim.place_limit("BTCUSDT", Side.BUY, qty=1.0, price=100.0,
                          link_id="BTCUSDT-Buy-entry-1")
    await sim.feed_candle(cdl(100.0, 100.5, 99.5, 100.2))
    await sim.place_limit("BTCUSDT", Side.BUY, qty=1.0, price=98.0,
                          link_id="BTCUSDT-Buy-entry-2")
    await sim.feed_candle(cdl(99.0, 99.0, 97.5, 98.5))
    pos = await sim.get_position("BTCUSDT")
    assert pos.size == 2.0
    assert pos.avg_price == 99.0  # (100 + 98) / 2


@pytest.mark.asyncio
async def test_position_reduces_to_flat_on_tp():
    sim = Simulator()
    await sim.place_limit("BTCUSDT", Side.BUY, qty=1.0, price=100.0,
                          link_id="BTCUSDT-Buy-entry-1")
    await sim.feed_candle(cdl(100.0, 100.5, 99.5, 100.2))
    await sim.place_limit("BTCUSDT", Side.SELL, qty=1.0, price=100.1,
                          link_id="BTCUSDT-Sell-tp-1")
    await sim.feed_candle(cdl(100.0, 100.3, 99.5, 100.2))
    pos = await sim.get_position("BTCUSDT")
    assert pos.size == 0.0
    assert pos.avg_price == 0.0


@pytest.mark.asyncio
async def test_up_bar_traversal_buy_fills_before_sell():
    """On an up bar O->H->L->C, a buy limit at low and sell limit at high
    both fill. Buy fills second (after high)."""
    sim = Simulator()
    await sim.place_limit("BTCUSDT", Side.BUY, qty=1.0, price=99.5,
                          link_id="BTCUSDT-Buy-entry-1")
    await sim.place_limit("BTCUSDT", Side.SELL, qty=1.0, price=100.5,
                          link_id="BTCUSDT-Sell-tp-1")
    # Up bar: traversal O=100, H=101, L=99, C=100.8
    await sim.feed_candle(cdl(100.0, 101.0, 99.0, 100.8))
    sides = [f.side for f in sim.fills]
    assert sides == [Side.SELL, Side.BUY]


@pytest.mark.asyncio
async def test_realistic_touch_only_does_not_fill():
    sim = Simulator(execution=BacktestExecutionConfig.realistic(latency_seconds=0.0))
    await sim.place_limit("BTCUSDT", Side.BUY, qty=1.0, price=99.0,
                          link_id="BTCUSDT-Buy-entry-1")
    await sim.feed_candle(cdl(100.0, 100.5, 99.0, 100.2))
    assert sim.fills == []


@pytest.mark.asyncio
async def test_realistic_fill_requires_price_after_latency():
    early = Simulator(execution=BacktestExecutionConfig.realistic(
        latency_seconds=50.0,
        slippage_bps=0.0,
        pass_through_bps=1.0,
        full_fill_bps=1.0,
    ))
    await early.place_limit("BTCUSDT", Side.BUY, qty=1.0, price=99.0,
                            link_id="BTCUSDT-Buy-entry-1")
    await early.feed_candle(cdl(100.0, 100.5, 98.5, 100.2, ts=60.0))
    assert early.fills == []

    active = Simulator(execution=BacktestExecutionConfig.realistic(
        latency_seconds=30.0,
        slippage_bps=0.0,
        pass_through_bps=1.0,
        full_fill_bps=1.0,
    ))
    await active.place_limit("BTCUSDT", Side.BUY, qty=1.0, price=99.0,
                             link_id="BTCUSDT-Buy-entry-1")
    await active.feed_candle(cdl(100.0, 100.5, 98.5, 100.2, ts=60.0))
    assert len(active.fills) == 1


@pytest.mark.asyncio
async def test_realistic_cancel_delay_allows_cancel_race_fill():
    sim = Simulator(execution=BacktestExecutionConfig.realistic(
        latency_seconds=0.0,
        cancel_delay_seconds=60.0,
        slippage_bps=0.0,
        pass_through_bps=1.0,
        full_fill_bps=1.0,
    ))
    await sim.place_limit("BTCUSDT", Side.BUY, qty=1.0, price=99.0,
                          link_id="BTCUSDT-Buy-entry-1")
    await sim.cancel("BTCUSDT", "BTCUSDT-Buy-entry-1")
    await sim.feed_candle(cdl(100.0, 100.5, 98.5, 100.2, ts=60.0))
    assert len(sim.fills) == 1
    assert sim.execution_stats.cancel_race_fills == 1


@pytest.mark.asyncio
async def test_realistic_partial_fill_leaves_remainder_open():
    sim = Simulator(execution=BacktestExecutionConfig.realistic(
        latency_seconds=0.0,
        slippage_bps=0.0,
        pass_through_bps=1.0,
        full_fill_bps=10.0,
        min_partial_fill_pct=25.0,
    ))
    await sim.place_limit("BTCUSDT", Side.BUY, qty=1.0, price=100.0,
                          link_id="BTCUSDT-Buy-entry-1")
    await sim.feed_candle(cdl(101.0, 101.0, 99.98, 100.5, ts=60.0))
    assert len(sim.fills) == 1
    assert 0.25 < sim.fills[0].qty < 1.0
    assert sim.execution_stats.partial_fills == 1
    open_orders = await sim.get_open_orders("BTCUSDT")
    assert len(open_orders) == 1
    assert open_orders[0].qty == pytest.approx(1.0 - sim.fills[0].qty)


@pytest.mark.asyncio
async def test_realistic_applies_adverse_slippage_to_fill_price_and_stats():
    sim = Simulator(execution=BacktestExecutionConfig.realistic(
        latency_seconds=0.0,
        slippage_bps=2.0,
        pass_through_bps=1.0,
        full_fill_bps=1.0,
    ))
    await sim.place_limit("BTCUSDT", Side.BUY, qty=1.0, price=100.0,
                          link_id="BTCUSDT-Buy-entry-1")
    await sim.feed_candle(cdl(101.0, 101.0, 99.0, 100.5, ts=60.0))
    assert sim.fills[0].price == pytest.approx(100.02)
    assert sim.execution_stats.slippage_cost == pytest.approx(0.02)


@pytest.mark.asyncio
async def test_realistic_rejects_below_min_notional():
    sim = Simulator(
        instruments={
            "XRPUSDT": Instrument(
                symbol="XRPUSDT",
                tick_size=Decimal("0.0001"),
                qty_step=Decimal("0.1"),
                min_notional=Decimal("5"),
                min_qty=Decimal("0.1"),
            )
        },
        execution=BacktestExecutionConfig.realistic(latency_seconds=0.0),
    )
    ack = await sim.place_limit("XRPUSDT", Side.SELL, qty=1.0, price=0.25,
                                link_id="XRPUSDT-Sell-tp-1", reduce_only=True)
    assert ack.accepted is False
    assert ack.reason == "notional_below_min(0.250 < 5)"
    assert sim.execution_stats.rejected_orders == 1
    assert sim.execution_stats.dust_rejected == 1
