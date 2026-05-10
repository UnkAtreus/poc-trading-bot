"""Market-regime labeling for strategy routing."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from bot.models import Candle


REGIMES = ("sideways", "uptrend", "downtrend", "crash", "high_volatility", "low_liquidity")


@dataclass(frozen=True)
class MarketRegime:
    label: str
    btc_return_pct: float
    basket_return_pct: float
    max_drawdown_pct: float
    annualized_vol_pct: float
    volume_ratio: float
    reason: str


def classify_market(candles_by_symbol: dict[str, list[Candle]]) -> MarketRegime:
    if not candles_by_symbol:
        return MarketRegime("low_liquidity", 0.0, 0.0, 0.0, 0.0, 0.0, "no candle data")

    btc = candles_by_symbol.get("BTCUSDT") or next(iter(candles_by_symbol.values()))
    btc_return = _return_pct(btc)
    basket_return = sum(_return_pct(v) for v in candles_by_symbol.values() if v) / max(
        1, sum(1 for v in candles_by_symbol.values() if v)
    )
    drawdown = max(_max_drawdown_pct(v) for v in candles_by_symbol.values() if v)
    vol = _annualized_vol_pct(btc)
    volume_ratio = _volume_ratio(btc)

    if volume_ratio < 0.35:
        label = "low_liquidity"
        reason = "recent BTC volume is far below its earlier sample average"
    elif drawdown >= 25.0 or basket_return <= -30.0:
        label = "crash"
        reason = "basket drawdown or return breached crash threshold"
    elif vol >= 120.0:
        label = "high_volatility"
        reason = "BTC realized volatility is elevated"
    elif btc_return >= 12.0 and basket_return >= 5.0:
        label = "uptrend"
        reason = "BTC and basket returns are positive"
    elif btc_return <= -12.0 and basket_return <= -5.0:
        label = "downtrend"
        reason = "BTC and basket returns are negative"
    else:
        label = "sideways"
        reason = "trend and volatility thresholds were not breached"

    return MarketRegime(
        label=label,
        btc_return_pct=btc_return,
        basket_return_pct=basket_return,
        max_drawdown_pct=drawdown,
        annualized_vol_pct=vol,
        volume_ratio=volume_ratio,
        reason=reason,
    )


def render_regime(regime: MarketRegime) -> str:
    return "\n".join([
        f"regime        : {regime.label}",
        f"reason        : {regime.reason}",
        f"btc return    : {regime.btc_return_pct:+.2f}%",
        f"basket return : {regime.basket_return_pct:+.2f}%",
        f"max drawdown  : {regime.max_drawdown_pct:.2f}%",
        f"ann. vol      : {regime.annualized_vol_pct:.2f}%",
        f"volume ratio  : {regime.volume_ratio:.2f}",
    ])


def _return_pct(candles: list[Candle]) -> float:
    if len(candles) < 2 or candles[0].open <= 0:
        return 0.0
    return (candles[-1].close / candles[0].open - 1.0) * 100.0


def _max_drawdown_pct(candles: list[Candle]) -> float:
    peak = 0.0
    max_dd = 0.0
    for c in candles:
        peak = max(peak, c.high)
        if peak > 0:
            max_dd = max(max_dd, (peak - c.low) / peak * 100.0)
    return max_dd


def _annualized_vol_pct(candles: list[Candle]) -> float:
    returns: list[float] = []
    prev = None
    for c in candles:
        if prev and prev > 0 and c.close > 0:
            returns.append(c.close / prev - 1.0)
        prev = c.close
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    # 1m candles: 365 * 24 * 60 samples/year.
    return sqrt(var) * sqrt(365 * 24 * 60) * 100.0


def _volume_ratio(candles: list[Candle]) -> float:
    if len(candles) < 20:
        return 1.0
    split = max(1, len(candles) // 5)
    recent = candles[-split:]
    base = candles[:-split]
    base_avg = sum(c.volume for c in base) / max(1, len(base))
    recent_avg = sum(c.volume for c in recent) / max(1, len(recent))
    return recent_avg / base_avg if base_avg > 0 else 0.0
