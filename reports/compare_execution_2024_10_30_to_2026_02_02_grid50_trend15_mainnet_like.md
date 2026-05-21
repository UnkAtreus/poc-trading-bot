# Execution Model Comparison

- Range: `2024-10-30` to `2026-02-02`
- Signal: `trend_grid_a200_e50_s25_t15`
- Full signal: `trend_filter:inner=grid:inner_anchor_period=200:inner_entry_bps=50:inner_step_bps=25:max_trend_bps=15`
- Execution profile: `mainnet-like`
- Realistic latencies: `0.3` seconds
- Realistic penalties: cancel `0.5`s, slippage `1` bps, pass-through `0.2` bps, full-fill `1` bps, min partial `50`%
- Initial equity: `30,000.00` USDT
- Target: `12-30%` annualized ROI
- Raw CSV: `logs/compare_execution_2024_10_30_to_2026_02_02_grid50_trend15_mainnet_like.csv`

| Model | Net PnL | ROI | Annual ROI | Max DD | Trades | Win % | Rejected | Partial | Cancel race | Dust | Slip cost | Vs naive | Target >= min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| naive | 4,990.34 | 16.63% | 13.20% | 21.85% | 487 | 100.00% | 0 | 0 | 0 | 0 | 0.0000 | +0.00% | yes |
| realistic_0.3s | 4,469.15 | 14.90% | 11.82% | 23.66% | 517 | 100.00% | 0 | 117 | 0 | 0 | 118.4404 | -1.74% | no |

## Read

- Realistic rows are candle-only execution proxies, not order-book replay.
- If realistic rows lose most of naive PnL, the old backtest was likely execution-sensitive.
- A strategy is interesting only if realistic rows still clear the target with acceptable drawdown and low dust/rejection counts.