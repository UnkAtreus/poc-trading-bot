from __future__ import annotations

import pytest

from bot.exchange.simulator import Simulator
from bot.models import Candle, OrderPurpose, Side


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
