"""Combine two signal engines."""

from __future__ import annotations

from bot.models import Candle, Signal
from bot.signals.base import SignalEngine, register


@register("dual_signal")
class DualSignal(SignalEngine):
    def __init__(
        self,
        left: str,
        right: str,
        mode: str = "agree",
        conflict: str = "none",
        **kwargs,
    ):
        from bot.signals.base import build  # avoid cycle at import time

        if mode not in {"agree", "either"}:
            raise ValueError("mode must be 'agree' or 'either'")
        if conflict not in {"none", "left", "right"}:
            raise ValueError("conflict must be 'none', 'left', or 'right'")
        self.mode = mode
        self.conflict = conflict
        left_params = {
            k[len("left_"):]: v
            for k, v in kwargs.items()
            if k.startswith("left_")
        }
        right_params = {
            k[len("right_"):]: v
            for k, v in kwargs.items()
            if k.startswith("right_")
        }
        self._left = build(left, left_params)
        self._right = build(right, right_params)

    def warmup_bars(self) -> int:
        return max(self._left.warmup_bars(), self._right.warmup_bars())

    def on_candle(self, candle: Candle) -> Signal | None:
        left_sig = self._left.on_candle(candle)
        right_sig = self._right.on_candle(candle)

        if self.mode == "agree":
            if (
                left_sig is not None
                and right_sig is not None
                and left_sig.direction is right_sig.direction
            ):
                return left_sig
            return None

        if left_sig is None:
            return right_sig
        if right_sig is None:
            return left_sig
        if left_sig.direction is right_sig.direction:
            return left_sig
        if self.conflict == "left":
            return left_sig
        if self.conflict == "right":
            return right_sig
        return None
