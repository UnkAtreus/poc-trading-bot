# V4 Stable Income Sweep

- Window: `2022-01-01` to `2024-01-01`
- Symbols: `BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT`
- Initial equity: `30,000 USDT`
- Base signal: v3 crash balanced.
- Stable candidate rule: avg monthly ROI >= 1.0%, positive months >= 70%, longest zero stretch <= 1 month, worst monthly DD <= 10%, account max DD <= 25%.
- Summary CSV: `logs/v4_stable_income_sweep_2022_2023_less_aggressive_equity30000.csv`
- Monthly CSV: `logs/v4_stable_income_sweep_2022_2023_less_aggressive_equity30000_monthly.csv`

## Best Ranked

| Case | Net PnL | ROI | Avg monthly ROI | Positive months | Months >=1% | Longest zero | Max DD | Worst monthly DD | Trades | Stops | Open | Stable? |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v4_tp50_hold60d_lock1p5 | -441.02 | -1.47% | -0.06% | 58.3% | 58.3% | 0 | 15.59% | 14.11% | 1837 | 29 | 0 | no |

## All Cases

| Case | Net PnL | ROI | Avg monthly ROI | Positive months | Months >=1% | Longest zero | Max DD | Worst monthly DD | Trades | Stops | Open | Stable? |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v4_tp50_hold60d_lock1p5 | -441.02 | -1.47% | -0.06% | 58.3% | 58.3% | 0 | 15.59% | 14.11% | 1837 | 29 | 0 | no |
| v4_tp100_hold30d_lock1p5_dd10 | -5,076.74 | -16.92% | -0.71% | 66.7% | 58.3% | 0 | 28.93% | 10.12% | 973 | 52 | 5 | no |
| v4_tp50_hold30d_lock1p5 | -2,447.25 | -8.16% | -0.34% | 54.2% | 41.7% | 0 | 25.34% | 12.75% | 2489 | 58 | 0 | no |
| v4_tp100_hold60d_lock1p5 | -1,267.41 | -4.22% | -0.18% | 70.8% | 58.3% | 0 | 23.86% | 20.21% | 915 | 27 | 2 | no |
| v4_tp50_hold30d_lock1p5_dd10 | -10,394.21 | -34.65% | -1.44% | 58.3% | 41.7% | 0 | 41.64% | 10.17% | 1454 | 72 | 1 | no |

## Read

This is a backtest-only v4 stability experiment. The monthly profit lock blocks new entries after the realized monthly target is reached, the monthly DD stop closes open positions and blocks new entries for the rest of that UTC month, and max-hold closes stale positions. These controls are not live orchestration yet.
