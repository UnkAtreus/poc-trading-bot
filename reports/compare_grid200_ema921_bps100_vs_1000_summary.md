# Grid 200/50/30 vs EMA 9/21, TP 100 vs 1000 bps

Setup:
- Symbols: BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, LTCUSDT, HYPEUSDT, ASTERUSDT, XAUTUSDT
- Strategies: `grid(anchor_period=200,entry_bps=50,step_bps=30)` and `ema_crossover(fast=9,slow=21)`
- Initial equity: 3000 USDT
- Config from run: 10x leverage, 20 USDT margin per order
- TP 100 bps = 1%; TP 1000 bps = 10%
- Max DD is mark-to-market using candle closes. This is not liquidation modeling.

## Full-period matrix

| Period | TP bps | Strategy | Trades | Win % | Net USDT | ROI % | Max DD | DD % | Open |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 2024 | 100 | grid 200/50/30 | 265 | 100.0 | 722.36 | 24.08 | 3122.71 | 104.09 | 4 |
| 2024 | 100 | ema 9/21 | 449 | 100.0 | 1085.42 | 36.18 | 1268.84 | 42.29 | 7 |
| 2024 | 1000 | grid 200/50/30 | 33 | 100.0 | 1042.32 | 34.74 | 1958.76 | 65.29 | 7 |
| 2024 | 1000 | ema 9/21 | 23 | 100.0 | 541.27 | 18.04 | 1775.36 | 59.18 | 7 |
| 2025 | 100 | grid 200/50/30 | 758 | 99.3 | 1762.24 | 58.74 | 458.70 | 15.29 | 9 |
| 2025 | 100 | ema 9/21 | 731 | 97.8 | 1608.65 | 53.62 | 470.96 | 15.70 | 4 |
| 2025 | 1000 | grid 200/50/30 | 87 | 98.9 | 2317.23 | 77.24 | 796.49 | 26.55 | 9 |
| 2025 | 1000 | ema 9/21 | 82 | 100.0 | 2044.30 | 68.14 | 703.95 | 23.46 | 9 |
| 2024-2025 | 100 | grid 200/50/30 | 271 | 100.0 | 734.58 | 24.49 | 4480.29 | 149.34 | 3 |
| 2024-2025 | 100 | ema 9/21 | 697 | 100.0 | 1626.06 | 54.20 | 2132.21 | 71.07 | 9 |
| 2024-2025 | 1000 | grid 200/50/30 | 67 | 100.0 | 1944.10 | 64.80 | 2229.16 | 74.31 | 7 |
| 2024-2025 | 1000 | ema 9/21 | 43 | 100.0 | 962.13 | 32.07 | 2523.35 | 84.11 | 8 |

## 2025 month-by-month

Values are `net USDT / trades`.

| Month | 100 bps grid | 100 bps ema | 1000 bps grid | 1000 bps ema |
|---|---:|---:|---:|---:|
| 2025-01 | 497.96 / 217 | 544.84 / 238 | 601.42 / 21 | 240.68 / 11 |
| 2025-02 | 393.80 / 134 | 424.32 / 176 | 360.71 / 15 | 480.91 / 18 |
| 2025-03 | 143.34 / 45 | 134.37 / 62 | 200.40 / 6 | 180.34 / 6 |
| 2025-04 | 18.38 / 9 | 27.65 / 16 | 80.15 / 3 | 40.10 / 1 |
| 2025-05 | 48.96 / 24 | 114.89 / 58 | 140.28 / 4 | 140.30 / 6 |
| 2025-06 | 0.00 / 0 | 10.20 / 5 | 100.20 / 3 | 40.08 / 2 |
| 2025-07 | 43.68 / 20 | 70.49 / 35 | 120.25 / 5 | 180.38 / 8 |
| 2025-08 | 41.55 / 23 | 46.90 / 23 | 100.23 / 3 | 120.24 / 5 |
| 2025-09 | 61.89 / 33 | 53.06 / 26 | 60.14 / 3 | 40.10 / 2 |
| 2025-10 | 267.78 / 124 | 70.37 / 41 | 280.56 / 10 | 360.70 / 15 |
| 2025-11 | 244.90 / 129 | 111.58 / 51 | 257.15 / 13 | 180.40 / 7 |
| 2025-12 | 0.00 / 0 | 0.00 / 0 | 15.76 / 1 | 40.06 / 1 |

## Read

For standalone 2025, TP 1000 bps produced higher net than TP 100 bps for both strategies, but with far fewer closes and all 9 symbols still open at year end. That means the result is carrying much more unresolved exposure.

The continuous 2024-2025 run is not equal to adding the separate 2024 and 2025 runs. It carries positions across January 1, 2025, while the standalone yearly runs reset state at each year boundary.

The DD numbers are a warning. Several rows exceed 50% mark-to-market DD, and the 2024-2025 TP 100 grid row exceeds the 3000 USDT starting equity. Since liquidation is not modeled, these rows should not be treated as live-safe just because the reported win rate is high.

Raw outputs:
- `reports/compare_grid200_ema921_2024_tp100_equity3000.txt`
- `reports/compare_grid200_ema921_2024_tp1000_equity3000.txt`
- `reports/compare_grid200_ema921_2025_tp100_equity3000.txt`
- `reports/compare_grid200_ema921_2025_tp1000_equity3000.txt`
- `reports/compare_grid200_ema921_2024_2025_tp100_equity3000.txt`
- `reports/compare_grid200_ema921_2024_2025_tp1000_equity3000.txt`
