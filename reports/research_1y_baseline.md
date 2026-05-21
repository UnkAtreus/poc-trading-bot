# Batch Stability Optimizer Report

## Run Config

- Raw CSV: `logs/research_1y_baseline.csv`
- Start: `2025-05-01`
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
| 50 | 5 | 5,000 | 1,000 | 75 | True | False | 1.96 | 5.51% | 4.97% | 2,151.58 |  |

## Top 20 By Stability Score

| Margin | Lev | Account cap | Symbol cap | TP bps | Safe | Stable | Score | ROI | Max DD | Open exposure | Error |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 50 | 5 | 5,000 | 1,000 | 75 | True | False | 1.96 | 5.51% | 4.97% | 2,151.58 |  |

## Worst 20 By Drawdown

| Margin | Lev | Account cap | Symbol cap | TP bps | Safe | Stable | Score | ROI | Max DD | Open exposure | Error |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 50 | 5 | 5,000 | 1,000 | 75 | True | False | 1.96 | 5.51% | 4.97% | 2,151.58 |  |

## Recommended Lot Size

- Margin USD: `50`
- Leverage: `5`
- Account cap: `5000`
- Symbol cap: `1000`
- TP offset bps: `75`
- Stability score: `1.96`

## Decision

`reduce_size`
