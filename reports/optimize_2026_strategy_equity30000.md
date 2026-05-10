# 2026 Strategy Optimization, Equity 30k

Period:
- 2026-01-01 to 2026-05-02

Baseline:
- v1 was saved before this optimization.
- v1 signal: `trend_filter(inner=grid,inner_anchor_period=200,inner_entry_bps=30,inner_step_bps=15,max_trend_bps=30)`
- v1 lot: 66 USDT margin/order
- v1 result on 2026 YTD: 45.93 + 31.28 + 110.76 + 33.15 = 221.12 USDT from Jan-Apr, weak for 2026.

## Tested Candidates

At margin 66, TP 100:

| Candidate | Net | ROI | Max DD | DD % | Read |
|---|---:|---:|---:|---:|---|
| `zscore(period=50,threshold=2.0)` | 1,877.29 | 6.26% | 5,461.32 | 18.20% | Best raw PnL, high DD |
| `bollinger_bands(period=20,num_std=2.0)` | 1,439.48 | 4.80% | 3,157.29 | 10.52% | Lower DD, under target |
| `trend_filter(grid 100/30/15, max_trend_bps=15)` | 1,044.14 | 3.48% | 1,914.91 | 6.38% | Best safer base |
| `trend_filter(grid 400/80/40, max_trend_bps=15)` | 519.02 | 1.73% | 1,805.70 | 6.02% | Safest, too low return |

Scaled follow-up tests:

| Candidate | Margin/order | Net | ROI | Max DD | DD % |
|---|---:|---:|---:|---:|---:|
| `bollinger_bands(period=20,num_std=2.0)` | 84 | 1,788.20 | 5.96% | 4,018.37 | 13.39% |
| `trend_filter(grid 100/30/15, max_trend_bps=15)` | 114 | 1,803.52 | 6.01% | 3,307.58 | 11.03% |

## Selected v2

```text
trend_filter(inner=grid,inner_anchor_period=100,inner_entry_bps=30,inner_step_bps=15,max_trend_bps=15)
margin/order: 114 USDT
leverage: 10x
TP: 100 bps
```

Reason:
- Reaches about 1.5%/month over 2026 YTD.
- Lower DD than the z-score and scaled Bollinger alternatives.
- Monthly PnL is more evenly distributed than z-score, which made almost all profit in January.

## v2 Monthly Result

| Month | Net | ROI % | Max DD | DD % |
|---|---:|---:|---:|---:|
| 2026-01 | 989.82 | 3.30 | 883.69 | 2.95 |
| 2026-02 | 418.69 | 1.40 | 3,307.58 | 11.03 |
| 2026-03 | 232.32 | 0.77 | 1,222.55 | 4.08 |
| 2026-04 | 162.68 | 0.54 | 697.90 | 2.33 |
| 2026-05 | 0.00 | 0.00 | 118.16 | 0.39 |
| TOTAL | 1,803.52 | 6.01 | 3,307.58 | 11.03 |

## Caveats

- This is optimized on only 2026 YTD and may overfit.
- It still ends with open `MERGE_PENDING` positions.
- Liquidation is still not modeled.
- It should be forward-tested before live use.

Raw logs:
- `logs/optimize_2026_equity30000_margin66_tp50_matrix.txt`
- `logs/optimize_2026_equity30000_margin66_tp100_matrix.txt`
- `logs/optimize_2026_equity30000_margin66_tp100_top_monthly.txt`
- `logs/optimize_2026_equity30000_margin84_bollinger20_2_tp100.txt`
- `logs/optimize_2026_equity30000_margin114_tfg100_30_15_tf15_tp100.txt`
