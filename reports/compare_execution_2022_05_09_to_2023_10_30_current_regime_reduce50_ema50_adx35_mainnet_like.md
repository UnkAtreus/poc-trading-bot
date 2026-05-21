# Execution Model Comparison

- Range: `2022-05-09` to `2023-10-30`
- Signal: `rg_trend_grid_a200_e30_s15_t30_ema50_adx35_reduce0_5`
- Full signal: `regime_gate:inner=trend_filter:inner_inner=grid:inner_inner_anchor_period=200:inner_inner_entry_bps=30:inner_inner_step_bps=15:inner_max_trend_bps=30:max_ema_spread_bps=50:max_adx=35:unsafe_action=reduce:unsafe_size_scale=0.5`
- Execution profile: `mainnet-like`
- Realistic latencies: `0.3` seconds
- Realistic penalties: cancel `0.5`s, slippage `1` bps, pass-through `0.2` bps, full-fill `1` bps, min partial `50`%
- Initial equity: `30,000.00` USDT
- Target: `12-30%` annualized ROI
- Raw CSV: `logs/compare_execution_2022_05_09_to_2023_10_30_current_regime_reduce50_ema50_adx35_mainnet_like.csv`

| Model | Net PnL | ROI | Annual ROI | Max DD | Trades | Win % | Rejected | Partial | Cancel race | Dust | Slip cost | Vs naive | Target >= min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| naive | 2,337.13 | 7.79% | 5.28% | 17.99% | 192 | 100.00% | 0 | 0 | 0 | 0 | 0.0000 | +0.00% | no |
| realistic_0.3s | 1,979.95 | 6.60% | 4.47% | 17.47% | 188 | 99.47% | 0 | 107 | 0 | 0 | 40.5292 | -1.19% | no |

## Read

- Realistic rows are candle-only execution proxies, not order-book replay.
- If realistic rows lose most of naive PnL, the old backtest was likely execution-sensitive.
- A strategy is interesting only if realistic rows still clear the target with acceptable drawdown and low dust/rejection counts.