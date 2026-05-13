from __future__ import annotations

from decimal import Decimal

from bot.exchange.bybit_live import _normalize_order
from bot.models import Instrument


def _inst() -> Instrument:
    return Instrument(
        symbol="XAUTUSDT",
        tick_size=Decimal("0.01"),
        qty_step=Decimal("0.001"),
        min_notional=Decimal("5"),
        min_qty=Decimal("0.001"),
    )


def test_normalize_order_floors_qty_and_price_to_exchange_steps():
    qty, price, reason = _normalize_order(
        _inst(),
        qty=0.14531594046841864,
        price=4541.827950000001,
    )

    assert reason is None
    assert qty == "0.145"
    assert price == "4541.82"


def test_normalize_order_rejects_below_min_qty():
    qty, price, reason = _normalize_order(_inst(), qty=0.0009, price=4541.82795)

    assert qty == ""
    assert price == ""
    assert reason == "qty_below_min(0.000 < 0.001)"


def test_normalize_order_rejects_below_min_notional():
    qty, price, reason = _normalize_order(_inst(), qty=0.001, price=1000.0)

    assert qty == ""
    assert price == ""
    assert reason == "notional_below_min(1.0000 < 5)"
