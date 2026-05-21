# 500 Start-Date Sensitivity Report

- Start-date range: `2022-05-09` to `2023-04-30`
- End date: `2023-10-30`
- Test count: `6`
- Symbols: `BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT`
- Raw CSV: `logs/start_date_sensitivity_2022_2023_grid50_count6.csv`

## Summary

- Launch-pass starts: `5 / 6`
- Median ROI across starts: `21.74%`
- Worst max DD start: `2022-09-28` at `13.90%`
- Worst open exposure start: `2022-09-28` at `12,160.75 USDT`
- Worst zero/non-positive stretch start: `2022-05-09` at `1` months

## Top 20 By Stability Score

| Start | Launch pass | Net PnL | ROI | Max DD | Open exposure | Positive months | Target months | Zero stretch | Worst monthly DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2023-02-17 | True | 4,898.22 | 16.33% | 4.36% | 9,382.32 | 100.0% | 66.7% | 0 | 4.36% |
| 2022-07-19 | True | 9,410.34 | 31.37% | 6.10% | 8,900.44 | 100.0% | 68.8% | 0 | 6.10% |
| 2023-04-30 | True | 2,772.91 | 9.24% | 5.52% | 8,711.61 | 100.0% | 57.1% | 0 | 5.52% |
| 2022-09-28 | True | 7,711.41 | 25.70% | 13.90% | 12,160.75 | 100.0% | 64.3% | 0 | 10.32% |
| 2022-12-08 | True | 4,366.50 | 14.55% | 10.04% | 8,583.52 | 100.0% | 54.5% | 0 | 8.14% |
| 2022-05-09 | False | 6,522.52 | 21.74% | 11.37% | 4,632.53 | 94.4% | 38.9% | 1 | 11.37% |

## Worst 20 By Max Drawdown

| Start | Launch pass | Net PnL | ROI | Max DD | Open exposure | Positive months | Target months | Zero stretch | Worst monthly DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2022-09-28 | True | 7,711.41 | 25.70% | 13.90% | 12,160.75 | 100.0% | 64.3% | 0 | 10.32% |
| 2022-05-09 | False | 6,522.52 | 21.74% | 11.37% | 4,632.53 | 94.4% | 38.9% | 1 | 11.37% |
| 2022-12-08 | True | 4,366.50 | 14.55% | 10.04% | 8,583.52 | 100.0% | 54.5% | 0 | 8.14% |
| 2022-07-19 | True | 9,410.34 | 31.37% | 6.10% | 8,900.44 | 100.0% | 68.8% | 0 | 6.10% |
| 2023-04-30 | True | 2,772.91 | 9.24% | 5.52% | 8,711.61 | 100.0% | 57.1% | 0 | 5.52% |
| 2023-02-17 | True | 4,898.22 | 16.33% | 4.36% | 9,382.32 | 100.0% | 66.7% | 0 | 4.36% |

## Decision Rule

A strategy is not start-date robust unless every tested start date passes the launch gate.
If any row fails because of liquidation, near-liquidation, high drawdown, high open exposure, or unstable monthly profit, reduce lot size or route that market condition to `no_trade`.
