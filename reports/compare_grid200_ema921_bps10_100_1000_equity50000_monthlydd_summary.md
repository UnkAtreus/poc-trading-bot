# Grid 200/50/30 vs EMA 9/21, TP 10/100/1000 bps, Equity 50k

Setup:
- Symbols: BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, LTCUSDT, HYPEUSDT, ASTERUSDT, XAUTUSDT
- Strategies: `grid(anchor_period=200,entry_bps=50,step_bps=30)` and `ema_crossover(fast=9,slow=21)`
- Initial equity: 50,000 USDT
- Config from run: 10x leverage, 20 USDT margin per order
- TP 10 bps = 0.1%; TP 100 bps = 1%; TP 1000 bps = 10%
- Max DD is mark-to-market using candle closes and open positions. It is not liquidation modeling.
- Monthly DD resets the equity peak at the start of each UTC month.

## Full-period matrix

| Period | TP bps | Strategy | Trades | Win % | Net USDT | ROI % | Max DD | DD % | Open |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 2024 | 10 | grid 200/50/30 | 156 | 80.1 | -21.23 | -0.04 | 5220.67 | 10.44 | 0 |
| 2024 | 10 | ema 9/21 | 137 | 84.7 | 22.07 | 0.04 | 4771.93 | 9.54 | 0 |
| 2024 | 100 | grid 200/50/30 | 265 | 100.0 | 722.36 | 1.44 | 3122.71 | 6.25 | 4 |
| 2024 | 100 | ema 9/21 | 449 | 100.0 | 1085.42 | 2.17 | 1268.84 | 2.54 | 7 |
| 2024 | 1000 | grid 200/50/30 | 33 | 100.0 | 1042.32 | 2.08 | 1958.76 | 3.92 | 7 |
| 2024 | 1000 | ema 9/21 | 23 | 100.0 | 541.27 | 1.08 | 1775.36 | 3.55 | 7 |
| 2025 | 10 | grid 200/50/30 | 420 | 89.5 | 56.71 | 0.11 | 1468.55 | 2.94 | 0 |
| 2025 | 10 | ema 9/21 | 343 | 86.0 | 77.56 | 0.16 | 1574.33 | 3.15 | 0 |
| 2025 | 100 | grid 200/50/30 | 758 | 99.3 | 1762.24 | 3.52 | 458.70 | 0.92 | 9 |
| 2025 | 100 | ema 9/21 | 731 | 97.8 | 1608.65 | 3.22 | 470.96 | 0.94 | 4 |
| 2025 | 1000 | grid 200/50/30 | 87 | 98.9 | 2317.23 | 4.63 | 796.49 | 1.59 | 9 |
| 2025 | 1000 | ema 9/21 | 82 | 100.0 | 2044.30 | 4.09 | 703.95 | 1.41 | 9 |
| 2024-2025 | 10 | grid 200/50/30 | 156 | 80.1 | -21.23 | -0.04 | 6445.06 | 12.89 | 0 |
| 2024-2025 | 10 | ema 9/21 | 137 | 84.7 | 22.07 | 0.04 | 6746.07 | 13.49 | 0 |
| 2024-2025 | 100 | grid 200/50/30 | 271 | 100.0 | 734.58 | 1.47 | 4480.29 | 8.96 | 3 |
| 2024-2025 | 100 | ema 9/21 | 697 | 100.0 | 1626.06 | 3.25 | 2132.21 | 4.26 | 9 |
| 2024-2025 | 1000 | grid 200/50/30 | 67 | 100.0 | 1944.10 | 3.89 | 2229.16 | 4.46 | 7 |
| 2024-2025 | 1000 | ema 9/21 | 43 | 100.0 | 962.13 | 1.92 | 2523.35 | 5.05 | 8 |

## 2025 monthly DD %

Values are monthly mark-to-market max DD as a percentage of 50,000 USDT.

| Month | 10 grid | 10 ema | 100 grid | 100 ema | 1000 grid | 1000 ema |
|---|---:|---:|---:|---:|---:|---:|
| 2025-01 | 1.16 | 1.07 | 0.64 | 0.33 | 0.33 | 0.46 |
| 2025-02 | 1.45 | 1.02 | 0.37 | 0.29 | 0.26 | 0.38 |
| 2025-03 | 2.17 | 1.48 | 0.68 | 0.24 | 0.58 | 0.58 |
| 2025-04 | 2.94 | 2.40 | 0.68 | 0.79 | 0.82 | 0.57 |
| 2025-05 | 1.78 | 1.35 | 0.35 | 0.21 | 0.33 | 0.22 |
| 2025-06 | 1.72 | 1.28 | 0.34 | 0.27 | 0.21 | 0.33 |
| 2025-07 | 1.18 | 1.96 | 0.28 | 0.61 | 0.22 | 0.17 |
| 2025-08 | 1.73 | 2.32 | 0.84 | 0.75 | 0.55 | 0.36 |
| 2025-09 | 1.65 | 2.69 | 0.69 | 0.77 | 1.50 | 1.26 |
| 2025-10 | 1.86 | 3.15 | 0.64 | 0.70 | 0.90 | 0.64 |
| 2025-11 | 1.43 | 1.85 | 0.30 | 0.51 | 0.29 | 0.29 |
| 2025-12 | 1.50 | 1.01 | 0.54 | 0.89 | 0.20 | 0.12 |

## Read

For standalone 2025, `1000 bps` has the best net PnL for both strategies, but it ends with all 9 symbols open. That means the closed PnL looks strong while a lot of exposure is still unresolved.

`10 bps` closes everything by year end but barely earns anything against 50,000 USDT. It also shows larger monthly DD% than `100 bps`/`1000 bps` in several months because many small trades still carry exposure while fees/rebates and risk gating limit net gain.

The continuous 2024-2025 run is not the same as adding the standalone yearly runs. It carries positions across January 1, 2025, so open exposure and DD differ.

Raw outputs:
- `reports/compare_grid200_ema921_2024_tp10_equity50000_monthlydd.txt`
- `reports/compare_grid200_ema921_2025_tp10_equity50000_monthlydd.txt`
- `reports/compare_grid200_ema921_2024_2025_tp10_equity50000_monthlydd.txt`
- `reports/compare_grid200_ema921_2024_tp100_equity50000_monthlydd.txt`
- `reports/compare_grid200_ema921_2025_tp100_equity50000_monthlydd.txt`
- `reports/compare_grid200_ema921_2024_2025_tp100_equity50000_monthlydd.txt`
- `reports/compare_grid200_ema921_2024_tp1000_equity50000_monthlydd.txt`
- `reports/compare_grid200_ema921_2025_tp1000_equity50000_monthlydd.txt`
- `reports/compare_grid200_ema921_2024_2025_tp1000_equity50000_monthlydd.txt`
