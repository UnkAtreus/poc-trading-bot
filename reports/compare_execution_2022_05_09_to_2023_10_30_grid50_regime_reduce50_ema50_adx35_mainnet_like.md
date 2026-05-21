# Execution Model Comparison

- Range: `2022-05-09` to `2023-10-30`
- Signal: `rg_trend_grid_a200_e50_s25_t20_ema50_adx35_reduce0_5`
- Full signal: `regime_gate:inner=trend_filter:inner_inner=grid:inner_inner_anchor_period=200:inner_inner_entry_bps=50:inner_inner_step_bps=25:inner_max_trend_bps=20:max_ema_spread_bps=50:max_adx=35:unsafe_action=reduce:unsafe_size_scale=0.5`
- Execution profile: `mainnet-like`
- Realistic latencies: `0.3` seconds
- Realistic penalties: cancel `0.5`s, slippage `1` bps, pass-through `0.2` bps, full-fill `1` bps, min partial `50`%
- Initial equity: `30,000.00` USDT
- Target: `12-30%` annualized ROI
- Raw CSV: `logs/compare_execution_2022_05_09_to_2023_10_30_grid50_regime_reduce50_ema50_adx35_mainnet_like.csv`

| Model | Net PnL | ROI | Annual ROI | Max DD | Trades | Win % | Rejected | Partial | Cancel race | Dust | Slip cost | Vs naive | Target >= min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| naive | 5,979.66 | 19.93% | 13.50% | 11.39% | 600 | 100.00% | 0 | 0 | 0 | 0 | 0.0000 | +0.00% | yes |
| realistic_0.3s | 5,618.66 | 18.73% | 12.68% | 10.17% | 663 | 100.00% | 0 | 210 | 0 | 0 | 148.7986 | -1.20% | yes |

## Read

- Realistic rows are candle-only execution proxies, not order-book replay.
- If realistic rows lose most of naive PnL, the old backtest was likely execution-sensitive.
- A strategy is interesting only if realistic rows still clear the target with acceptable drawdown and low dust/rejection counts.