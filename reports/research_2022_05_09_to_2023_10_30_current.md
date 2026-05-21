# Batch Stability Optimizer Report

## Run Config

- Raw CSV: `logs/research_2022_05_09_to_2023_10_30_current.csv`
- Start: `2022-05-09`
- End: `2023-10-30`
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
| 66 | 10 | 50,000 | 10,000 | 100 | True | False | -10.42 | 7.77% | 19.06% | 8,370.88 |  |

## Top 20 By Stability Score

| Margin | Lev | Account cap | Symbol cap | TP bps | Safe | Stable | Score | ROI | Max DD | Open exposure | Error |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 66 | 10 | 50,000 | 10,000 | 100 | True | False | -10.42 | 7.77% | 19.06% | 8,370.88 |  |

## Worst 20 By Drawdown

| Margin | Lev | Account cap | Symbol cap | TP bps | Safe | Stable | Score | ROI | Max DD | Open exposure | Error |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 66 | 10 | 50,000 | 10,000 | 100 | True | False | -10.42 | 7.77% | 19.06% | 8,370.88 |  |

## Recommended Lot Size

- Margin USD: `66`
- Leverage: `10`
- Account cap: `50000`
- Symbol cap: `10000`
- TP offset bps: `100`
- Stability score: `-10.42`

## Decision

`reduce_size`
