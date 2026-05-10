# V1/V2 Into V3 Backtest Matrix

- V3 framework: crash guard, account cap 20,000, per-symbol cap 4,560, TP 100 bps.
- `v1_into_v3`: v1 signal and v1 sizing under v3 protection.
- `v2_into_v3`: v2 signal and v2 sizing under v3 protection.
- `v1v2_agree_into_v3`: both v1 and v2 must signal same direction.
- `v1v2_either_into_v3`: either v1 or v2 can signal; conflicts are ignored.
- Raw CSV: `logs/v1_v2_into_v3_backtest_matrix.csv`

## 2026_ytd

| Variant | Window | Net PnL | ROI | Max DD % | Trades | Win rate | Open symbols |
|---|---|---:|---:|---:|---:|---:|---:|
| v1v2_agree_into_v3 | 2026_ytd | 2,180.62 | 7.27% | 4.80% | 133 | 97.74% | 7 |
| v2_into_v3 | 2026_ytd | 1,803.40 | 6.01% | 9.59% | 97 | 100.00% | 7 |
| v1v2_either_into_v3 | 2026_ytd | 1,799.02 | 6.00% | 13.41% | 96 | 98.96% | 7 |
| v1_into_v3 | 2026_ytd | 748.93 | 2.50% | 4.87% | 73 | 100.00% | 7 |

## 2025

| Variant | Window | Net PnL | ROI | Max DD % | Trades | Win rate | Open symbols |
|---|---|---:|---:|---:|---:|---:|---:|
| v2_into_v3 | 2025 | 9,450.20 | 31.50% | 8.71% | 492 | 98.98% | 7 |
| v1_into_v3 | 2025 | 9,007.96 | 30.03% | 10.64% | 622 | 99.84% | 6 |
| v1v2_agree_into_v3 | 2025 | 5,672.56 | 18.91% | 15.25% | 363 | 99.17% | 5 |
| v1v2_either_into_v3 | 2025 | 3,596.99 | 11.99% | 34.87% | 204 | 96.57% | 1 |

## 2024_2025_continuous

| Variant | Window | Net PnL | ROI | Max DD % | Trades | Win rate | Open symbols |
|---|---|---:|---:|---:|---:|---:|---:|
| v2_into_v3 | 2024_2025_continuous | 13,780.52 | 45.94% | 62.36% | 676 | 100.00% | 7 |
| v1v2_either_into_v3 | 2024_2025_continuous | 13,173.78 | 43.91% | 67.84% | 608 | 100.00% | 7 |
| v1_into_v3 | 2024_2025_continuous | 7,599.28 | 25.33% | 36.36% | 573 | 99.13% | 7 |
| v1v2_agree_into_v3 | 2024_2025_continuous | 6,458.80 | 21.53% | 57.61% | 450 | 87.33% | 7 |

## Read

Best 2026 YTD profit: `v1v2_agree_into_v3`.
Lowest continuous 2024-2025 DD: `v1_into_v3`.

A combined v1+v2 signal is only useful if it improves the continuous drawdown problem without destroying 2026 profit.

Decision:

- Do **not** replace current v3 with `v1v2_agree_into_v3`. It is strong in 2026 YTD but still has 57.61% continuous max DD.
- Do **not** use `v1v2_either_into_v3`. It is worse than v2/v3 on drawdown.
- `v1_into_v3` is the best lower-DD continuous option, but it misses the 2026 YTD target badly: 2.50% ROI vs the 6% target.
- Current `v2_into_v3` remains the best profit-balanced setup, but the continuous carryover drawdown problem remains unsolved.
