"""Opt-in integration tests against Bybit testnet.

Run only when explicitly requested:
    uv run pytest -m testnet

Requires .env with BYBIT_API_KEY, BYBIT_API_SECRET, MODE=testnet.
Skips automatically if credentials are missing.
"""

from __future__ import annotations

import asyncio
import os
import time
from decimal import ROUND_DOWN, Decimal

import pytest

from bot.config import Mode, load_settings
from bot.exchange.bybit_live import BybitLive
from bot.models import Side


pytestmark = pytest.mark.testnet


def _has_creds() -> bool:
    try:
        s = load_settings()
    except Exception:
        return False
    if s.env.mode is not Mode.TESTNET:
        return False
    return bool(s.env.bybit_api_key and s.env.bybit_api_secret)


pytestmark = [pytest.mark.testnet,
              pytest.mark.skipif(not _has_creds(),
                                 reason="testnet creds not configured in .env")]


@pytest.fixture
async def adapter():
    s = load_settings()
    a = BybitLive(
        api_key=s.env.bybit_api_key,
        api_secret=s.env.bybit_api_secret,
        testnet=True,
        leverage=s.bot.sizing.leverage,
    )
    await a.start()
    yield a
    await a.stop()


@pytest.mark.asyncio
async def test_get_instrument_returns_filters(adapter):
    inst = await adapter.get_instrument("BTCUSDT")
    assert inst.symbol == "BTCUSDT"
    assert inst.tick_size > 0
    assert inst.qty_step > 0


@pytest.mark.asyncio
async def test_get_position_succeeds(adapter):
    pos = await adapter.get_position("BTCUSDT")
    assert pos.symbol == "BTCUSDT"
    # size may be zero or whatever the testnet account has — we only assert the call works.
    assert pos.size == pos.size  # not NaN


@pytest.mark.asyncio
async def test_kline_stream_emits_confirmed_candle(adapter):
    """Wait up to 90s for at least one confirmed 1m candle."""
    seen = 0

    async def consume():
        nonlocal seen
        async for c in adapter.stream_klines(["BTCUSDT"], interval="1"):
            if c.confirm:
                seen += 1
                if seen >= 1:
                    return

    await asyncio.wait_for(consume(), timeout=90.0)
    assert seen >= 1


@pytest.mark.asyncio
async def test_place_then_cancel_far_limit(adapter):
    """Round-trip: place tiny limit far from market, see it, cancel it."""
    inst = await adapter.get_instrument("BTCUSDT")
    h = adapter._http  # noqa: SLF001
    r = h.get_kline(category="linear", symbol="BTCUSDT", interval="1", limit=1)
    last_close = float(r["result"]["list"][0][4])

    tick = inst.tick_size
    far_price_dec = (
        Decimal(str(last_close * 0.90)) / tick
    ).quantize(Decimal("1"), rounding=ROUND_DOWN) * tick
    qty = inst.min_qty

    link_id = f"BTCUSDT-Buy-entry-it{int(time.time())}"
    ack = await adapter.place_limit("BTCUSDT", Side.BUY, float(qty),
                                    float(far_price_dec), link_id)
    assert ack.accepted, ack.reason

    await asyncio.sleep(2.0)
    open_before = await adapter.get_open_orders("BTCUSDT")
    assert any(o.link_id == link_id for o in open_before)

    await adapter.cancel("BTCUSDT", link_id)
    await asyncio.sleep(2.0)
    open_after = await adapter.get_open_orders("BTCUSDT")
    assert not any(o.link_id == link_id for o in open_after)
