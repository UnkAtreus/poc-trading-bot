# 500 Start-Date Sensitivity Report

- Start-date range: `2022-05-09` to `2023-04-30`
- End date: `2023-10-30`
- Test count: `6`
- Symbols: `BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT`
- Raw CSV: `logs/start_date_sensitivity_2022_2023_latest_grid40_count6.csv`

## Summary

- Launch-pass starts: `5 / 6`
- Median ROI across starts: `16.71%`
- Worst max DD start: `2022-05-09` at `14.99%`
- Worst open exposure start: `2022-09-28` at `12,149.40 USDT`
- Worst zero/non-positive stretch start: `2022-05-09` at `2` months

## Top 20 By Stability Score

| Start | Launch pass | Net PnL | ROI | Max DD | Open exposure | Positive months | Target months | Zero stretch | Worst monthly DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2023-02-17 | True | 4,836.23 | 16.12% | 3.92% | 9,067.98 | 100.0% | 77.8% | 0 | 3.92% |
| 2022-07-19 | True | 9,772.22 | 32.57% | 7.57% | 9,373.64 | 100.0% | 75.0% | 0 | 5.12% |
| 2023-04-30 | True | 2,141.69 | 7.14% | 5.63% | 10,907.84 | 100.0% | 57.1% | 0 | 4.20% |
| 2022-09-28 | True | 7,234.89 | 24.12% | 9.38% | 12,149.40 | 100.0% | 57.1% | 0 | 9.38% |
| 2022-12-08 | True | 5,013.38 | 16.71% | 13.20% | 8,888.25 | 100.0% | 54.5% | 0 | 12.98% |
| 2022-05-09 | False | 3,889.23 | 12.96% | 14.99% | 5,015.32 | 66.7% | 16.7% | 2 | 13.92% |

## Worst 20 By Max Drawdown

| Start | Launch pass | Net PnL | ROI | Max DD | Open exposure | Positive months | Target months | Zero stretch | Worst monthly DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2022-05-09 | False | 3,889.23 | 12.96% | 14.99% | 5,015.32 | 66.7% | 16.7% | 2 | 13.92% |
| 2022-12-08 | True | 5,013.38 | 16.71% | 13.20% | 8,888.25 | 100.0% | 54.5% | 0 | 12.98% |
| 2022-09-28 | True | 7,234.89 | 24.12% | 9.38% | 12,149.40 | 100.0% | 57.1% | 0 | 9.38% |
| 2022-07-19 | True | 9,772.22 | 32.57% | 7.57% | 9,373.64 | 100.0% | 75.0% | 0 | 5.12% |
| 2023-04-30 | True | 2,141.69 | 7.14% | 5.63% | 10,907.84 | 100.0% | 57.1% | 0 | 4.20% |
| 2023-02-17 | True | 4,836.23 | 16.12% | 3.92% | 9,067.98 | 100.0% | 77.8% | 0 | 3.92% |

## Decision Rule

A strategy is not start-date robust unless every tested start date passes the launch gate.
If any row fails because of liquidation, near-liquidation, high drawdown, high open exposure, or unstable monthly profit, reduce lot size or route that market condition to `no_trade`.
