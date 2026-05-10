# V2 Baseline vs Hold24 - 2026 YTD

- Date range: `2026-01-01` to `2026-05-02`
- Initial equity: `30,000 USDT`
- Strategy: v2
- Signal: `trend_filter(inner=grid,inner_anchor_period=100,inner_entry_bps=30,inner_step_bps=15,max_trend_bps=15)`
- TP: 100 bps
- Margin per order: 114 USDT
- Leverage: 10x
- Raw logs:
  - `logs/v2_baseline_2026_ytd_equity30000.txt`
  - `logs/v2_hold24_2026_ytd_equity30000.txt`

## Summary

| Case | Net PnL | ROI | Trades | Win rate | Stop exits | Account max DD | Account max DD % | Worst monthly DD | Worst monthly DD % | Open symbols |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 1,803.52 | 6.01% | 92 | 100.00% | 0 | 3,307.58 | 11.03% | 3,307.58 | 11.03% | 7 |
| Hold24 | -1,572.94 | -5.24% | 1,355 | 72.18% | 426 | 3,589.94 | 11.97% | 2,580.26 | 8.60% | 5 |

## Monthly

| Month | Baseline net | Baseline ROI | Baseline DD % | Hold24 net | Hold24 ROI | Hold24 DD % |
|---|---:|---:|---:|---:|---:|---:|
| 2026-01 | 989.82 | 3.30% | 2.95% | -1,032.00 | -3.44% | 6.98% |
| 2026-02 | 418.69 | 1.40% | 11.03% | -196.59 | -0.66% | 8.60% |
| 2026-03 | 232.32 | 0.77% | 4.08% | 3.17 | 0.01% | 3.19% |
| 2026-04 | 162.68 | 0.54% | 2.33% | -369.97 | -1.23% | 4.76% |
| 2026-05 | 0.00 | 0.00% | 0.39% | 22.44 | 0.07% | 0.22% |

## Read

For 2026 YTD, baseline is better. It made +1,803.52 USDT with 100% closed-trade win rate, but it ended with 7 open MERGE_PENDING symbols.

Hold24 is worse in this window. It forced 426 stop exits, dropped win rate to 72.18%, and ended net negative. The 24h stop helped the monthly-reset drawdown number in February, but the account-level max DD was slightly worse than baseline.

The conclusion is that Hold24 helped the long continuous 2024-2025 risk problem, but it is too aggressive for the 2026 YTD behavior. For 2026, v2 baseline still has floating-position risk, but Hold24 is not the right stop setting.
