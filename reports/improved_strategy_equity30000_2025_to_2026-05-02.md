# Improved Strategy, Equity 30k, 2025 to 2026-05-02

Setup:
- Period: 2025-01-01 to 2026-05-02
- Equity: 30,000 USDT
- TP: 100 bps
- Margin/order: 66 USDT
- Leverage: 10x
- Symbols: BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, LTCUSDT, HYPEUSDT, XAUTUSDT
- Excluded: ASTERUSDT
- Signal: `trend_filter(inner=grid,inner_anchor_period=200,inner_entry_bps=30,inner_step_bps=15,max_trend_bps=30)`

## Result

| Metric | Value |
|---|---:|
| Closed trades | 713 |
| Win rate | 98.04% |
| Net PnL | 9,315.42 USDT |
| ROI | 31.05% |
| Approx monthly average | 1.94% |
| Global max DD | 5,043.19 USDT |
| Global DD % | 16.81% |
| Worst monthly-reset DD | 2,794.30 USDT |
| Worst monthly-reset DD % | 9.31% |

## Monthly

| Month | Net | ROI % | Max DD | DD % |
|---|---:|---:|---:|---:|
| 2025-01 | 1,111.92 | 3.71 | 2,189.01 | 7.30 |
| 2025-02 | 2,081.61 | 6.94 | 1,883.25 | 6.28 |
| 2025-03 | 785.92 | 2.62 | 1,831.27 | 6.10 |
| 2025-04 | 501.55 | 1.67 | 2,126.61 | 7.09 |
| 2025-05 | 411.14 | 1.37 | 667.90 | 2.23 |
| 2025-06 | 103.97 | 0.35 | 607.89 | 2.03 |
| 2025-07 | 554.57 | 1.85 | 1,721.80 | 5.74 |
| 2025-08 | 989.47 | 3.30 | 2,352.37 | 7.84 |
| 2025-09 | 579.01 | 1.93 | 1,456.28 | 4.85 |
| 2025-10 | 1,409.32 | 4.70 | 1,941.69 | 6.47 |
| 2025-11 | 449.77 | 1.50 | 1,649.52 | 5.50 |
| 2025-12 | 116.06 | 0.39 | 1,326.59 | 4.42 |
| 2026-01 | 45.93 | 0.15 | 2,794.30 | 9.31 |
| 2026-02 | 31.28 | 0.10 | 2,758.39 | 9.19 |
| 2026-03 | 110.76 | 0.37 | 1,297.89 | 4.33 |
| 2026-04 | 33.15 | 0.11 | 609.36 | 2.03 |
| 2026-05 | 0.00 | 0.00 | 117.72 | 0.39 |

## Read

The combined period still beats the average 1.5%/month target, but most of the
profit came from 2025. The 2026 months through 2026-05-02 are weak and show that
the strategy still depends heavily on sideways/mean-reverting conditions.

Global DD increased from the 2025-only test because open positions were carried
into 2026. The run ended with 7 symbols still in `MERGE_PENDING`.

Raw output:
- `logs/improve_tp100_margin66_trendfilter30_no_aster_equity30000_2025_to_2026-05-02.txt`
