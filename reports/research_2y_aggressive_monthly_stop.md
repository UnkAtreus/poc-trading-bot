# Batch Stability Optimizer Report

## Run Config

- Raw CSV: `logs/research_2y_aggressive_monthly_stop.csv`
- Start: `2024-05-01`
- End: `2026-05-01`
- Symbols: `BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT`

## Counts

- Candidate count: `1`
- Completed count: `1`
- Pruned count: `0`
- Error count: `0`
- Launch-pass count: `0`

## Top 20 Launch-Pass Candidates

No launch-pass candidates.

## Top 20 Safe But Not Stable Candidates

| Margin | Lev | Account cap | Symbol cap | TP bps | Safe | Stable | Score | ROI | Max DD | Open exposure | Error |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 100 | 10 | 10,000 | 3,000 | 75 | True | False | -36.33 | 20.16% | 21.67% | 5,257.50 |  |

## Top 20 By Stability Score

| Margin | Lev | Account cap | Symbol cap | TP bps | Safe | Stable | Score | ROI | Max DD | Open exposure | Error |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 100 | 10 | 10,000 | 3,000 | 75 | True | False | -36.33 | 20.16% | 21.67% | 5,257.50 |  |

## Worst 20 By Drawdown

| Margin | Lev | Account cap | Symbol cap | TP bps | Safe | Stable | Score | ROI | Max DD | Open exposure | Error |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 100 | 10 | 10,000 | 3,000 | 75 | True | False | -36.33 | 20.16% | 21.67% | 5,257.50 |  |

## Recommended Lot Size

- Margin USD: `100`
- Leverage: `10`
- Account cap: `10000`
- Symbol cap: `3000`
- TP offset bps: `75`
- Stability score: `-36.33`

## Decision

`reduce_size`
