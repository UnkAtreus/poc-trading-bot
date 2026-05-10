# Improved Sideways Strategy, TP 100 bps, Equity 50k

Goal:
- Keep the 100 bps TP style.
- Target average return around 1.5%/month on 50,000 USDT.
- Reduce the July-December drawdown problem.

## Change

The original high-return test used:

```text
signal: grid(anchor_period=200,entry_bps=30,step_bps=15)
symbols: BTC, ETH, SOL, XRP, BNB, LTC, HYPE, ASTER, XAUT
margin/order: 60 USDT
leverage: 10x
```

Improved version:

```text
signal: trend_filter(inner=grid,inner_anchor_period=200,inner_entry_bps=30,inner_step_bps=15,max_trend_bps=30)
symbols: BTC, ETH, SOL, XRP, BNB, LTC, HYPE, XAUT
exclude: ASTER
margin/order: 66 USDT
leverage: 10x
TP: 100 bps
```

Risk caps used for this backtest:

```text
max_notional_account_usd = 50,000
max_notional_per_symbol_usd = 10,000
daily_loss_limit_usd = 5,000
```

## Result

| Case | Net | ROI | Avg Monthly | Max DD | DD % | Win % | Open |
|---|---:|---:|---:|---:|---:|---:|---:|
| Original 60 margin, all symbols | 9,068.49 | 18.14% | 1.51% | 21,792.20 | 43.58% | 94.1% | 6 |
| No ASTER, plain grid, 60 margin | 10,841.27 | 21.68% | 1.81% | 6,461.96 | 12.92% | 98.6% | 6 |
| No ASTER, trend filter 30, 60 margin | 8,267.54 | 16.54% | 1.38% | 2,360.31 | 4.72% | 98.4% | 7 |
| No ASTER, trend filter 30, 66 margin | 9,094.30 | 18.19% | 1.52% | 2,352.37 | 4.70% | 98.4% | 7 |

## Monthly Result, Improved Version

| Month | Net | ROI % | Max DD | DD % |
|---|---:|---:|---:|---:|
| 2025-01 | 1,111.92 | 2.22 | 2,189.01 | 4.38 |
| 2025-02 | 2,081.61 | 4.16 | 1,883.25 | 3.77 |
| 2025-03 | 785.92 | 1.57 | 1,831.27 | 3.66 |
| 2025-04 | 501.55 | 1.00 | 2,126.61 | 4.25 |
| 2025-05 | 411.14 | 0.82 | 667.90 | 1.34 |
| 2025-06 | 103.97 | 0.21 | 607.89 | 1.22 |
| 2025-07 | 554.57 | 1.11 | 1,721.80 | 3.44 |
| 2025-08 | 989.47 | 1.98 | 2,352.37 | 4.70 |
| 2025-09 | 579.01 | 1.16 | 1,456.28 | 2.91 |
| 2025-10 | 1,409.32 | 2.82 | 1,941.69 | 3.88 |
| 2025-11 | 449.77 | 0.90 | 1,649.52 | 3.30 |
| 2025-12 | 116.06 | 0.23 | 1,326.59 | 2.65 |

## Read

This is a real improvement for the stated goal:

- Annual average target is met: 18.19% vs target 18%.
- Max DD dropped from 43.58% to 4.70%.
- September no longer creates the huge drawdown.
- Removing ASTER helped because ASTER was the main bad symbol in the high-DD run.
- The trend filter helps because this strategy is best in sideways markets and should avoid stronger trends.

Still not solved:

- It does not make every month profitable at 1.5%.
- Several positions are still open at year end.
- Liquidation is still not modeled.
- This should be treated as an improved backtest candidate, not a live-safe configuration yet.

## Command

```bash
uv run python -m bot.main backtest \
  --start 2025-01-01 --end 2026-01-01 \
  --symbols BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT,HYPEUSDT,XAUTUSDT \
  --signal 'trend_filter:inner=grid:inner_anchor_period=200:inner_entry_bps=30:inner_step_bps=15:max_trend_bps=30' \
  --by-month --with-risk --kline-workers 4 \
  --tp-offset-bps 100 --initial-equity 50000 \
  --margin-usd 66 --leverage 10 \
  --max-notional-account 50000 \
  --max-notional-per-symbol 10000 \
  --daily-loss-limit 5000
```

## Raw Logs

- `logs/improve_tp100_margin60_trendfilter_all_symbols.txt`
- `logs/improve_tp100_margin60_trendfilter_no_aster.txt`
- `logs/improve_tp100_margin65_trendfilter30_no_aster.txt`
- `logs/improve_tp100_margin66_trendfilter30_no_aster.txt`
