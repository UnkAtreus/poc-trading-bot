# Execution Model Comparison

- Range: `2024-10-30` to `2026-02-02`
- Signal: `rg_trend_grid_a200_e50_s25_t20_ema25_adx25_pause`
- Full signal: `regime_gate:inner=trend_filter:inner_inner=grid:inner_inner_anchor_period=200:inner_inner_entry_bps=50:inner_inner_step_bps=25:inner_max_trend_bps=20:max_ema_spread_bps=25:max_adx=25:unsafe_action=pause`
- Execution profile: `mainnet-like`
- Realistic latencies: `0.3` seconds
- Realistic penalties: cancel `0.5`s, slippage `1` bps, pass-through `0.2` bps, full-fill `1` bps, min partial `50`%
- Initial equity: `30,000.00` USDT
- Target: `12-30%` annualized ROI
- Raw CSV: `logs/compare_execution_2024_10_30_to_2026_02_02_grid50_regime_pause_ema25_adx25_mainnet_like.csv`

| Model | Net PnL | ROI | Annual ROI | Max DD | Trades | Win % | Rejected | Partial | Cancel race | Dust | Slip cost | Vs naive | Target >= min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| naive | 4,428.61 | 14.76% | 11.71% | 64.98% | 409 | 100.00% | 0 | 0 | 0 | 0 | 0.0000 | +0.00% | no |
| realistic_0.3s | 4,211.41 | 14.04% | 11.14% | 65.31% | 442 | 100.00% | 0 | 107 | 0 | 0 | 111.8092 | -0.72% | no |

## Read

- Realistic rows are candle-only execution proxies, not order-book replay.
- If realistic rows lose most of naive PnL, the old backtest was likely execution-sensitive.
- A strategy is interesting only if realistic rows still clear the target with acceptable drawdown and low dust/rejection counts.