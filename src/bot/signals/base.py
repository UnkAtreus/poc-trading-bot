from __future__ import annotations

from abc import ABC, abstractmethod

from bot.models import Candle, Signal


class SignalEngine(ABC):
    """Pluggable signal engine. One instance is shared across all symbols;
    per-symbol state lives inside the engine, keyed by symbol."""

    @abstractmethod
    def warmup_bars(self) -> int:
        """How many candles to buffer before emitting any signal."""

    @abstractmethod
    def on_candle(self, candle: Candle) -> Signal | None:
        """Called once per closed 1m candle per symbol. Returns a Signal or None."""


# Registry for engine names referenced from bot.yaml.
_REGISTRY: dict[str, type[SignalEngine]] = {}


def register(name: str):
    def deco(cls: type[SignalEngine]) -> type[SignalEngine]:
        if name in _REGISTRY:
            raise ValueError(f"signal engine '{name}' already registered")
        _REGISTRY[name] = cls
        return cls
    return deco


def build(name: str, params: dict) -> SignalEngine:
    if name not in _REGISTRY:
        # Trigger plugin imports so @register decorators run.
        import bot.signals.bollinger  # noqa: F401
        import bot.signals.crash_guard  # noqa: F401
        import bot.signals.dual_signal  # noqa: F401
        import bot.signals.ema_cross  # noqa: F401
        import bot.signals.grid  # noqa: F401
        import bot.signals.placeholder_rsi  # noqa: F401
        import bot.signals.random_signal  # noqa: F401
        import bot.signals.trend_filter  # noqa: F401
        import bot.signals.zscore  # noqa: F401
    if name not in _REGISTRY:
        raise ValueError(f"unknown signal engine '{name}'")
    return _REGISTRY[name](**params)


def list_engines() -> list[str]:
    """Trigger plugin imports and return all registered engine names."""
    # Force plugin imports.
    build.__wrapped__ = None  # type: ignore[attr-defined]
    try:
        build("__nonexistent__", {})
    except ValueError:
        pass
    return sorted(_REGISTRY.keys())
