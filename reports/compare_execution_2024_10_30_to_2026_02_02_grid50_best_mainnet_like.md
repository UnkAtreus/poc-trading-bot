# Execution Model Comparison

- Range: `2024-10-30` to `2026-02-02`
- Signal: `trend_grid_a200_e50_s25_t20`
- Full signal: `trend_filter:inner=grid:inner_anchor_period=200:inner_entry_bps=50:inner_step_bps=25:max_trend_bps=20`
- Execution profile: `mainnet-like`
- Realistic latencies: `0.15,0.3,0.5` seconds
- Realistic penalties: cancel `0.5`s, slippage `1` bps, pass-through `0.2` bps, full-fill `1` bps, min partial `50`%
- Initial equity: `30,000.00` USDT
- Target: `12-30%` annualized ROI
- Raw CSV: `logs/compare_execution_2024_10_30_to_2026_02_02_grid50_best_mainnet_like.csv`

| Model | Net PnL | ROI | Annual ROI | Max DD | Trades | Win % | Rejected | Partial | Cancel race | Dust | Slip cost | Vs naive | Target >= min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| naive | 4,936.83 | 16.46% | 13.06% | 21.80% | 432 | 100.00% | 0 | 0 | 0 | 0 | 0.0000 | +0.00% | yes |
| realistic_0.15s | 4,561.03 | 15.20% | 12.06% | 22.57% | 452 | 100.00% | 0 | 93 | 0 | 0 | 121.0259 | -1.25% | yes |
| realistic_0.3s | 4,561.03 | 15.20% | 12.06% | 22.57% | 452 | 100.00% | 0 | 93 | 0 | 0 | 121.0259 | -1.25% | yes |
| realistic_0.5s | 4,561.03 | 15.20% | 12.06% | 22.57% | 452 | 100.00% | 0 | 93 | 0 | 0 | 121.0259 | -1.25% | yes |

## Read

- Realistic rows are candle-only execution proxies, not order-book replay.
- If realistic rows lose most of naive PnL, the old backtest was likely execution-sensitive.
- A strategy is interesting only if realistic rows still clear the target with acceptable drawdown and low dust/rejection counts.