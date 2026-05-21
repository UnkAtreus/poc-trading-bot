"""Execution realism knobs for candle-based backtests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


ExecutionMode = Literal["naive", "realistic"]
ExecutionProfile = Literal["conservative", "mainnet-like"]

CONSERVATIVE_LATENCIES = "1,3,5"
MAINNET_LIKE_LATENCIES = "0.15,0.3,0.5"

EXECUTION_PROFILE_DEFAULTS: dict[ExecutionProfile, dict[str, float]] = {
    "conservative": {
        "latency_seconds": 1.0,
        "cancel_delay_seconds": 3.0,
        "slippage_bps": 2.0,
        "pass_through_bps": 1.0,
        "full_fill_bps": 5.0,
        "min_partial_fill_pct": 25.0,
    },
    # Based on local Bybit mainnet public checks from this machine:
    # REST keep-alive median ~40ms, p90 ~100ms; WS first data after subscribe
    # median ~35ms once IPv4 is preferred. These defaults add buffer for
    # private order POST/ack, local scheduling, and short jitter bursts.
    "mainnet-like": {
        "latency_seconds": 0.30,
        "cancel_delay_seconds": 0.50,
        "slippage_bps": 1.0,
        "pass_through_bps": 0.2,
        "full_fill_bps": 1.0,
        "min_partial_fill_pct": 50.0,
    },
}

EXECUTION_PROFILE_LATENCIES: dict[ExecutionProfile, str] = {
    "conservative": CONSERVATIVE_LATENCIES,
    "mainnet-like": MAINNET_LIKE_LATENCIES,
}


@dataclass(frozen=True)
class BacktestExecutionConfig:
    """Controls how the simulator turns candle prices into order fills."""

    mode: ExecutionMode = "naive"
    latency_seconds: float = 0.0
    cancel_delay_seconds: float = 0.0
    slippage_bps: float = 0.0
    pass_through_bps: float = 0.0
    full_fill_bps: float = 0.0
    min_partial_fill_pct: float = 100.0

    @classmethod
    def naive(cls) -> "BacktestExecutionConfig":
        return cls()

    @classmethod
    def realistic(
        cls,
        *,
        latency_seconds: float = 1.0,
        cancel_delay_seconds: float = 3.0,
        slippage_bps: float = 2.0,
        pass_through_bps: float = 1.0,
        full_fill_bps: float = 5.0,
        min_partial_fill_pct: float = 25.0,
    ) -> "BacktestExecutionConfig":
        return cls(
            mode="realistic",
            latency_seconds=latency_seconds,
            cancel_delay_seconds=cancel_delay_seconds,
            slippage_bps=slippage_bps,
            pass_through_bps=pass_through_bps,
            full_fill_bps=full_fill_bps,
            min_partial_fill_pct=min_partial_fill_pct,
        )

    @classmethod
    def from_profile(
        cls,
        profile: ExecutionProfile,
        *,
        latency_seconds: float | None = None,
        cancel_delay_seconds: float | None = None,
        slippage_bps: float | None = None,
        pass_through_bps: float | None = None,
        full_fill_bps: float | None = None,
        min_partial_fill_pct: float | None = None,
    ) -> "BacktestExecutionConfig":
        defaults = EXECUTION_PROFILE_DEFAULTS[profile]
        return cls.realistic(
            latency_seconds=defaults["latency_seconds"]
            if latency_seconds is None
            else latency_seconds,
            cancel_delay_seconds=defaults["cancel_delay_seconds"]
            if cancel_delay_seconds is None
            else cancel_delay_seconds,
            slippage_bps=defaults["slippage_bps"] if slippage_bps is None else slippage_bps,
            pass_through_bps=defaults["pass_through_bps"]
            if pass_through_bps is None
            else pass_through_bps,
            full_fill_bps=defaults["full_fill_bps"] if full_fill_bps is None else full_fill_bps,
            min_partial_fill_pct=defaults["min_partial_fill_pct"]
            if min_partial_fill_pct is None
            else min_partial_fill_pct,
        )

    def __post_init__(self) -> None:
        if self.mode not in ("naive", "realistic"):
            raise ValueError(f"unsupported execution mode: {self.mode}")
        if self.latency_seconds < 0:
            raise ValueError("latency_seconds must be >= 0")
        if self.cancel_delay_seconds < 0:
            raise ValueError("cancel_delay_seconds must be >= 0")
        if self.slippage_bps < 0:
            raise ValueError("slippage_bps must be >= 0")
        if self.pass_through_bps < 0:
            raise ValueError("pass_through_bps must be >= 0")
        if self.full_fill_bps < self.pass_through_bps:
            raise ValueError("full_fill_bps must be >= pass_through_bps")
        if not 0 < self.min_partial_fill_pct <= 100:
            raise ValueError("min_partial_fill_pct must be in (0, 100]")

    @property
    def is_realistic(self) -> bool:
        return self.mode == "realistic"


@dataclass
class ExecutionStats:
    placed_orders: int = 0
    accepted_orders: int = 0
    rejected_orders: int = 0
    rejected_by_reason: dict[str, int] = field(default_factory=dict)
    full_fills: int = 0
    partial_fills: int = 0
    cancel_requested: int = 0
    cancel_effective: int = 0
    cancel_race_fills: int = 0
    dust_rejected: int = 0
    slippage_cost: float = 0.0

    def record_rejection(self, reason: str | None) -> None:
        self.rejected_orders += 1
        key = reason or "unknown"
        self.rejected_by_reason[key] = self.rejected_by_reason.get(key, 0) + 1
        if key.startswith(("qty_below_min", "notional_below_min")):
            self.dust_rejected += 1
