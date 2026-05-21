# Batch Stability Optimizer Report

## Run Config

- Raw CSV: `logs/research_2022_05_09_to_2023_10_30_grid50_tp_tune.csv`
- Start: `2022-05-09`
- End: `2023-10-30`
- Symbols: `BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT`

## Counts

- Candidate count: `4`
- Completed count: `4`
- Pruned count: `0`
- Error count: `0`
- Launch-pass count: `0`

## Top 20 Launch-Pass Candidates

No launch-pass candidates.

## Top 20 Safe But Not Stable Candidates

| Margin | Lev | Account cap | Symbol cap | TP bps | Safe | Stable | Score | ROI | Max DD | Open exposure | Error |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 100 | 10 | 12,500 | 4,000 | 75 | True | False | 6.55 | 21.74% | 11.37% | 4,632.53 |  |
| 100 | 10 | 12,500 | 4,000 | 50 | True | False | 5.62 | 18.67% | 14.95% | 4,902.81 |  |
| 100 | 10 | 12,500 | 4,000 | 100 | True | False | -0.79 | 10.68% | 14.15% | 5,378.53 |  |
| 100 | 10 | 12,500 | 4,000 | 30 | True | False | -51.54 | -21.43% | 36.25% | 11,808.75 |  |

## Top 20 By Stability Score

| Margin | Lev | Account cap | Symbol cap | TP bps | Safe | Stable | Score | ROI | Max DD | Open exposure | Error |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 100 | 10 | 12,500 | 4,000 | 75 | True | False | 6.55 | 21.74% | 11.37% | 4,632.53 |  |
| 100 | 10 | 12,500 | 4,000 | 50 | True | False | 5.62 | 18.67% | 14.95% | 4,902.81 |  |
| 100 | 10 | 12,500 | 4,000 | 100 | True | False | -0.79 | 10.68% | 14.15% | 5,378.53 |  |
| 100 | 10 | 12,500 | 4,000 | 30 | True | False | -51.54 | -21.43% | 36.25% | 11,808.75 |  |

## Worst 20 By Drawdown

| Margin | Lev | Account cap | Symbol cap | TP bps | Safe | Stable | Score | ROI | Max DD | Open exposure | Error |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 100 | 10 | 12,500 | 4,000 | 30 | True | False | -51.54 | -21.43% | 36.25% | 11,808.75 |  |
| 100 | 10 | 12,500 | 4,000 | 50 | True | False | 5.62 | 18.67% | 14.95% | 4,902.81 |  |
| 100 | 10 | 12,500 | 4,000 | 100 | True | False | -0.79 | 10.68% | 14.15% | 5,378.53 |  |
| 100 | 10 | 12,500 | 4,000 | 75 | True | False | 6.55 | 21.74% | 11.37% | 4,632.53 |  |

## Recommended Lot Size

- Margin USD: `100`
- Leverage: `10`
- Account cap: `12500`
- Symbol cap: `4000`
- TP offset bps: `75`
- Stability score: `6.55`

## Decision

`reduce_size`
