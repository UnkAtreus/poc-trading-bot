# V4 Stable Income Sweep

- Window: `2022-01-01` to `2024-01-01`
- Symbols: `BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT`
- Initial equity: `30,000 USDT`
- Base signal: v3 crash balanced.
- Stable candidate rule: avg monthly ROI >= 1.0%, positive months >= 70%, longest zero stretch <= 1 month, worst monthly DD <= 10%, account max DD <= 25%.
- Summary CSV: `logs/v4_stable_income_sweep_2022_2023_equity30000.csv`
- Monthly CSV: `logs/v4_stable_income_sweep_2022_2023_equity30000_monthly.csv`

## Best Ranked

| Case | Net PnL | ROI | Avg monthly ROI | Positive months | Months >=1% | Longest zero | Max DD | Worst monthly DD | Trades | Stops | Open | Stable? |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v4_tp50_hold14d_lock1p5_dd8 | 149.56 | 0.50% | 0.02% | 79.2% | 45.8% | 0 | 9.28% | 8.13% | 1369 | 46 | 0 | no |

## All Cases

| Case | Net PnL | ROI | Avg monthly ROI | Positive months | Months >=1% | Longest zero | Max DD | Worst monthly DD | Trades | Stops | Open | Stable? |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v4_tp50_hold14d_lock1p5_dd8 | 149.56 | 0.50% | 0.02% | 79.2% | 45.8% | 0 | 9.28% | 8.13% | 1369 | 46 | 0 | no |
| v4_tp100_hold30d_lock1p5_dd10 | -5,076.74 | -16.92% | -0.71% | 66.7% | 58.3% | 0 | 28.93% | 10.12% | 973 | 52 | 5 | no |
| v4_tp30_hold14d_lock1p5_dd8 | -7,940.40 | -26.47% | -1.10% | 54.2% | 25.0% | 0 | 34.67% | 8.09% | 3524 | 103 | 5 | no |
| v4_tp50_hold30d_lock1p5_dd10 | -10,394.21 | -34.65% | -1.44% | 58.3% | 41.7% | 0 | 41.64% | 10.17% | 1454 | 72 | 1 | no |
| v4_tp30_hold7d_lock1p5_dd8 | -11,026.09 | -36.75% | -1.53% | 45.8% | 33.3% | 0 | 41.45% | 8.28% | 4012 | 133 | 0 | no |
| v3_baseline | 1,524.43 | 5.08% | 0.21% | 16.7% | 4.2% | 15 | 21.74% | 11.57% | 85 | 0 | 6 | no |

## Read

This is a backtest-only v4 stability experiment. The monthly profit lock blocks new entries after the realized monthly target is reached, the monthly DD stop closes open positions and blocks new entries for the rest of that UTC month, and max-hold closes stale positions. These controls are not live orchestration yet.
