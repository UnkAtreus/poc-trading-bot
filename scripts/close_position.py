"""Cancel all open orders for a symbol and market-close any open position.

Usage:
  uv run python scripts/close_position.py SYMBOL

Reads `.env` (BYBIT_API_KEY, BYBIT_API_SECRET, MODE). Refuses mainnet without
an explicit `--allow-mainnet` flag.

Intended for clean cutover between bot configs when a symbol is being
dropped from the active basket. Run while the live bot is stopped to avoid
the reconcile loop re-issuing orders during the cleanup window.
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


async def close(symbol: str, allow_mainnet: bool) -> int:
    settings = load_settings()
    configure_logging(settings.env.log_level)
    log = get_logger("close_position")

    if settings.env.mode is Mode.MAINNET and not allow_mainnet:
        log.error("refusing_mainnet_without_flag", symbol=symbol)
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

    try:
        pos = await adapter.get_position(symbol)
        orders = await adapter.get_open_orders(symbol)
        log.info(
            "before",
            symbol=symbol,
            position_size=pos.size,
            position_avg=pos.avg_price,
            open_orders=len(orders),
            order_link_ids=[o.link_id for o in orders],
        )

        if orders:
            await adapter.cancel_all(symbol)
            log.info("cancelled_all_orders", symbol=symbol, count=len(orders))

        if abs(pos.size) > 0:
            close_side = Side.BUY if pos.size < 0 else Side.SELL
            link = f"{symbol}-close-{int(time.time())}"
            ack = await adapter.close_position_market(symbol, close_side, link)
            log.info(
                "close_position_market_ack",
                symbol=symbol,
                side=close_side.value,
                link_id=link,
                accepted=ack.accepted,
                reason=ack.reason,
            )
            if not ack.accepted:
                return 3

        # Re-poll a couple of times so Bybit has time to process.
        for attempt in range(5):
            await asyncio.sleep(1.0)
            pos = await adapter.get_position(symbol)
            orders = await adapter.get_open_orders(symbol)
            if abs(pos.size) == 0 and not orders:
                log.info("verified_flat", symbol=symbol, attempt=attempt + 1)
                return 0
            log.info(
                "still_settling",
                symbol=symbol,
                attempt=attempt + 1,
                position_size=pos.size,
                open_orders=len(orders),
            )
        log.error(
            "did_not_settle",
            symbol=symbol,
            position_size=pos.size,
            open_orders=len(orders),
        )
        return 4
    finally:
        await adapter.stop()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("symbol")
    parser.add_argument("--allow-mainnet", action="store_true")
    args = parser.parse_args()
    return asyncio.run(close(args.symbol.upper(), args.allow_mainnet))


if __name__ == "__main__":
    sys.exit(main())
