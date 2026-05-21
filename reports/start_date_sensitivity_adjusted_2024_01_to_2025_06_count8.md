# 500 Start-Date Sensitivity Report

- Start-date range: `2024-01-01` to `2025-06-01`
- End date: `2026-05-01`
- Test count: `8`
- Symbols: `BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT`
- Raw CSV: `logs/start_date_sensitivity_adjusted_2024_01_to_2025_06_count8.csv`

## Summary

- Launch-pass starts: `4 / 8`
- Median ROI across starts: `26.17%`
- Worst max DD start: `2024-03-14` at `30.99%`
- Worst open exposure start: `2025-03-19` at `9,879.30 USDT`
- Worst zero/non-positive stretch start: `2024-03-14` at `5` months

## Top 20 By Stability Score

| Start | Launch pass | Net PnL | ROI | Max DD | Open exposure | Positive months | Target months | Zero stretch | Worst monthly DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2025-01-04 | False | 7,851.22 | 26.17% | 17.26% | 7,208.33 | 75.0% | 37.5% | 2 | 9.78% |
| 2025-06-01 | False | 5,649.70 | 18.83% | 16.86% | 5,968.23 | 72.7% | 45.5% | 2 | 10.81% |
| 2025-03-19 | False | 5,316.24 | 17.72% | 27.40% | 9,879.30 | 85.7% | 42.9% | 2 | 14.80% |
| 2024-10-22 | True | 7,663.53 | 25.55% | 16.70% | 7,309.00 | 78.9% | 57.9% | 2 | 15.06% |
| 2024-05-27 | True | 10,004.92 | 33.35% | 17.69% | 7,309.00 | 83.3% | 66.7% | 2 | 15.19% |
| 2024-08-09 | True | 9,273.86 | 30.91% | 19.33% | 7,309.00 | 81.0% | 61.9% | 2 | 15.04% |
| 2024-03-14 | False | 3,271.15 | 10.90% | 30.99% | 5,217.31 | 53.8% | 26.9% | 5 | 17.04% |
| 2024-01-01 | True | 9,478.91 | 31.60% | 20.49% | 7,309.00 | 82.1% | 64.3% | 2 | 15.06% |

## Worst 20 By Max Drawdown

| Start | Launch pass | Net PnL | ROI | Max DD | Open exposure | Positive months | Target months | Zero stretch | Worst monthly DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024-03-14 | False | 3,271.15 | 10.90% | 30.99% | 5,217.31 | 53.8% | 26.9% | 5 | 17.04% |
| 2025-03-19 | False | 5,316.24 | 17.72% | 27.40% | 9,879.30 | 85.7% | 42.9% | 2 | 14.80% |
| 2024-01-01 | True | 9,478.91 | 31.60% | 20.49% | 7,309.00 | 82.1% | 64.3% | 2 | 15.06% |
| 2024-08-09 | True | 9,273.86 | 30.91% | 19.33% | 7,309.00 | 81.0% | 61.9% | 2 | 15.04% |
| 2024-05-27 | True | 10,004.92 | 33.35% | 17.69% | 7,309.00 | 83.3% | 66.7% | 2 | 15.19% |
| 2025-01-04 | False | 7,851.22 | 26.17% | 17.26% | 7,208.33 | 75.0% | 37.5% | 2 | 9.78% |
| 2025-06-01 | False | 5,649.70 | 18.83% | 16.86% | 5,968.23 | 72.7% | 45.5% | 2 | 10.81% |
| 2024-10-22 | True | 7,663.53 | 25.55% | 16.70% | 7,309.00 | 78.9% | 57.9% | 2 | 15.06% |

## Decision Rule

A strategy is not start-date robust unless every tested start date passes the launch gate.
If any row fails because of liquidation, near-liquidation, high drawdown, high open exposure, or unstable monthly profit, reduce lot size or route that market condition to `no_trade`.
