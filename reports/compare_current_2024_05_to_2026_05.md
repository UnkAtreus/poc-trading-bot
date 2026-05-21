# Batch Stability Optimizer Report

## Run Config

- Raw CSV: `logs/compare_current_2024_05_to_2026_05.csv`
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
| 66 | 10 | 50,000 | 10,000 | 100 | True | False | 4.16 | 37.36% | 38.90% | 12,434.00 |  |

## Top 20 By Stability Score

| Margin | Lev | Account cap | Symbol cap | TP bps | Safe | Stable | Score | ROI | Max DD | Open exposure | Error |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 66 | 10 | 50,000 | 10,000 | 100 | True | False | 4.16 | 37.36% | 38.90% | 12,434.00 |  |

## Worst 20 By Drawdown

| Margin | Lev | Account cap | Symbol cap | TP bps | Safe | Stable | Score | ROI | Max DD | Open exposure | Error |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 66 | 10 | 50,000 | 10,000 | 100 | True | False | 4.16 | 37.36% | 38.90% | 12,434.00 |  |

## Recommended Lot Size

- Margin USD: `66`
- Leverage: `10`
- Account cap: `50000`
- Symbol cap: `10000`
- TP offset bps: `100`
- Stability score: `4.16`

## Decision

`reduce_size`
