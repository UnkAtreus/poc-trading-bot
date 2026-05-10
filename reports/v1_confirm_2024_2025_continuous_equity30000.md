# V1 Confirmation - 2024-2025 Continuous

Generated: 2026-05-03

## Config

- Strategy: v1
- Signal: `trend_filter(inner=grid,inner_anchor_period=200,inner_entry_bps=30,inner_step_bps=15,max_trend_bps=30)`
- TP: 100 bps
- Margin/order: 66 USDT
- Leverage: 10x
- Account cap: 50,000 USDT
- Per-symbol cap: 10,000 USDT
- Initial equity: 30,000 USDT
- Date range: `2024-01-01` to `2026-01-01`
- Raw log: `logs/v1_confirm_2024_2025_continuous_equity30000.txt`

## Result

| Metric | Value |
|---|---:|
| Net PnL | 8,484.48 USDT |
| ROI | 28.28% |
| Max DD | 10,859.50 USDT |
| Max DD % | 36.20% |
| Worst monthly DD | 6,333.18 USDT |
| Worst monthly DD % | 21.11% |
| Trades | 628 |
| Win rate | 99.20% |

## Comparison To V3 Continuous

| Strategy | Net PnL | ROI | Max DD % | Worst monthly DD % |
|---|---:|---:|---:|---:|
| v1 | 8,484.48 | 28.28% | 36.20% | 21.11% |
| v3 crash balanced | 13,780.52 | 45.94% | 62.36% | 36.46% |

## Read

V1 is lower profit than v3, but it is much better on continuous carryover
drawdown. If the priority is avoiding liquidation and stale-position risk, v1
is currently the safer choice.

V3 is better for isolated 2025 and 2026 YTD profit, but it still has dangerous
continuous carryover drawdown. Combining v1 and v2 did not fix that problem in
the previous matrix.
