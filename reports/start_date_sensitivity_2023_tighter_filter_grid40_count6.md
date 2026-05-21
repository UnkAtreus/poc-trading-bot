# 500 Start-Date Sensitivity Report

- Start-date range: `2023-05-09` to `2023-08-30`
- End date: `2023-10-30`
- Test count: `6`
- Symbols: `BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT`
- Raw CSV: `logs/start_date_sensitivity_2023_tighter_filter_grid40_count6.csv`

## Summary

- Launch-pass starts: `1 / 6`
- Median ROI across starts: `6.96%`
- Worst max DD start: `2023-06-23` at `8.92%`
- Worst open exposure start: `2023-06-23` at `12,186.36 USDT`
- Worst zero/non-positive stretch start: `2023-07-15` at `1` months

## Top 20 By Stability Score

| Start | Launch pass | Net PnL | ROI | Max DD | Open exposure | Positive months | Target months | Zero stretch | Worst monthly DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2023-05-09 | True | 3,188.60 | 10.63% | 4.40% | 9,326.17 | 100.0% | 50.0% | 0 | 4.21% |
| 2023-08-30 | False | 1,271.32 | 4.24% | 2.50% | 8,883.05 | 100.0% | 33.3% | 0 | 2.16% |
| 2023-05-31 | False | 2,249.28 | 7.50% | 4.91% | 9,830.74 | 100.0% | 33.3% | 0 | 4.21% |
| 2023-06-23 | False | 2,087.82 | 6.96% | 8.92% | 12,186.36 | 100.0% | 40.0% | 0 | 5.69% |
| 2023-08-07 | False | 978.81 | 3.26% | 5.04% | 9,817.68 | 66.7% | 66.7% | 1 | 4.87% |
| 2023-07-15 | False | 1,102.10 | 3.67% | 5.11% | 10,395.23 | 75.0% | 25.0% | 1 | 5.11% |

## Worst 20 By Max Drawdown

| Start | Launch pass | Net PnL | ROI | Max DD | Open exposure | Positive months | Target months | Zero stretch | Worst monthly DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2023-06-23 | False | 2,087.82 | 6.96% | 8.92% | 12,186.36 | 100.0% | 40.0% | 0 | 5.69% |
| 2023-07-15 | False | 1,102.10 | 3.67% | 5.11% | 10,395.23 | 75.0% | 25.0% | 1 | 5.11% |
| 2023-08-07 | False | 978.81 | 3.26% | 5.04% | 9,817.68 | 66.7% | 66.7% | 1 | 4.87% |
| 2023-05-31 | False | 2,249.28 | 7.50% | 4.91% | 9,830.74 | 100.0% | 33.3% | 0 | 4.21% |
| 2023-05-09 | True | 3,188.60 | 10.63% | 4.40% | 9,326.17 | 100.0% | 50.0% | 0 | 4.21% |
| 2023-08-30 | False | 1,271.32 | 4.24% | 2.50% | 8,883.05 | 100.0% | 33.3% | 0 | 2.16% |

## Decision Rule

A strategy is not start-date robust unless every tested start date passes the launch gate.
If any row fails because of liquidation, near-liquidation, high drawdown, high open exposure, or unstable monthly profit, reduce lot size or route that market condition to `no_trade`.
