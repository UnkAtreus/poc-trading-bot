# Execution Model Comparison

- Range: `2025-05-19` to `2026-05-19`
- Signal: `trend_filter`
- Initial equity: `30,000.00` USDT
- Target: `12-30%` annualized ROI
- Raw CSV: `logs/compare_execution_2025_05_19_to_2026_05_19_full_active.csv`

| Model | Net PnL | ROI | Annual ROI | Max DD | Trades | Win % | Rejected | Partial | Cancel race | Dust | Slip cost | Vs naive | Target >= min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| naive | 2,754.14 | 9.18% | 9.18% | 4.93% | 215 | 100.00% | 0 | 0 | 0 | 0 | 0.0000 | +0.00% | no |
| realistic_1s | 3,250.10 | 10.83% | 10.83% | 9.52% | 526 | 99.81% | 1 | 1169 | 0 | 1 | 132.1902 | +1.65% | no |
| realistic_3s | 3,250.10 | 10.83% | 10.83% | 9.52% | 526 | 99.81% | 1 | 1169 | 0 | 1 | 132.1902 | +1.65% | no |
| realistic_5s | 3,250.10 | 10.83% | 10.83% | 9.52% | 526 | 99.81% | 1 | 1169 | 0 | 1 | 132.1902 | +1.65% | no |

## Read

- `realistic_1s/3s/5s` are candle-only conservative execution proxies, not order-book replay.
- If realistic rows lose most of naive PnL, the old backtest was likely execution-sensitive.
- A strategy is interesting only if realistic rows still clear the target with acceptable drawdown and low dust/rejection counts.