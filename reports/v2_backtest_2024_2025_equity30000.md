# V2 Backtest Comparison - Equity 30,000 USDT

Generated: 2026-05-02

## Strategy

- Version: v2
- Signal: `trend_filter(inner=grid,inner_anchor_period=100,inner_entry_bps=30,inner_step_bps=15,max_trend_bps=15)`
- Symbols: `BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, LTCUSDT, HYPEUSDT, XAUTUSDT`
- TP: 100 bps
- Initial equity: 30,000 USDT
- Margin per order: 114 USDT
- Leverage: 10x
- Notional per order: 1,140 USDT
- Risk caps: account notional 50,000 USDT, per-symbol notional 10,000 USDT, daily loss limit 5,000 USDT
- Raw logs:
  - `logs/v2_backtest_2024_equity30000.txt`
  - `logs/v2_backtest_2025_equity30000.txt`
  - `logs/v2_backtest_2024_2025_equity30000.txt`

## Summary

| Period | Date range | Trades | Win rate | Net PnL | ROI | Account max DD | Account max DD % | Worst monthly DD | Worst monthly DD % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024 only | 2024-01-01 to 2025-01-01 | 413 | 100.00% | 9,163.99 | 30.55% | 15,046.58 | 50.16% | 10,299.16 | 34.33% |
| 2025 only | 2025-01-01 to 2026-01-01 | 484 | 98.35% | 9,858.97 | 32.86% | 2,637.31 | 8.79% | 2,306.44 | 7.69% |
| 2024-2025 continuous | 2024-01-01 to 2026-01-01 | 680 | 100.00% | 14,908.51 | 49.70% | 18,673.16 | 62.24% | 10,936.92 | 36.46% |

## Read

The separate 2025-only run looks good: 32.86% ROI with 8.79% account max drawdown.

The 2024-only run makes similar profit, but risk is much higher: 50.16% account max drawdown. Most of that risk shows around late 2024, especially November and December.

The continuous 2024-2025 run is the realistic long-hold view. It does not reset positions on 2025-01-01, so open MERGE_PENDING positions from 2024 carry into 2025. That run produces 49.70% total ROI, but the max drawdown reaches 62.24%, which is too high for a stable 30,000 USDT account unless the user accepts large floating loss.

## Monthly Breakdown - 2024 Only

| Month | Trades | Win % | Net PnL | ROI | Max DD | DD % |
|---|---:|---:|---:|---:|---:|---:|
| 2024-01 | 69 | 100.0% | 1,455.08 | 4.85% | 1,040.44 | 3.47% |
| 2024-02 | 35 | 100.0% | 778.65 | 2.60% | 1,390.63 | 4.64% |
| 2024-03 | 36 | 100.0% | 860.55 | 2.87% | 3,595.12 | 11.98% |
| 2024-04 | 64 | 100.0% | 1,592.93 | 5.31% | 1,204.71 | 4.02% |
| 2024-05 | 13 | 100.0% | 255.59 | 0.85% | 1,971.65 | 6.57% |
| 2024-06 | 44 | 100.0% | 883.83 | 2.95% | 881.31 | 2.94% |
| 2024-07 | 11 | 100.0% | 186.39 | 0.62% | 3,348.93 | 11.16% |
| 2024-08 | 70 | 100.0% | 1,767.14 | 5.89% | 830.83 | 2.77% |
| 2024-09 | 21 | 100.0% | 383.73 | 1.28% | 1,330.60 | 4.44% |
| 2024-10 | 10 | 100.0% | 128.02 | 0.43% | 1,910.32 | 6.37% |
| 2024-11 | 39 | 100.0% | 860.47 | 2.87% | 10,299.16 | 34.33% |
| 2024-12 | 1 | 100.0% | 11.63 | 0.04% | 5,678.88 | 18.93% |

## Monthly Breakdown - 2025 Only

