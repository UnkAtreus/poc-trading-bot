# 500 Start-Date Sensitivity Report

- Start-date range: `2023-05-09` to `2023-08-30`
- End date: `2023-10-30`
- Test count: `6`
- Symbols: `BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT`
- Raw CSV: `logs/start_date_sensitivity_2023_current_config_count6.csv`

## Summary

- Launch-pass starts: `2 / 6`
- Median ROI across starts: `5.88%`
- Worst max DD start: `2023-06-23` at `11.90%`
- Worst open exposure start: `2023-06-23` at `12,358.17 USDT`
- Worst zero/non-positive stretch start: `2023-05-31` at `1` months

## Top 20 By Stability Score

| Start | Launch pass | Net PnL | ROI | Max DD | Open exposure | Positive months | Target months | Zero stretch | Worst monthly DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2023-05-09 | True | 2,410.51 | 8.04% | 5.32% | 4,895.85 | 100.0% | 66.7% | 0 | 5.32% |
| 2023-05-31 | True | 2,518.21 | 8.39% | 3.50% | 4,391.37 | 83.3% | 50.0% | 1 | 3.50% |
| 2023-08-07 | False | 875.75 | 2.92% | 3.77% | 6,075.31 | 66.7% | 66.7% | 1 | 3.77% |
| 2023-08-30 | False | 1,111.50 | 3.71% | 3.28% | 8,303.41 | 100.0% | 33.3% | 0 | 3.28% |
| 2023-06-23 | False | 1,764.98 | 5.88% | 11.90% | 12,358.17 | 100.0% | 40.0% | 0 | 7.91% |
| 2023-07-15 | False | 1,017.13 | 3.39% | 6.96% | 5,804.25 | 75.0% | 25.0% | 1 | 6.38% |

## Worst 20 By Max Drawdown

| Start | Launch pass | Net PnL | ROI | Max DD | Open exposure | Positive months | Target months | Zero stretch | Worst monthly DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2023-06-23 | False | 1,764.98 | 5.88% | 11.90% | 12,358.17 | 100.0% | 40.0% | 0 | 7.91% |
| 2023-07-15 | False | 1,017.13 | 3.39% | 6.96% | 5,804.25 | 75.0% | 25.0% | 1 | 6.38% |
| 2023-05-09 | True | 2,410.51 | 8.04% | 5.32% | 4,895.85 | 100.0% | 66.7% | 0 | 5.32% |
| 2023-08-07 | False | 875.75 | 2.92% | 3.77% | 6,075.31 | 66.7% | 66.7% | 1 | 3.77% |
| 2023-05-31 | True | 2,518.21 | 8.39% | 3.50% | 4,391.37 | 83.3% | 50.0% | 1 | 3.50% |
| 2023-08-30 | False | 1,111.50 | 3.71% | 3.28% | 8,303.41 | 100.0% | 33.3% | 0 | 3.28% |

## Decision Rule

A strategy is not start-date robust unless every tested start date passes the launch gate.
If any row fails because of liquidation, near-liquidation, high drawdown, high open exposure, or unstable monthly profit, reduce lot size or route that market condition to `no_trade`.
