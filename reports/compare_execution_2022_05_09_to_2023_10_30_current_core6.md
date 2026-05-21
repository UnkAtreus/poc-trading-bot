# Execution Model Comparison

- Range: `2022-05-09` to `2023-10-30`
- Signal: `trend_filter`
- Initial equity: `30,000.00` USDT
- Target: `12-30%` annualized ROI
- Raw CSV: `logs/compare_execution_2022_05_09_to_2023_10_30_current_core6.csv`

| Model | Net PnL | ROI | Annual ROI | Max DD | Trades | Win % | Rejected | Partial | Cancel race | Dust | Slip cost | Vs naive | Target >= min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| naive | 2,518.89 | 8.40% | 5.69% | 19.06% | 192 | 100.00% | 0 | 0 | 0 | 0 | 0.0000 | +0.00% | no |
| realistic_1s | 1,631.14 | 5.44% | 3.68% | 15.57% | 240 | 100.00% | 0 | 416 | 0 | 0 | 67.4375 | -2.96% | no |
| realistic_3s | 1,631.14 | 5.44% | 3.68% | 15.57% | 240 | 100.00% | 0 | 416 | 0 | 0 | 67.4375 | -2.96% | no |
| realistic_5s | 1,631.14 | 5.44% | 3.68% | 15.57% | 240 | 100.00% | 0 | 416 | 0 | 0 | 67.4375 | -2.96% | no |

## Read

- `realistic_1s/3s/5s` are candle-only conservative execution proxies, not order-book replay.
- If realistic rows lose most of naive PnL, the old backtest was likely execution-sensitive.
- A strategy is interesting only if realistic rows still clear the target with acceptable drawdown and low dust/rejection counts.