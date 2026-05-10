"""Synthetic stress scenarios for candle-based liquidation backtests."""

from __future__ import annotations

from dataclasses import dataclass

from bot.models import Candle


@dataclass(frozen=True)
class StressScenario:
    name: str
    candles_by_symbol: dict[str, list[Candle]]
    funding_stress_bps: float = 0.0


def build_stress_scenarios(
    candles_by_symbol: dict[str, list[Candle]],
    *,
    shocks: tuple[float, ...] = (-20.0, -40.0, -60.0, -80.0),
    names: tuple[str, ...] = ("instant", "slow_grind", "v_shape", "wick", "liquidity_shock", "missing_candles"),
) -> list[StressScenario]:
    scenarios = [StressScenario("historical", clone_candles(candles_by_symbol))]
    if "instant" in names:
        for shock in shocks:
            scenarios.append(StressScenario(
                f"instant_{shock:+.0f}pct",
                append_instant_shock(candles_by_symbol, shock),
            ))
    if "slow_grind" in names:
        scenarios.append(StressScenario(
            "slow_grind_-40pct",
            append_slow_grind(candles_by_symbol, -40.0, bars=60),
        ))
    if "v_shape" in names:
        scenarios.append(StressScenario(
            "v_shape_-40pct",
            append_v_shape(candles_by_symbol, -40.0, bars_each_side=30),
        ))
    if "wick" in names:
        scenarios.append(StressScenario(
            "exchange_wick_-60pct",
            append_wick(candles_by_symbol, -60.0),
        ))
    if "liquidity_shock" in names:
        scenarios.append(StressScenario(
            "liquidity_shock_wide_range_funding",
            widen_recent_ranges(candles_by_symbol, range_mult=4.0, volume_mult=0.10),
            funding_stress_bps=50.0,
        ))
    if "missing_candles" in names:
        scenarios.append(StressScenario(
            "missing_candles_every_7th",
            drop_every_nth_candle(candles_by_symbol, 7),
        ))
    return scenarios


def clone_candles(candles_by_symbol: dict[str, list[Candle]]) -> dict[str, list[Candle]]:
    return {sym: list(rows) for sym, rows in candles_by_symbol.items()}


def append_instant_shock(candles_by_symbol: dict[str, list[Candle]], shock_pct: float) -> dict[str, list[Candle]]:
    out = clone_candles(candles_by_symbol)
    for sym, rows in out.items():
        if not rows:
            continue
        rows.append(_next_candle_from_close(rows[-1], shock_pct, bars_after=1))
    return out


def append_slow_grind(
    candles_by_symbol: dict[str, list[Candle]],
    shock_pct: float,
    *,
    bars: int,
) -> dict[str, list[Candle]]:
    out = clone_candles(candles_by_symbol)
    bars = max(1, bars)
    for sym, rows in out.items():
        if not rows:
            continue
        start_close = rows[-1].close
        target = start_close * max(0.01, 1.0 + shock_pct / 100.0)
        prev = rows[-1]
        for i in range(1, bars + 1):
            close = start_close + (target - start_close) * (i / bars)
            rows.append(_make_continuation(prev, close, volume_mult=1.25))
            prev = rows[-1]
    return out


def append_v_shape(
    candles_by_symbol: dict[str, list[Candle]],
    shock_pct: float,
    *,
    bars_each_side: int,
) -> dict[str, list[Candle]]:
    out = append_slow_grind(candles_by_symbol, shock_pct, bars=bars_each_side)
    bars_each_side = max(1, bars_each_side)
    for sym, rows in out.items():
        if not rows:
            continue
        trough = rows[-1].close
        target = candles_by_symbol[sym][-1].close
        prev = rows[-1]
        for i in range(1, bars_each_side + 1):
            close = trough + (target - trough) * (i / bars_each_side)
            rows.append(_make_continuation(prev, close, volume_mult=1.75))
            prev = rows[-1]
    return out


def append_wick(candles_by_symbol: dict[str, list[Candle]], wick_pct: float) -> dict[str, list[Candle]]:
    out = clone_candles(candles_by_symbol)
    for sym, rows in out.items():
        if not rows:
            continue
        last = rows[-1]
        wick = last.close * max(0.01, 1.0 + wick_pct / 100.0)
        low = min(last.close, wick)
        high = max(last.close, wick)
        rows.append(Candle(
            symbol=sym,
            timestamp=last.timestamp + 60.0,
            open=last.close,
            high=high,
            low=low,
            close=last.close,
            volume=last.volume * 2.0,
            confirm=True,
        ))
    return out


def widen_recent_ranges(
    candles_by_symbol: dict[str, list[Candle]],
    *,
    range_mult: float,
    volume_mult: float,
    tail_bars: int = 60,
) -> dict[str, list[Candle]]:
    out = clone_candles(candles_by_symbol)
    for sym, rows in out.items():
        if not rows:
            continue
        start = max(0, len(rows) - tail_bars)
        widened = rows[:start]
        for c in rows[start:]:
            width_high = max(0.0, c.high - c.close) * range_mult
            width_low = max(0.0, c.close - c.low) * range_mult
            widened.append(Candle(
                symbol=c.symbol,
                timestamp=c.timestamp,
                open=c.open,
                high=max(c.open, c.close + width_high),
                low=max(0.01, min(c.open, c.close - width_low)),
                close=c.close,
                volume=c.volume * volume_mult,
                confirm=c.confirm,
            ))
        out[sym] = widened
    return out


def drop_every_nth_candle(candles_by_symbol: dict[str, list[Candle]], n: int) -> dict[str, list[Candle]]:
    n = max(2, n)
    return {
        sym: [c for i, c in enumerate(rows, start=1) if i % n != 0]
        for sym, rows in candles_by_symbol.items()
    }


def _next_candle_from_close(last: Candle, move_pct: float, *, bars_after: int) -> Candle:
    mult = max(0.01, 1.0 + move_pct / 100.0)
    close = last.close * mult
    low = min(last.close, close)
    high = max(last.close, close)
    return Candle(
        symbol=last.symbol,
        timestamp=last.timestamp + 60.0 * bars_after,
        open=last.close,
        high=high,
        low=low,
        close=close,
        volume=last.volume,
        confirm=True,
    )


def _make_continuation(prev: Candle, close: float, *, volume_mult: float) -> Candle:
    low = min(prev.close, close)
    high = max(prev.close, close)
    return Candle(
        symbol=prev.symbol,
        timestamp=prev.timestamp + 60.0,
        open=prev.close,
        high=high,
        low=max(0.01, low),
        close=max(0.01, close),
        volume=prev.volume * volume_mult,
        confirm=True,
    )
