# Lot Size Test for 1.5% Monthly, TP 100 bps, Equity 50k

Question:
- Equity: 50,000 USDT
- Target: average 1.5%/month = 750 USDT/month = 9,000 USDT/year
- TP: 100 bps = 1%
- Signal: `grid(anchor_period=200,entry_bps=30,step_bps=15)`
- Current lot: 20 USDT margin/order at 10x = 200 USDT notional/order

## Equity Meaning

`--initial-equity 50000` is one shared account deposit for the whole backtest.
It is not 50,000 USDT per symbol/currency.

All symbols draw against this one account-level equity number for ROI and DD
calculation. Separately, the risk manager controls how much of that equity can
be deployed using notional caps.

## What To Adjust

To increase lot size, adjust `margin_usd` first.

Example:

```text
margin_usd = 60
leverage = 10
notional/order = 600 USDT
```

Increasing leverage instead can create the same notional with less margin, but
it moves liquidation much closer. For this strategy, increasing `margin_usd`
is the cleaner sizing knob.

## Tested Results

| Case | Margin/order | Leverage | Notional/order | Account cap | Per-symbol cap | Net | ROI | Avg monthly | Max DD | DD % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Original practical signal | 20 | 10x | 200 | 2,000 | 600 | 1,742.22 | 3.48% | 0.29% | 397.72 | 0.80% |
| Estimated 5.17x size, scaled caps | 103 | 10x | 1,030 | 10,330 | 3,100 | 1,939.85 | 3.88% | 0.32% | 6,715.55 | 13.43% |
| 103 margin, loose caps | 103 | 10x | 1,030 | 50,000 | 10,000 | 16,285.32 | 32.57% | 2.71% | 39,870.45 | 79.74% |
| 57 margin, loose caps | 57 | 10x | 570 | 50,000 | 10,000 | 8,582.47 | 17.16% | 1.43% | 21,818.95 | 43.64% |
| 60 margin, loose caps | 60 | 10x | 600 | 50,000 | 10,000 | 9,068.49 | 18.14% | 1.51% | 21,792.20 | 43.58% |

## Answer

To reach average 1.5%/month in this 2025 backtest, the tested lot size is:

```text
60 USDT margin/order
10x leverage
600 USDT notional/order
```

But this only works after loosening risk caps:

```text
max_notional_account_usd = 50,000
max_notional_per_symbol_usd = 10,000
daily_loss_limit_usd = 5,000
```

That setting is not live-safe from the current backtest alone because:
- Max DD was 43.58%.
- September lost money.
- Several symbols were still in `MERGE_PENDING` at year end.
- Liquidation is still not modeled.

## Monthly Result For 60 USDT Lot

| Month | Net | ROI % | Max DD | DD % |
|---|---:|---:|---:|---:|
| 2025-01 | 1,639.56 | 3.28 | 2,868.11 | 5.74 |
| 2025-02 | 2,636.31 | 5.27 | 3,296.82 | 6.59 |
| 2025-03 | 1,233.53 | 2.47 | 3,982.09 | 7.96 |
| 2025-04 | 43.13 | 0.09 | 4,422.75 | 8.85 |
| 2025-05 | 813.08 | 1.63 | 3,465.49 | 6.93 |
| 2025-06 | 0.00 | 0.00 | 3,776.82 | 7.55 |
| 2025-07 | 808.03 | 1.62 | 5,938.46 | 11.88 |
| 2025-08 | 752.70 | 1.51 | 6,324.45 | 12.65 |
| 2025-09 | -233.56 | -0.47 | 21,792.20 | 43.58 |
| 2025-10 | 570.03 | 1.14 | 12,266.22 | 24.53 |
| 2025-11 | 805.69 | 1.61 | 8,700.79 | 17.40 |
| 2025-12 | 0.00 | 0.00 | 14,107.55 | 28.22 |

## Raw Logs

- `logs/backtest_grid200_30_15_tp100_equity50000_margin103_caps_scaled.txt`
- `logs/backtest_grid200_30_15_tp100_equity50000_margin103_caps_scaled_daily517.txt`
- `logs/backtest_grid200_30_15_tp100_equity50000_margin103_caps_loose.txt`
- `logs/backtest_grid200_30_15_tp100_equity50000_margin57_caps_loose.txt`
- `logs/backtest_grid200_30_15_tp100_equity50000_margin60_caps_loose.txt`
