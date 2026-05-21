# Dashboard Backtest 1779272887

- Started UTC: `2026-05-20T10:28:07.712694+00:00`
- Duration: `74.6s`
- Exit code: `0`
- Signal: `trend_grid_a200_e50_s25_t30`
- Full signal: `trend_filter:inner=grid:inner_anchor_period=200:inner_entry_bps=50:inner_step_bps=25:max_trend_bps=30`
- Symbols: `BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, LTCUSDT`
- Window: `2023-02-17` to `2023-10-30`
- Initial equity: `10000.0`
- Margin / leverage: `100.0` USDT × `10`
- TP / caps: TP `75.0` bps, account cap `12500.0`, symbol cap `4000.0`
- Daily loss limit: `5000.0`
- Raw log: `logs/dashboard_backtest_1779272887.txt`

## Command

```
uv run trading-bot backtest --start 2023-02-17 --end 2023-10-30 --symbols BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT --initial-equity 10000.0 --by-month --with-risk --signal trend_filter:inner=grid:inner_anchor_period=200:inner_entry_bps=50:inner_step_bps=25:max_trend_bps=30 --margin-usd 100.0 --leverage 10 --max-notional-account 12500.0 --max-notional-per-symbol 4000.0 --tp-offset-bps 75.0 --daily-loss-limit 5000.0
```

## Summary

```
BACKTEST REPORT
============================================================
trades         : 479
wins           : 479
losses         : 0
win rate       : 100.00%
gross PnL      : +5797.5000 USDT
fees (signed)  : -155.5307 USDT  (negative = rebate)
net PnL        : +5953.0307 USDT
max drawdown   : 1415.6231 USDT
max DD %       : 14.16%
liquidated     : False
near liq       : False
max margin r.  : 0.57%
min liq dist   : 0.00%
worst unreal.  : -1345.9191 USDT
recovery time  : 6110.12 h
open exposure  : 8462.5537 USDT
execution      : naive
exec stats     : accepted=2762 rejected=0 partial=0 cancel_race=0 dust=0 slip_cost=0.0000

Per-symbol PnL:
------------------------------------------------------------
symbol          n    W    L       gross      fees         net
SOLUSDT       147  147    0   1890.0000  -50.5045   1940.5045
XRPUSDT       106  106    0   1252.5000  -33.5023   1286.0022
ETHUSDT        86   86    0   1027.5000  -27.6053   1055.1053
BTCUSDT        53   53    0    615.0000  -16.4940    631.4940
BNBUSDT        49   49    0    517.5000  -13.9112    531.4112
LTCUSDT        38   38    0    495.0000  -13.5135    508.5135

long PnL       : +3052.5000 USDT
short PnL      : +2745.0000 USDT

Final state:
  BTCUSDT: MERGE_PENDING size=0.036048684642617235 bep=27740.2632
  ETHUSDT: MERGE_PENDING size=1.2697376045376356 bep=1575.1286
  SOLUSDT: MERGE_PENDING size=42.47769867722322 bep=23.5418
  XRPUSDT: MERGE_PENDING size=1323.763231178966 bep=0.7554
  BNBUSDT: MERGE_PENDING size=3.293285879279337 bep=303.6481
  LTCUSDT: MERGE_PENDING size=29.92728260568365 bep=100.2430

====================================================================================================================
MONTHLY BREAKDOWN
====================================================================================================================
period      trades   win%       gross      fees         net    roi%       maxDD     dd%
--------------------------------------------------------------------------------------------------------------------
2023-02         69 100.0%      832.50    -23.09      855.59    8.56      301.19    3.01
2023-03        108 100.0%     1320.00    -35.12     1355.12   13.55     1415.62   14.16
2023-04         52 100.0%      562.50    -15.30      577.80    5.78      711.86    7.12
2023-05         17 100.0%      180.00     -4.50      184.50    1.85      497.84    4.98
2023-06         38 100.0%      487.50    -13.10      500.60    5.01      771.38    7.71
2023-07         78 100.0%      997.50    -26.71     1024.21   10.24      393.09    3.93
2023-08         39 100.0%      457.50    -12.00      469.50    4.70     1074.87   10.75
2023-09         20 100.0%      247.50     -6.71      254.21    2.54      546.39    5.46
2023-10         58 100.0%      712.50    -19.01      731.51    7.32      597.82    5.98
--------------------------------------------------------------------------------------------------------------------
TOTAL          479 100.0%     5797.50   -155.53     5953.03   59.53     1415.62   14.16

archive        : data/backtests/runs/20260520T102922176612Z_cli_backtest_d8705b6d6c.json
```

