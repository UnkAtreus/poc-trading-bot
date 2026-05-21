# 500 Start-Date Sensitivity Report

- Start-date range: `2022-05-09` to `2023-04-30`
- End date: `2023-10-30`
- Test count: `6`
- Symbols: `BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT`
- Raw CSV: `logs/start_date_sensitivity_2022_2023_current_count6.csv`

## Summary

- Launch-pass starts: `3 / 6`
- Median ROI across starts: `14.61%`
- Worst max DD start: `2022-05-09` at `19.06%`
- Worst open exposure start: `2022-12-08` at `14,311.54 USDT`
- Worst zero/non-positive stretch start: `2022-05-09` at `5` months

## Top 20 By Stability Score

| Start | Launch pass | Net PnL | ROI | Max DD | Open exposure | Positive months | Target months | Zero stretch | Worst monthly DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2022-07-19 | True | 9,589.40 | 31.96% | 4.69% | 8,117.82 | 100.0% | 81.2% | 0 | 4.29% |
| 2023-02-17 | True | 4,255.22 | 14.18% | 7.23% | 6,030.73 | 100.0% | 77.8% | 0 | 6.19% |
| 2022-09-28 | True | 7,655.01 | 25.52% | 8.60% | 8,639.81 | 100.0% | 71.4% | 0 | 8.60% |
| 2022-12-08 | False | 4,383.50 | 14.61% | 13.11% | 14,311.54 | 100.0% | 45.5% | 0 | 9.50% |
| 2023-04-30 | False | 2,545.22 | 8.48% | 6.17% | 5,101.08 | 85.7% | 42.9% | 1 | 5.61% |
| 2022-05-09 | False | 2,330.53 | 7.77% | 19.06% | 8,370.88 | 55.6% | 16.7% | 5 | 12.63% |

## Worst 20 By Max Drawdown

| Start | Launch pass | Net PnL | ROI | Max DD | Open exposure | Positive months | Target months | Zero stretch | Worst monthly DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2022-05-09 | False | 2,330.53 | 7.77% | 19.06% | 8,370.88 | 55.6% | 16.7% | 5 | 12.63% |
| 2022-12-08 | False | 4,383.50 | 14.61% | 13.11% | 14,311.54 | 100.0% | 45.5% | 0 | 9.50% |
| 2022-09-28 | True | 7,655.01 | 25.52% | 8.60% | 8,639.81 | 100.0% | 71.4% | 0 | 8.60% |
| 2023-02-17 | True | 4,255.22 | 14.18% | 7.23% | 6,030.73 | 100.0% | 77.8% | 0 | 6.19% |
| 2023-04-30 | False | 2,545.22 | 8.48% | 6.17% | 5,101.08 | 85.7% | 42.9% | 1 | 5.61% |
| 2022-07-19 | True | 9,589.40 | 31.96% | 4.69% | 8,117.82 | 100.0% | 81.2% | 0 | 4.29% |

## Decision Rule

A strategy is not start-date robust unless every tested start date passes the launch gate.
If any row fails because of liquidation, near-liquidation, high drawdown, high open exposure, or unstable monthly profit, reduce lot size or route that market condition to `no_trade`.
