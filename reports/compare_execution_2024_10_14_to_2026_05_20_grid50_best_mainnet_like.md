# Execution Model Comparison

- Range: `2024-10-14` to `2026-05-20`
- Signal: `trend_grid_a200_e50_s25_t20`
- Full signal: `trend_filter:inner=grid:inner_anchor_period=200:inner_entry_bps=50:inner_step_bps=25:max_trend_bps=20`
- Execution profile: `mainnet-like`
- Realistic latencies: `0.15,0.3,0.5` seconds
- Realistic penalties: cancel `0.5`s, slippage `1` bps, pass-through `0.2` bps, full-fill `1` bps, min partial `50`%
- Initial equity: `30,000.00` USDT
- Target: `12-30%` annualized ROI
- Raw CSV: `logs/compare_execution_2024_10_14_to_2026_05_20_grid50_best_mainnet_like.csv`

| Model | Net PnL | ROI | Annual ROI | Max DD | Trades | Win % | Rejected | Partial | Cancel race | Dust | Slip cost | Vs naive | Target >= min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| naive | 4,859.51 | 16.20% | 10.14% | 27.77% | 428 | 100.00% | 0 | 0 | 0 | 0 | 0.0000 | +0.00% | no |
| realistic_0.15s | 5,123.24 | 17.08% | 10.69% | 25.47% | 516 | 100.00% | 0 | 124 | 0 | 0 | 135.6381 | +0.88% | no |
| realistic_0.3s | 5,123.24 | 17.08% | 10.69% | 25.47% | 516 | 100.00% | 0 | 124 | 0 | 0 | 135.6381 | +0.88% | no |
| realistic_0.5s | 5,123.24 | 17.08% | 10.69% | 25.47% | 516 | 100.00% | 0 | 124 | 0 | 0 | 135.6381 | +0.88% | no |

## Read

- Realistic rows are candle-only execution proxies, not order-book replay.
- If realistic rows lose most of naive PnL, the old backtest was likely execution-sensitive.
- A strategy is interesting only if realistic rows still clear the target with acceptable drawdown and low dust/rejection counts.