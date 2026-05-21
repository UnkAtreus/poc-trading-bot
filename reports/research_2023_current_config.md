# Batch Stability Optimizer Report

## Run Config

- Raw CSV: `logs/research_2023_current_config.csv`
- Start: `2023-05-09`
- End: `2023-10-30`
- Symbols: `BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT`

## Counts

- Candidate count: `1`
- Completed count: `1`
- Pruned count: `0`
- Error count: `0`
- Launch-pass count: `1`

## Top 20 Launch-Pass Candidates

| Margin | Lev | Account cap | Symbol cap | TP bps | Safe | Stable | Score | ROI | Max DD | Open exposure | Error |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 66 | 10 | 50,000 | 10,000 | 100 | True | True | 18.11 | 8.04% | 5.32% | 4,895.85 |  |

## Top 20 Safe But Not Stable Candidates

No safe-but-unstable candidates.

## Top 20 By Stability Score

| Margin | Lev | Account cap | Symbol cap | TP bps | Safe | Stable | Score | ROI | Max DD | Open exposure | Error |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 66 | 10 | 50,000 | 10,000 | 100 | True | True | 18.11 | 8.04% | 5.32% | 4,895.85 |  |

## Worst 20 By Drawdown

| Margin | Lev | Account cap | Symbol cap | TP bps | Safe | Stable | Score | ROI | Max DD | Open exposure | Error |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 66 | 10 | 50,000 | 10,000 | 100 | True | True | 18.11 | 8.04% | 5.32% | 4,895.85 |  |

## Recommended Lot Size

- Margin USD: `66`
- Leverage: `10`
- Account cap: `50000`
- Symbol cap: `10000`
- TP offset bps: `100`
- Stability score: `18.11`

## Decision

`trade`
