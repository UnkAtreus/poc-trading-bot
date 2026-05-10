# V3 Backtest 2021-Now

- Run date: `2026-05-03`
- Window: `2021-01-01` to `2026-05-04` UTC; May 2026 is partial, using data available at run time.
- Initial equity: `30,000 USDT`
- Strategy: v3 crash balanced: `crash_guard(trend_filter(grid anchor=100 entry=30 step=15 max_trend=15))`
- Sizing/risk: margin `114`, leverage `10x`, TP `100 bps`, account cap `20,000`, per-symbol cap `4,560`, daily loss limit `5,000`.
- Raw log: `logs/v3_backtest_2021_now_equity30000_raw_retry1.txt`
- Clean report: `logs/v3_backtest_2021_now_equity30000_clean.txt`

## Headline

| Metric | Value |
|---|---:|
| Trades | 1,113 |
| Wins / losses | 1104 / 9 |
| Win rate | 99.19% |
| Gross PnL | 21,322.16 USDT |
| Fees | -421.87 USDT |
| Net PnL | 21,744.03 USDT |
| ROI on 30k | 72.48% |
| Overall max DD | 11,417.61 USDT |
| Overall max DD % | 38.06% |
| Long PnL | 10,848.91 USDT |
| Short PnL | 10,473.26 USDT |

## Annual Summary

| Year | Trades | Net PnL | ROI | Worst monthly DD | Worst monthly DD % |
|---|---:|---:|---:|---:|---:|
| 2021 | 419 | 7,702.73 | 25.68% | 4,592.27 | 15.31% |
| 2022 | 168 | 3,139.54 | 10.47% | 2,843.87 | 9.48% |
| 2023 | 20 | 360.61 | 1.20% | 1,237.83 | 4.13% |
| 2024 | 324 | 6,532.27 | 21.77% | 5,313.21 | 17.71% |
| 2025 | 168 | 3,775.56 | 12.59% | 7,397.69 | 24.66% |
| 2026 | 14 | 233.32 | 0.78% | 1,539.92 | 5.13% |

## Per Symbol

| Symbol | Trades | W | L | Gross | Fees | Net |
|---|---:|---:|---:|---:|---:|---:|
| SOLUSDT | 373 | 364 | 9 | 7,627.15 | -146.47 | 7,773.63 |
| ETHUSDT | 299 | 299 | 0 | 5,578.21 | -112.17 | 5,690.38 |
| LTCUSDT | 153 | 153 | 0 | 2,701.80 | -54.14 | 2,755.94 |
| BNBUSDT | 110 | 110 | 0 | 1,881.00 | -37.91 | 1,918.91 |
| XRPUSDT | 89 | 89 | 0 | 1,789.80 | -35.94 | 1,825.74 |
| BTCUSDT | 86 | 86 | 0 | 1,675.80 | -33.76 | 1,709.56 |
| XAUTUSDT | 3 | 3 | 0 | 68.40 | -1.48 | 69.88 |

## Worst Monthly DD

| Month | Trades | Net PnL | ROI | Max DD | DD % |
|---|---:|---:|---:|---:|---:|
| 2025-01 | 26 | 546.26 | 1.82% | 7,397.69 | 24.66% |
| 2025-07 | 17 | 418.40 | 1.39% | 5,931.70 | 19.77% |
| 2024-11 | 24 | 546.99 | 1.82% | 5,313.21 | 17.71% |
| 2021-05 | 50 | 969.15 | 3.23% | 4,592.27 | 15.31% |
| 2025-04 | 20 | 566.71 | 1.89% | 4,276.66 | 14.26% |
| 2025-02 | 5 | 139.82 | 0.47% | 4,238.10 | 14.13% |
| 2024-12 | 22 | 430.22 | 1.43% | 4,230.80 | 14.10% |
| 2025-10 | 20 | 418.27 | 1.39% | 4,144.94 | 13.82% |
| 2025-03 | 22 | 499.78 | 1.67% | 3,857.37 | 12.86% |
| 2025-09 | 7 | 139.53 | 0.47% | 3,793.38 | 12.64% |

## Zero-Trade Stretches

- `2022-06 to 2023-09`: 16 month(s)
- `2026-03 to 2026-05`: 3 month(s)
- `2025-05 to 2025-06`: 2 month(s)
- `2021-11`: 1 month(s)
- `2024-01`: 1 month(s)

## Final Open State

- `BTCUSDT: MERGE_PENDING size=0.06422791215415678 bep=35498.5850`
- `ETHUSDT: MERGE_PENDING size=0.5062008359814513 bep=4504.1411`
- `SOLUSDT: MERGE_PENDING size=21.77803904942396 bep=104.6926`
- `XRPUSDT: MERGE_PENDING size=463.42039864398316 bep=2.4600`
- `BNBUSDT: MERGE_PENDING size=4.929400553547464 bep=462.5309`
- `LTCUSDT: MERGE_PENDING size=6.971274892381707 bep=163.5282`
- `XAUTUSDT: MERGE_PENDING size=0.37892593443883316 bep=3008.5035`

## Read

The long window is profitable in realized PnL, but it is not a clean monthly-income profile. The strategy spends long periods stuck in recovery mode, including a 16-month zero-trade stretch from 2022-06 through 2023-09, and it ends the run with seven symbols still open in `MERGE_PENDING`.

The monthly DD table resets each month; the overall max DD is larger at 11,417.61 USDT / 38.06% because it measures peak-to-trough across the full continuous equity curve.
