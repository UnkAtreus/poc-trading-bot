# Execution Model Comparison

- Range: `2022-05-09` to `2023-10-30`
- Signal: `trend_grid_a200_e50_s25_t20`
- Full signal: `trend_filter:inner=grid:inner_anchor_period=200:inner_entry_bps=50:inner_step_bps=25:max_trend_bps=20`
- Initial equity: `30,000.00` USDT
- Target: `12-30%` annualized ROI
- Raw CSV: `logs/compare_execution_2022_05_09_to_2023_10_30_grid50_best_realistic.csv`

| Model | Net PnL | ROI | Annual ROI | Max DD | Trades | Win % | Rejected | Partial | Cancel race | Dust | Slip cost | Vs naive | Target >= min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| naive | 6,522.52 | 21.74% | 14.72% | 11.37% | 600 | 100.00% | 0 | 0 | 0 | 0 | 0.0000 | +0.00% | yes |
| realistic_1s | 3,446.54 | 11.49% | 7.78% | 7.94% | 564 | 100.00% | 2 | 510 | 0 | 2 | 185.1166 | -10.25% | no |
| realistic_3s | 3,446.54 | 11.49% | 7.78% | 7.94% | 564 | 100.00% | 2 | 510 | 0 | 2 | 185.1166 | -10.25% | no |
| realistic_5s | 3,446.54 | 11.49% | 7.78% | 7.94% | 564 | 100.00% | 2 | 510 | 0 | 2 | 185.1166 | -10.25% | no |

## Read

- `realistic_1s/3s/5s` are candle-only conservative execution proxies, not order-book replay.
- If realistic rows lose most of naive PnL, the old backtest was likely execution-sensitive.
- A strategy is interesting only if realistic rows still clear the target with acceptable drawdown and low dust/rejection counts.