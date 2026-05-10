# Best Signal Search for 1-2% Monthly, TP 100 bps, Equity 50k

Target:
- Equity: 50,000 USDT
- TP: 100 bps = 1%
- Desired average return: 1.5%/month = 750 USDT/month = 9,000 USDT/year
- Current bot sizing from config: 20 USDT margin/order, 10x leverage = 200 USDT notional/order
- Risk enabled: account notional cap 2,000 USDT, per-symbol cap 600 USDT

## Result

No tested signal reaches the target with current sizing/risk.

The best 2025 result was:

| Rank | Signal | Net USDT | Annual ROI | Avg Monthly ROI | Max DD | DD % | Open |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | `grid(anchor_period=200,entry_bps=50,step_bps=30)` | 1762.24 | 3.52% | 0.29% | 458.70 | 0.92% | 9 |
| 2 | `grid(anchor_period=200,entry_bps=30,step_bps=15)` | 1742.22 | 3.48% | 0.29% | 397.72 | 0.80% | 3 |
| 3 | `ema_crossover(fast=9,slow=21)` | 1608.65 | 3.22% | 0.27% | 470.96 | 0.94% | 4 |
| 4 | `ema_crossover(fast=20,slow=50)` | 1527.04 | 3.05% | 0.25% | 563.32 | 1.13% | 6 |
| 5 | `grid(anchor_period=100,entry_bps=50,step_bps=20)` | 1499.72 | 3.00% | 0.25% | 1070.80 | 2.14% | 1 |
| 6 | `trend_filter(inner=grid,inner_anchor_period=200,inner_entry_bps=50,inner_step_bps=30,max_trend_bps=30)` | 1391.32 | 2.78% | 0.23% | 900.51 | 1.80% | 3 |
| 7 | `placeholder_rsi(period=7,oversold=25,overbought=75)` | 858.20 | 1.72% | 0.14% | 1257.08 | 2.51% | 0 |

## Recommendation

Best raw PnL signal:

```text
grid:anchor_period=200:entry_bps=50:step_bps=30
```

Best practical signal from this sweep:

```text
grid:anchor_period=200:entry_bps=30:step_bps=15
```

Reason: it earned almost the same as the top signal, but with lower max DD and fewer open symbols at year end.

## Monthly Check, Best Practical Signal

`grid(anchor_period=200,entry_bps=30,step_bps=15)`:

| Month | Net USDT | ROI % | Max DD | DD % |
|---|---:|---:|---:|---:|
| 2025-01 | 510.18 | 1.02 | 323.23 | 0.65 |
| 2025-02 | 439.17 | 0.88 | 197.83 | 0.40 |
| 2025-03 | 142.80 | 0.29 | 245.94 | 0.49 |
| 2025-04 | 14.28 | 0.03 | 352.82 | 0.71 |
| 2025-05 | 75.92 | 0.15 | 162.42 | 0.32 |
| 2025-06 | 20.40 | 0.04 | 108.84 | 0.22 |
| 2025-07 | 81.60 | 0.16 | 186.53 | 0.37 |
| 2025-08 | 134.64 | 0.27 | 383.38 | 0.77 |
| 2025-09 | 173.40 | 0.35 | 307.20 | 0.61 |
| 2025-10 | 106.08 | 0.21 | 199.85 | 0.40 |
| 2025-11 | 23.35 | 0.05 | 240.73 | 0.48 |
| 2025-12 | 20.40 | 0.04 | 308.77 | 0.62 |

This does not satisfy the monthly target. It only averages 0.29%/month.

## Sizing Gap

To reach 1.5% average monthly on 50,000 USDT:

```text
target annual net = 50,000 * 18% = 9,000 USDT
best practical annual net = 1,742.22 USDT
required rough size multiplier = 9,000 / 1,742.22 = 5.17x
```

That means a signal alone is not enough under the current sizing. Roughly, the bot would need about 5.17x more deployed notional, for example moving from:

```text
20 USDT margin/order, 200 USDT notional/order
```

to about:

```text
103 USDT margin/order, 1,033 USDT notional/order
```

and increasing account/per-symbol notional caps accordingly.

Approximate cap scaling:

```text
account notional cap: 2,000 -> 10,330 USDT
per-symbol cap     :   600 ->  3,100 USDT
```

This is only a sizing estimate; liquidation modeling is still missing, so this should not be treated as live-safe.

If the target is stricter — every month must reach 1.5% — then the weakest month in the best practical signal was April at only 14.28 USDT net. Scaling that to 750 USDT would require about 52.5x current lot size:

```text
1,050 USDT margin/order, 10,500 USDT notional/order
```

That is not a reasonable live setting without liquidation modeling and a redesigned risk system.

## Raw Reports

- `logs/search_best_signal_2025_tp100_equity50000_matrix.txt`
- `logs/search_best_signal_2025_tp100_equity50000_top_monthly.txt`
