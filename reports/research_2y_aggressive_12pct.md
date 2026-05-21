# Batch Stability Optimizer Report

## Run Config

- Raw CSV: `logs/research_2y_aggressive_12pct.csv`
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
| 100 | 10 | 10,000 | 3,000 | 75 | True | False | 0.79 | 24.75% | 39.88% | 10,826.66 |  |

## Top 20 By Stability Score

| Margin | Lev | Account cap | Symbol cap | TP bps | Safe | Stable | Score | ROI | Max DD | Open exposure | Error |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 100 | 10 | 10,000 | 3,000 | 75 | True | False | 0.79 | 24.75% | 39.88% | 10,826.66 |  |

## Worst 20 By Drawdown

| Margin | Lev | Account cap | Symbol cap | TP bps | Safe | Stable | Score | ROI | Max DD | Open exposure | Error |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 100 | 10 | 10,000 | 3,000 | 75 | True | False | 0.79 | 24.75% | 39.88% | 10,826.66 |  |

## Recommended Lot Size

- Margin USD: `100`
- Leverage: `10`
- Account cap: `10000`
- Symbol cap: `3000`
- TP offset bps: `75`
- Stability score: `0.79`

## Decision

`reduce_size`
