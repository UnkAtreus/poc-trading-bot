# Execution Model Comparison

- Range: `2026-01-01` to `2026-05-20`
- Signal: `trend_grid_a200_e50_s25_t20`
- Full signal: `trend_filter:inner=grid:inner_anchor_period=200:inner_entry_bps=50:inner_step_bps=25:max_trend_bps=20`
- Execution profile: `mainnet-like`
- Realistic latencies: `0.15,0.3,0.5` seconds
- Realistic penalties: cancel `0.5`s, slippage `1` bps, pass-through `0.2` bps, full-fill `1` bps, min partial `50`%
- Initial equity: `30,000.00` USDT
- Target: `12-30%` annualized ROI
- Raw CSV: `logs/compare_execution_2026_01_01_to_2026_05_20_grid50_best_mainnet_like.csv`

| Model | Net PnL | ROI | Annual ROI | Max DD | Trades | Win % | Rejected | Partial | Cancel race | Dust | Slip cost | Vs naive | Target >= min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| naive | 601.20 | 2.00% | 5.26% | 7.55% | 66 | 100.00% | 0 | 0 | 0 | 0 | 0.0000 | +0.00% | no |
| realistic_0.15s | 692.20 | 2.31% | 6.06% | 7.48% | 82 | 100.00% | 0 | 14 | 0 | 0 | 18.7992 | +0.30% | no |
| realistic_0.3s | 692.20 | 2.31% | 6.06% | 7.48% | 82 | 100.00% | 0 | 14 | 0 | 0 | 18.7992 | +0.30% | no |
| realistic_0.5s | 692.20 | 2.31% | 6.06% | 7.48% | 82 | 100.00% | 0 | 14 | 0 | 0 | 18.7992 | +0.30% | no |

## Read

- Realistic rows are candle-only execution proxies, not order-book replay.
- If realistic rows lose most of naive PnL, the old backtest was likely execution-sensitive.
- A strategy is interesting only if realistic rows still clear the target with acceptable drawdown and low dust/rejection counts.