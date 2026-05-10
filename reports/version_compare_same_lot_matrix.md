# Version Comparison - Same Lot Size

- v1 is tested with the same lot size as v2: 114 USDT margin, 10x leverage, 1,140 USDT notional/order.
- v2 baseline uses the original v2 signal and 50,000 / 10,000 notional caps.
- v3 crash balanced uses v2 signal plus crash guard and 20,000 / 4,560 notional caps.
- Raw CSV: `logs/version_compare_same_lot_matrix.csv`

## 2026_ytd

| Version | Window | Net PnL | ROI | Max DD % | Trades | Win rate | Open symbols |
|---|---|---:|---:|---:|---:|---:|---:|
| v2_baseline | 2026_ytd | 1,803.52 | 6.01% | 11.03% | 92 | 100.00% | 7 |
| v3_crash_balanced | 2026_ytd | 1,803.40 | 6.01% | 9.59% | 97 | 100.00% | 7 |
| v1_same_lot | 2026_ytd | 1,299.27 | 4.33% | 11.32% | 73 | 100.00% | 7 |

## 2025

| Version | Window | Net PnL | ROI | Max DD % | Trades | Win rate | Open symbols |
|---|---|---:|---:|---:|---:|---:|---:|
| v1_same_lot | 2025 | 14,994.02 | 49.98% | 23.04% | 651 | 98.31% | 6 |
| v2_baseline | 2025 | 9,858.97 | 32.86% | 8.79% | 484 | 98.35% | 7 |
| v3_crash_balanced | 2025 | 9,450.20 | 31.50% | 8.71% | 492 | 98.98% | 7 |

## 2024_2025_continuous

| Version | Window | Net PnL | ROI | Max DD % | Trades | Win rate | Open symbols |
|---|---|---:|---:|---:|---:|---:|---:|
| v2_baseline | 2024_2025_continuous | 14,908.51 | 49.70% | 62.24% | 680 | 100.00% | 7 |
| v1_same_lot | 2024_2025_continuous | 14,643.71 | 48.81% | 62.52% | 628 | 99.20% | 7 |
| v3_crash_balanced | 2024_2025_continuous | 13,780.52 | 45.94% | 62.36% | 676 | 100.00% | 7 |

## Recommendation Logic

- Best 2026 YTD profit: `v2_baseline`.
- Lowest continuous 2024-2025 DD: `v2_baseline`.
- If liquidation/carryover safety is priority, choose the lowest continuous DD.
- If short-term 2026 YTD profit is priority, choose the best 2026 YTD profit.

## Final Read

With the same lot size, v1 no longer has a drawdown advantage. Its earlier lower
DD came mainly from using smaller orders (`66 USDT` margin instead of `114`).

Recommendation:

- Best pure backtest PnL: `v2_baseline`.
- Best practical live choice: `v3_crash_balanced`, because it keeps the same
  2026 YTD ROI as v2, improves 2026 DD, and limits future full-cap crash
  exposure with a lower account cap.
- Do not choose `v1_same_lot`; it has weaker 2026 results and does not reduce
  continuous DD.