| Month | Trades | Win % | Net PnL | ROI | Max DD | DD % |
|---|---:|---:|---:|---:|---:|---:|
| 2025-01 | 85 | 100.0% | 1,961.82 | 6.54% | 1,589.74 | 5.30% |
| 2025-02 | 73 | 98.6% | 1,433.84 | 4.78% | 1,964.54 | 6.55% |
| 2025-03 | 36 | 97.2% | 693.62 | 2.31% | 2,124.42 | 7.08% |
| 2025-04 | 31 | 93.5% | 734.98 | 2.45% | 2,197.85 | 7.33% |
| 2025-05 | 25 | 96.0% | 512.61 | 1.71% | 716.09 | 2.39% |
| 2025-06 | 10 | 100.0% | 151.17 | 0.50% | 912.13 | 3.04% |
| 2025-07 | 30 | 100.0% | 535.24 | 1.78% | 1,715.41 | 5.72% |
| 2025-08 | 0 | 0.0% | 0.00 | 0.00% | 2,306.44 | 7.69% |
| 2025-09 | 34 | 100.0% | 639.43 | 2.13% | 1,135.92 | 3.79% |
| 2025-10 | 70 | 100.0% | 1,406.84 | 4.69% | 1,670.45 | 5.57% |
| 2025-11 | 54 | 94.4% | 1,079.99 | 3.60% | 1,018.05 | 3.39% |
| 2025-12 | 36 | 100.0% | 709.42 | 2.36% | 1,081.37 | 3.60% |

## Monthly Breakdown - 2024-2025 Continuous

| Month | Trades | Win % | Net PnL | ROI | Max DD | DD % |
|---|---:|---:|---:|---:|---:|---:|
| 2024-01 | 69 | 100.0% | 1,455.08 | 4.85% | 1,040.44 | 3.47% |
| 2024-02 | 35 | 100.0% | 778.65 | 2.60% | 1,390.63 | 4.64% |
| 2024-03 | 36 | 100.0% | 860.55 | 2.87% | 3,595.12 | 11.98% |
| 2024-04 | 64 | 100.0% | 1,592.93 | 5.31% | 1,204.71 | 4.02% |
| 2024-05 | 13 | 100.0% | 255.59 | 0.85% | 1,971.65 | 6.57% |
| 2024-06 | 44 | 100.0% | 883.83 | 2.95% | 881.31 | 2.94% |
| 2024-07 | 11 | 100.0% | 186.39 | 0.62% | 3,348.93 | 11.16% |
| 2024-08 | 70 | 100.0% | 1,767.14 | 5.89% | 830.83 | 2.77% |
| 2024-09 | 21 | 100.0% | 383.73 | 1.28% | 1,330.60 | 4.44% |
| 2024-10 | 10 | 100.0% | 128.02 | 0.43% | 1,910.32 | 6.37% |
| 2024-11 | 39 | 100.0% | 860.47 | 2.87% | 10,299.16 | 34.33% |
| 2024-12 | 1 | 100.0% | 11.63 | 0.04% | 5,678.88 | 18.93% |
| 2025-01 | 0 | 0.0% | 0.00 | 0.00% | 8,825.87 | 29.42% |
| 2025-02 | 7 | 100.0% | 174.52 | 0.58% | 7,577.60 | 25.26% |
| 2025-03 | 53 | 100.0% | 1,081.53 | 3.61% | 5,462.12 | 18.21% |
| 2025-04 | 43 | 100.0% | 1,046.74 | 3.49% | 4,696.09 | 15.65% |
| 2025-05 | 44 | 100.0% | 1,069.66 | 3.57% | 2,966.48 | 9.89% |
| 2025-06 | 33 | 100.0% | 662.54 | 2.21% | 3,546.42 | 11.82% |
| 2025-07 | 8 | 100.0% | 139.65 | 0.47% | 10,936.92 | 36.46% |
| 2025-08 | 0 | 0.0% | 0.00 | 0.00% | 6,999.93 | 23.33% |
| 2025-09 | 0 | 0.0% | 0.00 | 0.00% | 5,390.71 | 17.97% |
| 2025-10 | 48 | 100.0% | 976.73 | 3.26% | 9,968.99 | 33.23% |
| 2025-11 | 28 | 100.0% | 558.04 | 1.86% | 4,603.69 | 15.35% |
| 2025-12 | 3 | 100.0% | 35.12 | 0.12% | 2,789.29 | 9.30% |

## Notes

- The `2024 only` and `2025 only` rows reset the account and positions at the start of each year.
- The `2024-2025 continuous` row keeps positions open across the full date range, so it is not equal to adding the two separate yearly results.
- In the continuous run, 2025 January shows no closed trades but still has high drawdown because carried positions from 2024 remain open.
- V2 meets profit expectations in isolated 2025, but the 2024 and continuous runs show drawdown that is too high for conservative live use.
