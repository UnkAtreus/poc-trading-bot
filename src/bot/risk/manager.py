"""Risk gatekeeper. Synchronous checks before every PlaceEntry."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from bot.config import Settings, Mode
from bot.logger import get_logger

log = get_logger(__name__)


@dataclass
class _SymbolRiskState:
    consecutive_losses: int = 0
    cooldown_until_ts: float = 0.0
    open_notional: float = 0.0


@dataclass
class RiskManager:
    settings: Settings
    state_dir: Path = Path("data/state")
    # Clock function: returns "now" in unix seconds. Defaults to wall-clock; the
    # backtest runner injects a sim-time clock so cooldowns + daily-rolls are
    # measured in simulation time, not real time.
    clock: Callable[[], float] = time.time
    _symbols: dict[str, _SymbolRiskState] = field(default_factory=dict)
    _account_open_notional: float = 0.0
    _daily_pnl: float = 0.0
    _daily_anchor_utc_date: str = ""

    def __post_init__(self):
        self._daily_anchor_utc_date = datetime.fromtimestamp(self.clock(), tz=timezone.utc).strftime("%Y-%m-%d")

    # ---- public API ----

    def assert_can_start(self) -> None:
        """Enforce mainnet-confirm and kill-switch on startup."""
        if self.settings.env.mode is Mode.MAINNET:
            if self.settings.env.mainnet_confirm != "YES_I_MEAN_IT":
                raise RuntimeError("MAINNET_CONFIRM=YES_I_MEAN_IT required for mainnet")
        if self.kill_active():
            raise RuntimeError("kill switch active (KILL file or BOT_KILL=1)")

    def kill_active(self) -> bool:
        if self.settings.env.kill_active:
            return True
        return (self.state_dir / "KILL").exists()

    def check_can_place_entry(self, symbol: str, notional: float) -> tuple[bool, str | None]:
        """Returns (allowed, reason_if_blocked)."""
        if self.kill_active():
            return False, "kill_switch"
        self._roll_daily()
        if self._daily_pnl <= -self.settings.bot.risk.daily_loss_limit_usd:
            return False, "daily_loss_limit"
        st = self._sym(symbol)
        now = self.clock()
        if now < st.cooldown_until_ts:
            return False, f"cooldown({int(st.cooldown_until_ts - now)}s)"
        per_sym_cap = self.settings.per_symbol_max_notional(symbol)
        if st.open_notional + notional > per_sym_cap:
            return False, f"per_symbol_cap({per_sym_cap})"
        if self._account_open_notional + notional > self.settings.bot.risk.max_notional_account_usd:
            return False, "account_cap"
        return True, None

    def on_entry_placed(self, symbol: str, notional: float) -> None:
        st = self._sym(symbol)
        st.open_notional += notional
        self._account_open_notional += notional

    def on_entry_cancelled(self, symbol: str, notional: float) -> None:
        st = self._sym(symbol)
        st.open_notional = max(0.0, st.open_notional - notional)
        self._account_open_notional = max(0.0, self._account_open_notional - notional)

    def sync_open_notional(self, symbol: str, notional: float) -> None:
        """Adopt authoritative exchange exposure for a symbol after reconcile."""
        st = self._sym(symbol)
        notional = max(0.0, notional)
        delta = notional - st.open_notional
        st.open_notional = notional
        self._account_open_notional = max(0.0, self._account_open_notional + delta)

    def on_trade_closed(self, symbol: str, pnl: float, notional_closed: float) -> None:
        """Update consecutive losses, cooldown, daily PnL, exposure."""
        st = self._sym(symbol)
        st.open_notional = max(0.0, st.open_notional - notional_closed)
        self._account_open_notional = max(0.0, self._account_open_notional - notional_closed)
        self._roll_daily()
        self._daily_pnl += pnl
        if pnl >= 0:
            st.consecutive_losses = 0
        else:
            st.consecutive_losses += 1
            if st.consecutive_losses >= self.settings.bot.risk.max_consecutive_losses:
                st.cooldown_until_ts = self.clock() + self.settings.bot.risk.cooldown_minutes * 60
                log.warning(
                    "risk.cooldown_triggered", symbol=symbol,
                    losses=st.consecutive_losses, minutes=self.settings.bot.risk.cooldown_minutes,
                )

    # ---- internals ----

    def _sym(self, symbol: str) -> _SymbolRiskState:
        if symbol not in self._symbols:
            self._symbols[symbol] = _SymbolRiskState()
        return self._symbols[symbol]

    def _roll_daily(self) -> None:
        today = datetime.fromtimestamp(self.clock(), tz=timezone.utc).strftime("%Y-%m-%d")
        if today != self._daily_anchor_utc_date:
            self._daily_anchor_utc_date = today
            self._daily_pnl = 0.0
