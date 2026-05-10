# Start-Date Backtest Comparison

Date: `2026-05-09`

Purpose: test how results change when the same trading bot starts at different historical dates and runs to present. This checks path dependency: a grid/recovery bot can look profitable from one start date but become stuck in large recovery exposure from another start date.

## Config

- End date: `2026-05-09`
- Symbols: `BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT`
- Initial equity: `30,000 USDT`
- Signal: current config from `config/bot.yaml`
  - `trend_filter(inner=grid)`
  - `inner_anchor_period=200`
  - `inner_entry_bps=30`
  - `inner_step_bps=15`
  - `max_trend_bps=30`
- Sizing:
  - margin/order: `66 USDT`
  - leverage: `10x`
  - notional/order: `660 USDT`
- Risk enabled: yes
- Raw logs:
  - `logs/backtest_start_2022-01-20_to_2026-05-09_core6.txt`
  - `logs/backtest_start_2024-09-07_to_2026-05-09_core6.txt`

## Commands Run

```bash
nice -n 10 uv run python -m bot.main backtest \
  --start 2022-01-20 \
  --end 2026-05-09 \
  --symbols BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT \
  --with-risk \
  --by-month \
  > logs/backtest_start_2022-01-20_to_2026-05-09_core6.txt 2>&1
```

```bash
nice -n 10 uv run python -m bot.main backtest \
  --start 2024-09-07 \
  --end 2026-05-09 \
  --symbols BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT \
  --with-risk \
  --by-month \
  > logs/backtest_start_2024-09-07_to_2026-05-09_core6.txt 2>&1
```

## Headline Results

| Start date | Trades | Win rate | Net PnL | ROI | Overall max DD | Liquidated | Near liq | Worst unrealized | Final open exposure |
|---|---:|---:|---:|---:|---:|---|---|---:|---:|
| `2022-01-20` | 1,043 | 100.00% | 15,686.66 | 52.29% | 25.46% | false | false | -7,247.34 | 12,884.53 |
| `2024-09-07` | 303 | 99.67% | 4,306.22 | 14.35% | 68.60% | false | false | -15,273.13 | 15,959.60 |

## Monthly Stability

| Start date | Months | Positive months | Months >= 0.5% ROI | Avg monthly ROI | Median monthly ROI | Longest zero/non-positive stretch | Worst monthly DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| `2022-01-20` | 53 | 31 / 58.5% | 28 / 52.8% | 0.99% | 0.67% | 14 months | 21.46% |
| `2024-09-07` | 21 | 13 / 61.9% | 9 / 42.9% | 0.68% | 0.23% | 4 months | 36.52% |

## Launch Gate Check

Required gates from the proof plan:

```text
liquidated = false
near_liquidation = false
max_drawdown <= 25%
final_open_exposure <= 5,000 USDT
positive_months >= 70%
target_months >= 50%
longest non-positive stretch <= 2 months
worst_monthly_dd <= 10%
```

| Start date | Safety result | Stability result | Decision |
|---|---|---|---|
| `2022-01-20` | Fails: overall DD `25.46%` is above 25%, open exposure `12,884.53` is above 5,000 | Fails: positive months `58.5%`, zero stretch `14`, worst monthly DD `21.46%` | `no_trade` for real money |
| `2024-09-07` | Fails: overall DD `68.60%`, open exposure `15,959.60` is above 5,000 | Fails: positive months `61.9%`, target months `42.9%`, zero stretch `4`, worst monthly DD `36.52%` | `no_trade` for real money |

## Read

Both runs made realized profit and avoided modeled liquidation, but this is not enough for real money. The bot carries large open recovery exposure at the end of both tests, and the later start date has much worse path dependency. Starting on `2024-09-07` causes a very large overall drawdown of `68.60%`, even though realized PnL is positive.

The current bot is therefore not proven stable by start-date sensitivity testing. It should not launch with the current `66 USDT / 10x / 50,000 account cap` style risk profile.

## Next Test

Run the same start-date comparison after the overnight `optimize-stability` job identifies smaller safe lot-size candidates. The next comparison should test the best safe candidate, not the current aggressive config.

Recommended next start dates:

```text
2021-01-01
2022-01-20
2023-01-01
2024-01-01
2024-09-07
2025-01-01
2026-01-01
```

Acceptance rule: a candidate must pass every start date. If one start date fails, the strategy is path-dependent and should be reduced, routed to `no_trade`, or rejected.

