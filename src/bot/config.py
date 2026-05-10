from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Mode(str, Enum):
    BACKTEST = "backtest"
    TESTNET = "testnet"
    MAINNET = "mainnet"


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    bybit_api_key: str = ""
    bybit_api_secret: str = ""
    mode: Mode = Mode.TESTNET
    mainnet_confirm: str = ""
    log_level: str = "INFO"
    bot_kill: str = ""

    @property
    def kill_active(self) -> bool:
        return self.bot_kill.strip() == "1"

    @model_validator(mode="after")
    def _enforce_mainnet_confirm(self) -> "EnvSettings":
        if self.mode is Mode.MAINNET and self.mainnet_confirm != "YES_I_MEAN_IT":
            raise ValueError(
                "MODE=mainnet requires MAINNET_CONFIRM=YES_I_MEAN_IT in env"
            )
        return self


class Sizing(BaseModel, extra="forbid"):
    margin_usd: float = Field(gt=0)
    leverage: int = Field(ge=1, le=100)

    @property
    def notional_usd(self) -> float:
        return self.margin_usd * self.leverage


class Offsets(BaseModel, extra="forbid"):
    entry_offset_bps: float = Field(ge=0)
    tp_offset_bps: float = Field(gt=0)


class MergeTimer(BaseModel, extra="forbid"):
    seconds: int = Field(gt=0)
    policy: Literal["first_fill"] = "first_fill"


class Fees(BaseModel, extra="forbid"):
    maker_bps: float
    taker_bps: float


class RiskConfig(BaseModel, extra="forbid"):
    max_notional_per_symbol_usd: float = Field(gt=0)
    max_notional_account_usd: float = Field(gt=0)
    max_consecutive_losses: int = Field(ge=1)
    cooldown_minutes: int = Field(ge=0)
    daily_loss_limit_usd: float = Field(gt=0)


class AccountConfig(BaseModel, extra="forbid"):
    initial_equity: float = Field(default=30_000.0, gt=0)
    margin_mode: Literal["cross", "isolated"] = "cross"


class LiquidationConfig(BaseModel, extra="forbid"):
    enabled: bool = True
    maintenance_margin_rate: float = Field(default=0.005, ge=0, lt=1)
    near_liq_buffer_pct: float = Field(default=10.0, ge=0)
    taker_exit_bps: float | None = Field(default=None, ge=0)
    funding_stress_bps: float = Field(default=0.0, ge=0)


class OptimizerSafetyGates(BaseModel, extra="forbid"):
    reject_liquidated: bool = True
    reject_near_liquidation: bool = True
    max_drawdown_pct: float | None = Field(default=None, gt=0)
    max_final_open_exposure_usd: float | None = Field(default=None, ge=0)


class OptimizerConfig(BaseModel, extra="forbid"):
    safety_gates: OptimizerSafetyGates = Field(default_factory=OptimizerSafetyGates)


class RegimeRouterConfig(BaseModel, extra="forbid"):
    enabled: bool = False
    no_trade_on_unsafe: bool = True


class SignalConfig(BaseModel, extra="forbid"):
    engine: str
    params: dict[str, float | int | str | bool] = Field(default_factory=dict)


class LoopConfig(BaseModel, extra="forbid"):
    reconcile_every_seconds: int = Field(gt=0)


class BotConfig(BaseModel, extra="forbid"):
    sizing: Sizing
    offsets: Offsets
    merge_timer: MergeTimer
    fees: Fees
    risk: RiskConfig
    account: AccountConfig = Field(default_factory=AccountConfig)
    liquidation: LiquidationConfig = Field(default_factory=LiquidationConfig)
    optimizer: OptimizerConfig = Field(default_factory=OptimizerConfig)
    regime_router: RegimeRouterConfig = Field(default_factory=RegimeRouterConfig)
    signal: SignalConfig
    loop: LoopConfig


class SymbolOverride(BaseModel, extra="forbid"):
    max_notional_per_symbol_usd: float | None = Field(default=None, gt=0)


class SymbolsConfig(BaseModel, extra="forbid"):
    active: list[str]
    overrides: dict[str, SymbolOverride] = Field(default_factory=dict)


class Settings(BaseModel):
    env: EnvSettings
    bot: BotConfig
    symbols: SymbolsConfig

    def per_symbol_max_notional(self, symbol: str) -> float:
        ov = self.symbols.overrides.get(symbol)
        if ov and ov.max_notional_per_symbol_usd is not None:
            return ov.max_notional_per_symbol_usd
        return self.bot.risk.max_notional_per_symbol_usd


def _load_yaml(path: Path) -> dict:
    with path.open("r") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected mapping at top level")
    return data


def load_settings(
    config_dir: str | Path = "config",
    env_file: str | Path | None = None,
) -> Settings:
    cdir = Path(config_dir)
    bot_yaml = _load_yaml(cdir / "bot.yaml")
    sym_yaml = _load_yaml(cdir / "symbols.yaml")
    if env_file is not None:
        env = EnvSettings(_env_file=str(env_file))  # type: ignore[call-arg]
    else:
        env = EnvSettings()
    return Settings(
        env=env,
        bot=BotConfig.model_validate(bot_yaml),
        symbols=SymbolsConfig.model_validate(sym_yaml),
    )
