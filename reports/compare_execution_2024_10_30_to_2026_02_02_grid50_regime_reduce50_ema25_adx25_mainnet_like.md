# Execution Model Comparison

- Range: `2024-10-30` to `2026-02-02`
- Signal: `rg_trend_grid_a200_e50_s25_t20_ema25_adx25_reduce0_5`
- Full signal: `regime_gate:inner=trend_filter:inner_inner=grid:inner_inner_anchor_period=200:inner_inner_entry_bps=50:inner_inner_step_bps=25:inner_max_trend_bps=20:max_ema_spread_bps=25:max_adx=25:unsafe_action=reduce:unsafe_size_scale=0.5`
- Execution profile: `mainnet-like`
- Realistic latencies: `0.3` seconds
- Realistic penalties: cancel `0.5`s, slippage `1` bps, pass-through `0.2` bps, full-fill `1` bps, min partial `50`%
- Initial equity: `30,000.00` USDT
- Target: `12-30%` annualized ROI
- Raw CSV: `logs/compare_execution_2024_10_30_to_2026_02_02_grid50_regime_reduce50_ema25_adx25_mainnet_like.csv`

| Model | Net PnL | ROI | Annual ROI | Max DD | Trades | Win % | Rejected | Partial | Cancel race | Dust | Slip cost | Vs naive | Target >= min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| naive | 4,008.83 | 13.36% | 10.60% | 15.14% | 432 | 100.00% | 0 | 0 | 0 | 0 | 0.0000 | +0.00% | no |
| realistic_0.3s | 3,759.08 | 12.53% | 9.94% | 15.69% | 451 | 100.00% | 0 | 93 | 0 | 0 | 99.7816 | -0.83% | no |

## Read

- Realistic rows are candle-only execution proxies, not order-book replay.
- If realistic rows lose most of naive PnL, the old backtest was likely execution-sensitive.
- A strategy is interesting only if realistic rows still clear the target with acceptable drawdown and low dust/rejection counts.