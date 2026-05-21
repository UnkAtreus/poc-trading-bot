# Batch Stability Optimizer Report

## Run Config

- Raw CSV: `logs/research_2022_05_09_to_2023_10_30_grid50_margin_tune.csv`
- Start: `2022-05-09`
- End: `2023-10-30`
- Symbols: `BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT`

## Counts

- Candidate count: `5`
- Completed count: `5`
- Pruned count: `0`
- Error count: `0`
- Launch-pass count: `0`

## Top 20 Launch-Pass Candidates

No launch-pass candidates.

## Top 20 Safe But Not Stable Candidates

| Margin | Lev | Account cap | Symbol cap | TP bps | Safe | Stable | Score | ROI | Max DD | Open exposure | Error |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 140 | 10 | 12,500 | 4,000 | 75 | True | False | 6.92 | 27.46% | 14.46% | 6,485.54 |  |
| 120 | 10 | 12,500 | 4,000 | 75 | True | False | 6.65 | 25.87% | 13.64% | 5,559.03 |  |
| 130 | 10 | 12,500 | 4,000 | 75 | True | False | 6.64 | 27.56% | 14.78% | 6,022.29 |  |
| 110 | 10 | 12,500 | 4,000 | 75 | True | False | 6.62 | 23.92% | 12.50% | 5,095.78 |  |
| 125 | 10 | 12,500 | 4,000 | 75 | True | False | 6.58 | 26.31% | 14.21% | 5,790.66 |  |

## Top 20 By Stability Score

| Margin | Lev | Account cap | Symbol cap | TP bps | Safe | Stable | Score | ROI | Max DD | Open exposure | Error |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 140 | 10 | 12,500 | 4,000 | 75 | True | False | 6.92 | 27.46% | 14.46% | 6,485.54 |  |
| 120 | 10 | 12,500 | 4,000 | 75 | True | False | 6.65 | 25.87% | 13.64% | 5,559.03 |  |
| 130 | 10 | 12,500 | 4,000 | 75 | True | False | 6.64 | 27.56% | 14.78% | 6,022.29 |  |
| 110 | 10 | 12,500 | 4,000 | 75 | True | False | 6.62 | 23.92% | 12.50% | 5,095.78 |  |
| 125 | 10 | 12,500 | 4,000 | 75 | True | False | 6.58 | 26.31% | 14.21% | 5,790.66 |  |

## Worst 20 By Drawdown

| Margin | Lev | Account cap | Symbol cap | TP bps | Safe | Stable | Score | ROI | Max DD | Open exposure | Error |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 130 | 10 | 12,500 | 4,000 | 75 | True | False | 6.64 | 27.56% | 14.78% | 6,022.29 |  |
| 140 | 10 | 12,500 | 4,000 | 75 | True | False | 6.92 | 27.46% | 14.46% | 6,485.54 |  |
| 125 | 10 | 12,500 | 4,000 | 75 | True | False | 6.58 | 26.31% | 14.21% | 5,790.66 |  |
| 120 | 10 | 12,500 | 4,000 | 75 | True | False | 6.65 | 25.87% | 13.64% | 5,559.03 |  |
| 110 | 10 | 12,500 | 4,000 | 75 | True | False | 6.62 | 23.92% | 12.50% | 5,095.78 |  |

## Recommended Lot Size

- Margin USD: `140`
- Leverage: `10`
- Account cap: `12500`
- Symbol cap: `4000`
- TP offset bps: `75`
- Stability score: `6.92`

## Decision

`reduce_size`
