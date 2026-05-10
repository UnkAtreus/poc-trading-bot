"""Testnet smoke script. Verifies API keys + WS plumbing without strategy logic.

Run: uv run python scripts/dry_testnet.py [--place-order]

Steps:
  1. Connect REST, fetch BTCUSDT instrument + position + open orders
  2. Subscribe to kline.1.BTCUSDT for ~90s, log every confirmed candle
  3. (Optional, with --place-order) Place a tiny PostOnly limit order far from
     market, verify it appears in get_open_orders, cancel it, verify gone.

Requires .env with BYBIT_API_KEY, BYBIT_API_SECRET, MODE=testnet.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time

from bot.config import Mode, load_settings
from bot.exchange.bybit_live import BybitLive
from bot.logger import configure as configure_logging, get_logger
from bot.models import Side


async def smoke(place_order: bool, kline_seconds: float) -> int:
    settings = load_settings()
    configure_logging(settings.env.log_level)
    log = get_logger("smoke")

    if settings.env.mode is Mode.MAINNET:
        log.error("refusing_mainnet_smoke")
        return 2
    if not settings.env.bybit_api_key or not settings.env.bybit_api_secret:
        log.error("missing_credentials")
        return 1

    adapter = BybitLive(
        api_key=settings.env.bybit_api_key,
        api_secret=settings.env.bybit_api_secret,
        testnet=settings.env.mode is Mode.TESTNET,
        leverage=settings.bot.sizing.leverage,
    )
    await adapter.start()

    symbol = settings.symbols.active[0] if settings.symbols.active else "BTCUSDT"
    log.info("smoke.start", symbol=symbol, mode=settings.env.mode.value)

    # 1. REST checks
    inst = await adapter.get_instrument(symbol)
    log.info("smoke.instrument", symbol=symbol, tick_size=str(inst.tick_size),
             qty_step=str(inst.qty_step), min_qty=str(inst.min_qty))
    pos = await adapter.get_position(symbol)
    log.info("smoke.position", symbol=symbol, size=pos.size, avg_price=pos.avg_price)
    open_orders = await adapter.get_open_orders(symbol)
    log.info("smoke.open_orders", symbol=symbol, count=len(open_orders))

    # 2. WS kline stream
    log.info("smoke.kline_stream_subscribing", seconds=kline_seconds)
    seen = 0
    deadline = time.time() + kline_seconds

    async def consume():
        nonlocal seen
        async for c in adapter.stream_klines([symbol], interval="1"):
            seen += 1
            log.info("smoke.kline", symbol=c.symbol, ts=c.timestamp,
                     close=c.close, confirm=c.confirm)
            if time.time() >= deadline:
                return

    try:
        await asyncio.wait_for(consume(), timeout=kline_seconds + 10)
    except asyncio.TimeoutError:
        pass
    log.info("smoke.kline_done", confirmed_candles=seen)

    # 3. Optional order round-trip
    if place_order:
        await _order_round_trip(adapter, symbol, inst, log)

    await adapter.stop()
    log.info("smoke.complete")
    return 0


async def _order_round_trip(adapter: BybitLive, symbol: str, inst, log) -> None:
    """Place a tiny PostOnly buy ~10% below market, confirm it lands, then cancel."""
    # Reuse the kline stream's last close to anchor a price; fetch via REST instead
    # for reliability inside the round-trip.
    pos = await adapter.get_position(symbol)
    # Pull a recent kline via REST.
    from pybit.unified_trading import HTTP  # noqa: E402
    h: HTTP = adapter._http  # type: ignore[attr-defined]
    r = h.get_kline(category="linear", symbol=symbol, interval="1", limit=1)
    last_close = float(r["result"]["list"][0][4])
    far_price = round(last_close * 0.90, int(-1 * (str(inst.tick_size).find('.') and 0 or 0))) or last_close * 0.90
    # Round to tick.
    from decimal import Decimal, ROUND_DOWN
    tick = inst.tick_size
    far_price_dec = (Decimal(str(last_close * 0.90)) / tick).quantize(Decimal("1"), rounding=ROUND_DOWN) * tick
    qty = inst.min_qty  # smallest legal qty

    link_id = f"{symbol}-Buy-entry-smoke{int(time.time())}"
    log.info("smoke.order.place", price=str(far_price_dec), qty=str(qty), link_id=link_id)
    ack = await adapter.place_limit(symbol, Side.BUY, float(qty), float(far_price_dec), link_id)
    if not ack.accepted:
        log.warning("smoke.order.rejected", reason=ack.reason)
        return

    await asyncio.sleep(2.0)
    open_orders = await adapter.get_open_orders(symbol)
    found = any(o.link_id == link_id for o in open_orders)
    log.info("smoke.order.visible_in_open_orders", found=found,
             count=len(open_orders))

    await adapter.cancel(symbol, link_id)
    await asyncio.sleep(2.0)
    open_orders = await adapter.get_open_orders(symbol)
    still_there = any(o.link_id == link_id for o in open_orders)
    log.info("smoke.order.after_cancel", still_there=still_there,
             count=len(open_orders))
    if still_there:
        log.warning("smoke.order.cancel_did_not_remove")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--place-order", action="store_true",
                        help="Round-trip a tiny limit order far from market")
    parser.add_argument("--kline-seconds", type=float, default=90.0,
                        help="How long to listen to kline.1 stream")
    args = parser.parse_args()
    return asyncio.run(smoke(args.place_order, args.kline_seconds))


if __name__ == "__main__":
    sys.exit(main())
