# Batch Stability Optimizer Report

## Run Config

- Raw CSV: `logs/research_2023_tighter_filter_grid50.csv`
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
| 100 | 10 | 12,500 | 4,000 | 75 | True | True | 21.95 | 10.37% | 4.50% | 7,649.72 |  |

## Top 20 Safe But Not Stable Candidates

No safe-but-unstable candidates.

## Top 20 By Stability Score

| Margin | Lev | Account cap | Symbol cap | TP bps | Safe | Stable | Score | ROI | Max DD | Open exposure | Error |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 100 | 10 | 12,500 | 4,000 | 75 | True | True | 21.95 | 10.37% | 4.50% | 7,649.72 |  |

## Worst 20 By Drawdown

| Margin | Lev | Account cap | Symbol cap | TP bps | Safe | Stable | Score | ROI | Max DD | Open exposure | Error |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 100 | 10 | 12,500 | 4,000 | 75 | True | True | 21.95 | 10.37% | 4.50% | 7,649.72 |  |

## Recommended Lot Size

- Margin USD: `100`
- Leverage: `10`
- Account cap: `12500`
- Symbol cap: `4000`
- TP offset bps: `75`
- Stability score: `21.95`

## Decision

`trade`
