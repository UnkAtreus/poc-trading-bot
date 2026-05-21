"""Market-regime gate for grid-style signals.

The gate wraps another SignalEngine and measures whether the broader market is
trending too hard for passive grid entries. When unsafe, it can either suppress
new signals or pass them through with a reduced order size.
"""

from __future__ import annotations

from collections import deque
from dataclasses import replace

from bot.models import Candle, Signal
from bot.signals.base import SignalEngine, register


class _RegimeState:
    __slots__ = (
        "adx",
        "bars",
        "dx_values",
        "ema_fast",
        "ema_slow",
        "minus_dm_values",
        "plus_dm_values",
        "prev_close",
        "prev_high",
        "prev_low",
        "tr_values",
    )

    def __init__(self, adx_period: int):
        self.bars = 0
        self.ema_fast: float | None = None
        self.ema_slow: float | None = None
        self.prev_high: float | None = None
        self.prev_low: float | None = None
        self.prev_close: float | None = None
        self.tr_values: deque[float] = deque(maxlen=adx_period)
        self.plus_dm_values: deque[float] = deque(maxlen=adx_period)
        self.minus_dm_values: deque[float] = deque(maxlen=adx_period)
        self.dx_values: deque[float] = deque(maxlen=adx_period)
        self.adx: float | None = None


@register("regime_gate")
class RegimeGate(SignalEngine):
    def __init__(
        self,
        inner: str = "trend_filter",
        scope: str = "benchmark",
        benchmark_symbol: str = "BTCUSDT",
        ema_fast: int = 60,
        ema_slow: int = 240,
        max_ema_spread_bps: float = 25.0,
        use_ema_spread: bool = True,
        adx_period: int = 60,
        max_adx: float = 25.0,
        use_adx: bool = True,
        unsafe_action: str = "pause",
        unsafe_size_scale: float = 0.5,
        **inner_kwargs,
    ):
        from bot.signals.base import build  # avoid cycle at import time

        if scope not in {"benchmark", "symbol"}:
            raise ValueError("scope must be 'benchmark' or 'symbol'")
        if ema_fast < 1 or ema_slow < 1 or ema_fast >= ema_slow:
            raise ValueError("require ema_fast >= 1 and ema_fast < ema_slow")
        if max_ema_spread_bps <= 0:
            raise ValueError("max_ema_spread_bps must be > 0")
        if adx_period < 2:
            raise ValueError("adx_period must be >= 2")
        if max_adx <= 0:
            raise ValueError("max_adx must be > 0")
        if unsafe_action not in {"pause", "reduce", "block_new"}:
            raise ValueError("unsafe_action must be 'pause', 'reduce', or 'block_new'")
        if not (0 < unsafe_size_scale <= 1):
            raise ValueError("unsafe_size_scale must be > 0 and <= 1")

        self.scope = scope
        self.benchmark_symbol = benchmark_symbol
        self.ema_fast_period = ema_fast
        self.ema_slow_period = ema_slow
        self.max_ema_spread_bps = max_ema_spread_bps
        self.use_ema_spread = use_ema_spread
        self.adx_period = adx_period
        self.max_adx = max_adx
        self.use_adx = use_adx
        self.unsafe_action = unsafe_action
        self.unsafe_size_scale = unsafe_size_scale
        self._alpha_fast = 2.0 / (ema_fast + 1)
        self._alpha_slow = 2.0 / (ema_slow + 1)
        self._states: dict[str, _RegimeState] = {}

        inner_params: dict = {}
        for key, value in inner_kwargs.items():
            if key.startswith("inner_"):
                inner_params[key[len("inner_"):]] = value
        self._inner = build(inner, inner_params)

    def warmup_bars(self) -> int:
        regime_bars = max(self.ema_slow_period + 1, self.adx_period * 2 + 1)
        return max(regime_bars, self._inner.warmup_bars())

    def on_candle(self, candle: Candle) -> Signal | None:
        update_symbol = candle.symbol if self.scope == "symbol" else self.benchmark_symbol
        if self.scope == "symbol" or candle.symbol == self.benchmark_symbol:
            self._update(update_symbol, candle)

        # Always feed the inner engine so its state stays aligned even when the
        # market gate suppresses or shrinks a signal.
        sig = self._inner.on_candle(candle)
        if sig is None:
            return None

        state = self._states.get(candle.symbol if self.scope == "symbol" else self.benchmark_symbol)
        if state is None or not self._unsafe(state):
            return sig
        if self.unsafe_action == "pause":
            return None
        if self.unsafe_action == "block_new":
            return replace(sig, allow_new_position=False)
        return replace(sig, size_scale=sig.size_scale * self.unsafe_size_scale)

    def _update(self, symbol: str, candle: Candle) -> None:
        state = self._states.setdefault(symbol, _RegimeState(self.adx_period))
        state.bars += 1
        if state.ema_fast is None:
            state.ema_fast = candle.close
            state.ema_slow = candle.close
        else:
            state.ema_fast = self._alpha_fast * candle.close + (1 - self._alpha_fast) * state.ema_fast
            assert state.ema_slow is not None
            state.ema_slow = self._alpha_slow * candle.close + (1 - self._alpha_slow) * state.ema_slow

        if state.prev_close is not None and state.prev_high is not None and state.prev_low is not None:
            tr = max(
                candle.high - candle.low,
                abs(candle.high - state.prev_close),
                abs(candle.low - state.prev_close),
            )
            up_move = candle.high - state.prev_high
            down_move = state.prev_low - candle.low
            plus_dm = up_move if up_move > down_move and up_move > 0 else 0.0
            minus_dm = down_move if down_move > up_move and down_move > 0 else 0.0
            state.tr_values.append(tr)
            state.plus_dm_values.append(plus_dm)
            state.minus_dm_values.append(minus_dm)
            self._update_adx(state)

        state.prev_high = candle.high
        state.prev_low = candle.low
        state.prev_close = candle.close

    def _update_adx(self, state: _RegimeState) -> None:
        if len(state.tr_values) < self.adx_period:
            return
        tr_sum = sum(state.tr_values)
        if tr_sum <= 0:
            return
        plus_di = 100.0 * sum(state.plus_dm_values) / tr_sum
        minus_di = 100.0 * sum(state.minus_dm_values) / tr_sum
        di_sum = plus_di + minus_di
        if di_sum <= 0:
            return
        dx = 100.0 * abs(plus_di - minus_di) / di_sum
        state.dx_values.append(dx)
        if len(state.dx_values) == self.adx_period:
            state.adx = sum(state.dx_values) / len(state.dx_values)

    def _unsafe(self, state: _RegimeState) -> bool:
        if (
            self.use_ema_spread
            and state.bars >= self.ema_slow_period
            and state.ema_fast is not None
            and state.ema_slow
        ):
            spread_bps = abs(state.ema_fast - state.ema_slow) / state.ema_slow * 10_000.0
            if spread_bps > self.max_ema_spread_bps:
                return True
        if self.use_adx and state.adx is not None and state.adx > self.max_adx:
            return True
        return False
