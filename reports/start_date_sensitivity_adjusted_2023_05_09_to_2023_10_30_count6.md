# 500 Start-Date Sensitivity Report

- Start-date range: `2023-05-09` to `2023-08-30`
- End date: `2023-10-30`
- Test count: `6`
- Symbols: `BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT`
- Raw CSV: `logs/start_date_sensitivity_adjusted_2023_05_09_to_2023_10_30_count6.csv`

## Summary

- Launch-pass starts: `0 / 6`
- Median ROI across starts: `5.93%`
- Worst max DD start: `2023-05-09` at `12.96%`
- Worst open exposure start: `2023-06-23` at `13,113.56 USDT`
- Worst zero/non-positive stretch start: `2023-05-09` at `1` months

## Top 20 By Stability Score

| Start | Launch pass | Net PnL | ROI | Max DD | Open exposure | Positive months | Target months | Zero stretch | Worst monthly DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2023-08-07 | False | 1,448.62 | 4.83% | 5.33% | 11,043.28 | 66.7% | 66.7% | 1 | 4.83% |
| 2023-08-30 | False | 1,779.62 | 5.93% | 3.90% | 10,398.13 | 100.0% | 33.3% | 0 | 3.17% |
| 2023-06-23 | False | 2,634.60 | 8.78% | 10.27% | 13,113.56 | 100.0% | 40.0% | 0 | 6.64% |
| 2023-05-31 | False | 2,903.81 | 9.68% | 8.46% | 11,177.09 | 100.0% | 33.3% | 0 | 7.33% |
| 2023-07-15 | False | 1,348.61 | 4.50% | 10.06% | 10,208.10 | 75.0% | 25.0% | 1 | 10.06% |
| 2023-05-09 | False | 1,291.42 | 4.30% | 12.96% | 2,293.75 | 66.7% | 16.7% | 1 | 12.96% |

## Worst 20 By Max Drawdown

| Start | Launch pass | Net PnL | ROI | Max DD | Open exposure | Positive months | Target months | Zero stretch | Worst monthly DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2023-05-09 | False | 1,291.42 | 4.30% | 12.96% | 2,293.75 | 66.7% | 16.7% | 1 | 12.96% |
| 2023-06-23 | False | 2,634.60 | 8.78% | 10.27% | 13,113.56 | 100.0% | 40.0% | 0 | 6.64% |
| 2023-07-15 | False | 1,348.61 | 4.50% | 10.06% | 10,208.10 | 75.0% | 25.0% | 1 | 10.06% |
| 2023-05-31 | False | 2,903.81 | 9.68% | 8.46% | 11,177.09 | 100.0% | 33.3% | 0 | 7.33% |
| 2023-08-07 | False | 1,448.62 | 4.83% | 5.33% | 11,043.28 | 66.7% | 66.7% | 1 | 4.83% |
| 2023-08-30 | False | 1,779.62 | 5.93% | 3.90% | 10,398.13 | 100.0% | 33.3% | 0 | 3.17% |

## Decision Rule

A strategy is not start-date robust unless every tested start date passes the launch gate.
If any row fails because of liquidation, near-liquidation, high drawdown, high open exposure, or unstable monthly profit, reduce lot size or route that market condition to `no_trade`.
