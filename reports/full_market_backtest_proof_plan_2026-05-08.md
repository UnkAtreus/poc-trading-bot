# Full Market Backtest Proof Plan

Date: `2026-05-08`

Goal: build proof before real money. The bot must first pass liquidation safety, then stable monthly profit checks. If a market type has no safe strategy, the correct output is `no_trade`.

## Important Truth

No leveraged trading bot can be proven `100% safe` against every real-world event. Bybit states that USDT perpetual liquidation depends on mark price, maintenance margin, leverage, position size, margin used, available balance, and risk tiers. Bybit also notes that liquidation risk increases in high volatility and cannot be completely avoided.

Official references:

- Bybit USDT liquidation price: https://www.bybit.com/en/help-center/article/Liquidation-Price-USDT-Contract
- Bybit USDT maintenance margin: https://www.bybit.com/fr-FR/help-center/article/Maintenance-Margin-USDT-Contract
- Bybit USDT perpetual FAQ: https://www.bybit.com/en/help-center/article/FAQ-USDT-Perpetual-and-Expiry-Contracts

So the proof target is:

```text
No liquidation and no near-liquidation under historical data,
synthetic crash scenarios, stress scenarios, and walk-forward validation.
```

If this proof fails, do not launch on real market.

## What Is Already Implemented

The repo now has the foundation needed to prove safety and monthly stability:

- Liquidation/account-risk metrics in backtest results:
  - `liquidated`
  - `near_liquidation`
  - `min_liq_distance_pct`
  - `margin_ratio_max`
  - `worst_unrealized_loss`
  - `time_in_recovery`
  - `final_open_exposure`
  - `max_initial_margin`
  - `min_available_balance`
- Synthetic stress scenarios:
  - historical
  - instant crash
  - slow grind crash
  - V-shape crash/rebound
  - exchange wick
  - liquidity shock with funding stress
  - missing candles
- Market regime classifier:
  - `sideways`
  - `uptrend`
  - `downtrend`
  - `crash`
  - `high_volatility`
  - `low_liquidity`
- Lot-size optimizer:
  - ranks by liquidation safety first
  - rejects unsafe candidates before profit ranking
- Monthly stability optimizer:
  - positive month percentage
  - target ROI month percentage
  - average monthly ROI
  - median monthly ROI
  - worst monthly ROI
  - worst monthly drawdown
  - longest zero/non-positive month stretch

Verification already run:

```text
uv run pytest tests/unit -q
84 passed
```

## Proof Gates

A candidate is rejected immediately if any of these are true:

```text
liquidated = true
near_liquidation = true
max_drawdown_pct > 25%
final_open_exposure > 5,000 USDT
```

After safety passes, stable monthly profit is checked:

```text
positive_month_pct >= 70%
target_month_pct >= 50%
target_monthly_roi_pct >= 0.5%
longest_non_positive_stretch <= 2 months
worst_monthly_dd_pct <= 10%
```

Later, after a safe candidate exists, test a harder monthly target:

```text
target_monthly_roi_pct = 1.0%
```

## Market Types and Strategy Selection

The framework should not force one bot to trade every market. It should select a strategy by market type:

| Market type | First strategy candidates | Allowed result |
|---|---|---|
| Sideways | grid, Bollinger, z-score, trend-filtered grid | trade if safe |
| Uptrend | trend-following or reduced mean-reversion | trade only if safety passes |
| Downtrend | short-capable strategy or no-trade | trade/no_trade |
| Crash | crash guard, emergency no-long mode, no-trade | usually no_trade |
| High volatility | low-cap grid or no-trade | trade/no_trade |
| Low liquidity | no-trade | no_trade |

The selector must prefer `no_trade` over unsafe profit.

## Backtest Matrix

Use account equity:

```text
initial_equity = 30,000 USDT
```

Core symbols:

```text
BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT
```

Extended symbols after core passes:

```text
HYPEUSDT,XAUTUSDT
```

