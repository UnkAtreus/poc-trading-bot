"""Liquidation and account-risk helpers for USDT linear perpetual backtests.

The formulas intentionally model a conservative approximation of Bybit USDT
perpetual risk: initial margin is position notional divided by leverage, and
liquidation is triggered when equity no longer covers maintenance margin.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import inf

from bot.config import AccountConfig, LiquidationConfig
from bot.models import Direction


class MarginMode(str, Enum):
    CROSS = "cross"
    ISOLATED = "isolated"


@dataclass(frozen=True)
class PositionRisk:
    symbol: str
    direction: Direction
    qty: float
    avg_entry: float
    mark: float
    adverse_mark: float | None = None

    @property
    def notional(self) -> float:
        return self.qty * self.mark

    def unrealized_at(self, price: float) -> float:
        if self.direction is Direction.LONG:
            return (price - self.avg_entry) * self.qty
        return (self.avg_entry - price) * self.qty


@dataclass(frozen=True)
class AccountRiskInput:
    initial_equity: float
    realized_net: float
    positions: tuple[PositionRisk, ...]
    pending_entry_notional: float = 0.0
    leverage: float = 1.0
    maintenance_margin_rate: float = 0.005
    taker_exit_bps: float = 0.0
    funding_stress_bps: float = 0.0
    margin_mode: MarginMode = MarginMode.CROSS


@dataclass(frozen=True)
class PositionLiquidation:
    symbol: str
    liquidation_price: float | None
    distance_pct: float
    liquidated: bool
    near_liquidation: bool


@dataclass(frozen=True)
class AccountRiskSnapshot:
    equity: float
    adverse_equity: float
    maintenance_margin: float
    initial_margin: float
    pending_initial_margin: float
    available_balance: float
    margin_ratio: float
    min_liq_distance_pct: float
    worst_unrealized_loss: float
    final_open_exposure: float
    liquidated: bool
    near_liquidation: bool
    positions: tuple[PositionLiquidation, ...]


def config_to_input(
    *,
    account: AccountConfig,
    liquidation: LiquidationConfig,
    realized_net: float,
    positions: tuple[PositionRisk, ...],
    pending_entry_notional: float,
    leverage: float,
) -> AccountRiskInput:
    return AccountRiskInput(
        initial_equity=account.initial_equity,
        realized_net=realized_net,
        positions=positions,
        pending_entry_notional=pending_entry_notional,
        leverage=leverage,
        maintenance_margin_rate=liquidation.maintenance_margin_rate,
        taker_exit_bps=liquidation.taker_exit_bps or 0.0,
        funding_stress_bps=liquidation.funding_stress_bps,
        margin_mode=MarginMode(account.margin_mode),
    )


def liquidation_price(
    *,
    direction: Direction,
    avg_entry: float,
    leverage: float,
    maintenance_margin_rate: float,
    fee_buffer_bps: float = 0.0,
) -> float | None:
    """Return isolated liquidation price for a linear USDT position.

    Fee/funding buffers reduce usable margin, pushing long liquidation higher
    and short liquidation lower. Invalid inputs return None instead of raising
    so callers can keep scanning partial datasets.
    """
    if avg_entry <= 0 or leverage <= 0:
        return None
    mmr = maintenance_margin_rate
    if not 0 <= mmr < 1:
        return None
    margin_per_unit = avg_entry / leverage
    fee_buffer_per_unit = avg_entry * (fee_buffer_bps / 10_000.0)
    usable_margin = max(0.0, margin_per_unit - fee_buffer_per_unit)
    if direction is Direction.LONG:
        denom = 1.0 - mmr
        if denom <= 0:
            return None
        return max(0.0, (avg_entry - usable_margin) / denom)
    denom = 1.0 + mmr
    return max(0.0, (avg_entry + usable_margin) / denom)


def assess_account_risk(inp: AccountRiskInput, *, near_liq_buffer_pct: float) -> AccountRiskSnapshot:
    leverage = max(inp.leverage, 1.0)
    fee_buffer_bps = inp.taker_exit_bps + inp.funding_stress_bps
    equity = inp.initial_equity + inp.realized_net + sum(p.unrealized_at(p.mark) for p in inp.positions)
    adverse_equity = (
        inp.initial_equity
        + inp.realized_net
        + sum(p.unrealized_at(p.adverse_mark if p.adverse_mark is not None else p.mark) for p in inp.positions)
    )
    maintenance = sum(p.notional * inp.maintenance_margin_rate for p in inp.positions)
    initial = sum(p.avg_entry * p.qty / leverage for p in inp.positions)
    pending_initial = inp.pending_entry_notional / leverage
    fee_reserve = (sum(p.notional for p in inp.positions) + inp.pending_entry_notional) * (
        inp.taker_exit_bps / 10_000.0
    )
    funding_reserve = sum(p.notional for p in inp.positions) * (inp.funding_stress_bps / 10_000.0)
    available = equity - initial - pending_initial - fee_reserve - funding_reserve
    margin_ratio = maintenance / equity if equity > 0 else inf

    pos_liqs: list[PositionLiquidation] = []
    min_distance = inf
    isolated_liquidated = False
    isolated_near = False
    for p in inp.positions:
        liq = liquidation_price(
            direction=p.direction,
            avg_entry=p.avg_entry,
            leverage=leverage,
            maintenance_margin_rate=inp.maintenance_margin_rate,
            fee_buffer_bps=fee_buffer_bps,
        )
        distance = inf
        hit = False
        near = False
        if liq is not None and p.mark > 0:
            if p.direction is Direction.LONG:
                distance = max(0.0, (p.mark - liq) / p.mark * 100.0)
                adverse = p.adverse_mark if p.adverse_mark is not None else p.mark
                hit = adverse <= liq
            else:
                distance = max(0.0, (liq - p.mark) / p.mark * 100.0)
                adverse = p.adverse_mark if p.adverse_mark is not None else p.mark
                hit = adverse >= liq
            near = distance <= near_liq_buffer_pct
            min_distance = min(min_distance, distance)
        isolated_liquidated = isolated_liquidated or hit
        isolated_near = isolated_near or near
        pos_liqs.append(PositionLiquidation(p.symbol, liq, distance, hit, near))

    cross_liquidated = adverse_equity <= maintenance
    cross_near = margin_ratio >= 0.80 or available <= 0.0
    if inp.margin_mode is MarginMode.ISOLATED:
        liquidated = isolated_liquidated
        near_liq = isolated_near
    else:
        liquidated = cross_liquidated
        near_liq = cross_near

    unrealized_losses = [p.unrealized_at(p.mark) for p in inp.positions]

    return AccountRiskSnapshot(
        equity=equity,
        adverse_equity=adverse_equity,
        maintenance_margin=maintenance,
        initial_margin=initial,
        pending_initial_margin=pending_initial,
        available_balance=available,
        margin_ratio=margin_ratio,
        min_liq_distance_pct=0.0 if min_distance == inf else min_distance,
        worst_unrealized_loss=min([0.0, *unrealized_losses]),
        final_open_exposure=sum(p.notional for p in inp.positions),
        liquidated=liquidated,
        near_liquidation=near_liq,
        positions=tuple(pos_liqs),
    )
