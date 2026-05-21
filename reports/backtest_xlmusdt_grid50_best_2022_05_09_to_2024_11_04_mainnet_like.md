# XLMUSDT grid50_best backtest

- Run date: 2026-05-21
- Window: 2022-05-09 to 2024-11-04 UTC
- Symbol: XLMUSDT
- Strategy/config: current `grid50_best` config from `config/bot.yaml`
- Execution: realistic `mainnet-like` profile, 0.3s latency, 0.5s cancel delay, 1 bps slippage, 0.2 bps pass-through
- Risk: enabled
- Initial equity: 30,000 USDT
- Raw log: `logs/backtest_xlmusdt_grid50_best_2022_05_09_to_2024_11_04_mainnet_like.txt`
- Archive: `data/backtests/runs/20260520T170552830807Z_cli_backtest_c74efa942b.json`

## Summary

| Metric | Value |
|---|---:|
| Trades | 76 |
| Wins | 76 |
| Losses | 0 |
| Win rate | 100.00% |
| Gross PnL | +769.60 USDT |
| Fees signed | -20.91 USDT |
| Net PnL | +790.51 USDT |
| ROI | 2.64% |
| Max drawdown | 568.05 USDT |
| Max DD | 1.89% |
| Liquidated | false |
| Near liquidation | false |
| Worst unrealized | -561.09 USDT |
| Final open exposure | 576.82 USDT |

## Monthly read

Closed-trade PnL was concentrated in two months:

| Month | Trades | Net PnL | ROI | Max DD |
|---|---:|---:|---:|---:|
| 2023-07 | 37 | +402.90 | 1.34% | 0.87% |
| 2023-08 | 1 | +15.10 | 0.05% | 1.01% |
| 2024-03 | 38 | +372.41 | 1.24% | 1.02% |

All other months in the requested window had no closed trades, though monthly
drawdown still moved because open exposure was carried through parts of the
period.