Parameter sweep:

```text
margin_usd: 10,20,30,50,66,80,100
leverage: 3,5,10
account_cap: 5,000,7,500,10,000,12,500,15,000,20,000
symbol_cap: 500,1,000,1,500,2,000,3,000,4,000
tp_offset_bps: 30,50,75,100
```

Safety controls to test:

```text
stop_account_dd_pct: 5,8,10,15
stop_monthly_dd_pct: 5,8,10
stop_monthly_profit_lock_pct: 0.5,1.0,1.5
stop_max_hold_hours: 168,336,720
```

## Commands

Classify current/historical market:

```bash
uv run python -m bot.main classify-market \
  --start 2026-04-01 \
  --end 2026-05-08 \
  --symbols BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT
```

Run liquidation stress proof:

```bash
uv run python -m bot.main stress \
  --start 2024-01-01 \
  --end 2026-05-01 \
  --symbols BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT \
  --shocks -20,-40,-60,-80 \
  --with-risk
```

Find safest lot size:

```bash
uv run python -m bot.main optimize-lot-size \
  --start 2024-01-01 \
  --end 2026-05-01 \
  --symbols BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT \
  --margins 10,20,30,50,66,80,100 \
  --leverages 3,5,10 \
  --account-caps 5000,7500,10000,12500,15000,20000 \
  --symbol-caps 500,1000,1500,2000,3000,4000 \
  --with-risk
```

Find stable monthly setup after safety:

```bash
uv run python -m bot.main optimize-stability \
  --start 2024-01-01 \
  --end 2026-05-01 \
  --symbols BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT \
  --margins 10,20,30,50,66,80,100 \
  --leverages 3,5,10 \
  --account-caps 5000,7500,10000,12500,15000,20000 \
  --symbol-caps 500,1000,1500,2000,3000,4000 \
  --tp-offsets 30,50,75,100 \
  --target-monthly-roi-pct 0.5 \
  --min-positive-month-pct 70 \
  --min-target-month-pct 50 \
  --max-non-positive-stretch 2 \
  --max-worst-monthly-dd-pct 10 \
  --with-risk
```

Select strategy for current market:

```bash
uv run python -m bot.main select-strategy \
  --start 2026-04-01 \
  --end 2026-05-08 \
  --symbols BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT \
  --signals 'trend_filter:inner=grid:inner_anchor_period=200:inner_entry_bps=30:inner_step_bps=15:max_trend_bps=30,crash_guard:inner=trend_filter:inner_inner=grid:inner_inner_anchor_period=200:inner_inner_entry_bps=30:inner_inner_step_bps=15:inner_max_trend_bps=30' \
  --with-risk
```

## Report Outputs Required Before Real Money

Before launch, produce these files:

```text
reports/01_market_regime_report.md
reports/02_liquidation_stress_report.md
reports/03_best_lot_size_report.md
reports/04_monthly_stability_report.md
reports/05_strategy_selector_report.md
reports/06_real_money_launch_gate.md
```

Each report must include:

- exact command run
- date range
- symbols
- strategy config
- safety pass/fail
- best lot size
- max drawdown
- liquidation/near-liquidation status
- monthly stability metrics
- final decision: `trade`, `reduce_size`, or `no_trade`

## Launch Gate

Real money is allowed only if all are true:

```text
unit tests pass
historical stress passes
synthetic stress passes
no liquidation
no near-liquidation
max drawdown <= 25%
worst monthly DD <= 10%
positive months >= 70%
target months >= 50%
longest non-positive stretch <= 2 months
final open exposure <= 5,000 USDT
current market selector returns trade
```

If any item fails:

```text
do not launch
```

## Current Status

The framework is ready to run the proof process. The full proof report is not complete yet because the long optimization run was interrupted before results were produced.

Next execution step:

```text
Run the full optimize-stability command, save the output to logs/, then summarize it into reports/04_monthly_stability_report.md.
```

