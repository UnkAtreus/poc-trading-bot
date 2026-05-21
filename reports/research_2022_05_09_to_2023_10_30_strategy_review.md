# Strategy Review: 2022-05-09 to 2023-10-30

## Scope

- Exact backtest window: `2022-05-09` to `2023-10-30`
- Start-date sensitivity: 6 starts from `2022-05-09` to `2023-04-30`, fixed end `2023-10-30`
- Symbols: `BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT`
- Initial equity: `30000`
- Stability target: average monthly goal checked with `target_monthly_roi_pct=1.0`, `min_positive_month_pct=70`, `min_target_month_pct=50`, `max_non_positive_stretch=2`, `max_worst_monthly_dd_pct=16`

## Settings Compared

| Name | Signal | Margin | Lev | Account cap | Symbol cap | TP bps | Monthly DD stop |
|---|---|---:|---:|---:|---:|---:|---:|
| Current config | `grid30/15`, trend max `30` | 66 | 10 | 50000 | 10000 | 100 | none |
| Second setting | `grid30/15`, trend max `30` | 100 | 10 | 12500 | 4000 | 75 | 15% |
| Latest 2023 setting | `grid40/20`, trend max `20` | 100 | 10 | 12500 | 4000 | 75 | 15% |
| Best long-window candidate | `grid50/25`, trend max `20` | 100 | 10 | 12500 | 4000 | 75 | 15% |

## Exact Window Results

| Strategy | Launch pass | ROI | Annualized | Avg month | Median month | Max DD | Worst monthly DD | Target months | Positive months | Open exposure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Current config | False | 7.77% | 5.11% | 0.43% | 0.12% | 19.06% | 12.63% | 16.7% | 55.6% | 8371 |
| Second setting | False | 8.50% | 5.59% | 0.47% | 0.10% | 19.65% | 13.82% | 22.2% | 50.0% | 9027 |
| Latest 2023 setting | False | 12.96% | 8.47% | 0.72% | 0.47% | 14.99% | 13.92% | 16.7% | 66.7% | 5015 |
| `grid50/25`, trend max `20` | False | 21.74% | 14.01% | 1.21% | 0.69% | 11.37% | 11.37% | 38.9% | 94.4% | 4633 |
| `grid40/20`, trend max `15` | False | 10.11% | 6.63% | 0.56% | 0.17% | 11.20% | 9.34% | 22.2% | 50.0% | 4334 |
| `grid60/30`, trend max `15` | False | 16.25% | 10.56% | 0.90% | 0.51% | 7.60% | 7.60% | 16.7% | 88.9% | 4079 |

## Start-Date Sensitivity

### Current Config

Pass count: `3/6`

| Start | Pass | ROI | Annualized | Avg month | Max DD | Target months | Positive months |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2022-05-09 | False | 7.77% | 5.11% | 0.43% | 19.06% | 16.7% | 55.6% |
| 2022-07-19 | True | 31.96% | 23.12% | 2.00% | 4.69% | 81.2% | 100.0% |
| 2022-09-28 | True | 25.52% | 21.51% | 1.82% | 8.60% | 71.4% | 100.0% |
| 2022-12-08 | False | 14.61% | 16.04% | 1.33% | 13.11% | 45.5% | 100.0% |
| 2023-02-17 | True | 14.18% | 19.35% | 1.58% | 7.23% | 77.8% | 100.0% |
| 2023-04-30 | False | 8.48% | 14.98% | 1.21% | 6.17% | 42.9% | 85.7% |

### Latest 2023 Setting

Pass count: `5/6`

| Start | Pass | ROI | Annualized | Avg month | Max DD | Target months | Positive months |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2022-05-09 | False | 12.96% | 8.47% | 0.72% | 14.99% | 16.7% | 66.7% |
| 2022-07-19 | True | 32.57% | 23.55% | 2.04% | 7.57% | 75.0% | 100.0% |
| 2022-09-28 | True | 24.12% | 20.34% | 1.72% | 9.38% | 57.1% | 100.0% |
| 2022-12-08 | True | 16.71% | 18.36% | 1.52% | 13.20% | 54.5% | 100.0% |
| 2023-02-17 | True | 16.12% | 22.05% | 1.79% | 3.92% | 77.8% | 100.0% |
| 2023-04-30 | True | 7.14% | 12.55% | 1.02% | 5.63% | 57.1% | 100.0% |

### Best Long-Window Candidate: Grid50

Pass count: `5/6`

| Start | Pass | ROI | Annualized | Avg month | Max DD | Target months | Positive months |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2022-05-09 | False | 21.74% | 14.01% | 1.21% | 11.37% | 38.9% | 94.4% |
| 2022-07-19 | True | 31.37% | 22.71% | 1.96% | 6.10% | 68.8% | 100.0% |
| 2022-09-28 | True | 25.70% | 21.66% | 1.84% | 13.90% | 64.3% | 100.0% |
| 2022-12-08 | True | 14.55% | 15.98% | 1.32% | 10.04% | 54.5% | 100.0% |
| 2023-02-17 | True | 16.33% | 22.34% | 1.81% | 4.36% | 66.7% | 100.0% |
| 2023-04-30 | True | 9.24% | 16.36% | 1.32% | 5.52% | 57.1% | 100.0% |

## Extra Tuning

Margin tune on `grid50/25` did not fix the exact `2022-05-09` start. Margin `110` to `140` stayed launch-fail because target-month rate remained `38.9%`.

TP tune on `grid50/25` did not fix it either:

| TP bps | Launch pass | ROI | Annualized | Avg month | Max DD | Target months | Positive months |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 30 | False | -21.43% | -14.85% | -1.19% | 36.25% | 16.7% | 50.0% |
| 50 | False | 18.67% | 12.09% | 1.04% | 14.95% | 44.4% | 94.4% |
| 75 | False | 21.74% | 14.01% | 1.21% | 11.37% | 38.9% | 94.4% |
| 100 | False | 10.68% | 7.00% | 0.59% | 14.15% | 27.8% | 77.8% |

## Decision

For full `2022-05-09` to `2023-10-30`, no tested strategy passes launch gates. `grid50/25`, trend max `20`, margin `100`, TP `75`, monthly DD stop `15%` is best safe candidate: annualized return is inside the `12-30%` goal, drawdown is acceptable, and start-date sensitivity passes `5/6`.

Weakness: exact start `2022-05-09` fails stability. Main failure is not liquidation or drawdown; it is monthly consistency. Too few months hit `1%` during early 2022 bear regime.

Practical interpretation: annual target looks possible after avoiding the May-June 2022 bear start, but the strategy is not robust enough to launch blindly across every start date in this long window.

## Raw Files

- Exact current: `logs/research_2022_05_09_to_2023_10_30_current.csv`
- Exact second: `logs/research_2022_05_09_to_2023_10_30_second.csv`
- Exact latest: `logs/research_2022_05_09_to_2023_10_30_latest_grid40.csv`
- Exact best long candidate: `logs/research_2022_05_09_to_2023_10_30_grid50.csv`
- Margin tune: `logs/research_2022_05_09_to_2023_10_30_grid50_margin_tune.csv`
- TP tune: `logs/research_2022_05_09_to_2023_10_30_grid50_tp_tune.csv`
- Sensitivity current: `logs/start_date_sensitivity_2022_2023_current_count6.csv`
- Sensitivity latest: `logs/start_date_sensitivity_2022_2023_latest_grid40_count6.csv`
- Sensitivity grid50: `logs/start_date_sensitivity_2022_2023_grid50_count6.csv`
