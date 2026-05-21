# Dashboard Backtest 1779278257

- Started UTC: `2026-05-20T11:57:37.907392+00:00`
- Duration: `250.0s`
- Exit code: `0`
- Signal: `rg_trend_grid_a200_e50_s25_t20_ema25_adx25_reduce0_5`
- Full signal: `regime_gate:inner=trend_filter:inner_inner=grid:inner_inner_anchor_period=200:inner_inner_entry_bps=50:inner_inner_step_bps=25:inner_max_trend_bps=20:max_adx=25:max_ema_spread_bps=25:unsafe_action=reduce:unsafe_size_scale=0.5`
- Symbols: `BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, LTCUSDT`
- Window: `2024-05-20` to `2026-05-20`
- Initial equity: `10000.0`
- Margin / leverage: `100.0` USDT × `10`
- TP / caps: TP `75.0` bps, account cap `12500.0`, symbol cap `4000.0`
- Daily loss limit: `5000.0`
- Raw log: `logs/dashboard_backtest_1779278257.txt`

## Command

```
uv run trading-bot backtest --start 2024-05-20 --end 2026-05-20 --symbols BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT --initial-equity 10000.0 --by-month --with-risk --signal regime_gate:inner=trend_filter:inner_inner=grid:inner_inner_anchor_period=200:inner_inner_entry_bps=50:inner_inner_step_bps=25:inner_max_trend_bps=20:max_adx=25:max_ema_spread_bps=25:unsafe_action=reduce:unsafe_size_scale=0.5 --margin-usd 100.0 --leverage 10 --max-notional-account 12500.0 --max-notional-per-symbol 4000.0 --tp-offset-bps 75.0 --daily-loss-limit 5000.0
```

## Summary

```
BACKTEST REPORT
============================================================
trades         : 1026
wins           : 1026
losses         : 0
win rate       : 100.00%
gross PnL      : +8658.7500 USDT
fees (signed)  : -231.4906 USDT  (negative = rebate)
net PnL        : +8890.2406 USDT
max drawdown   : 4147.6183 USDT
max DD %       : 41.48%
liquidated     : False
near liq       : False
max margin r.  : 0.90%
min liq dist   : 0.00%
worst unreal.  : -4483.6068 USDT
recovery time  : 17514.03 h
open exposure  : 5725.8737 USDT
execution      : naive
exec stats     : accepted=5101 rejected=0 partial=0 cancel_race=0 dust=0 slip_cost=0.0000

Per-symbol PnL:
------------------------------------------------------------
symbol          n    W    L       gross      fees         net
LTCUSDT       358  358    0   3243.7500  -86.6301   3330.3801
SOLUSDT       183  183    0   1597.5000  -42.6978   1640.1977
ETHUSDT       179  179    0   1590.0000  -42.4643   1632.4642
BTCUSDT       103  103    0    828.7500  -22.2011    850.9511
XRPUSDT       102  102    0    731.2500  -19.5899    750.8399
BNBUSDT       101  101    0    667.5000  -17.9075    685.4075

long PnL       : +4282.5000 USDT
short PnL      : +4376.2500 USDT

Final state:
  BTCUSDT: MERGE_PENDING size=0.01450695593304686 bep=68932.4490
  ETHUSDT: MERGE_PENDING size=0.128214032176532 bep=3899.7292
  SOLUSDT: MERGE_PENDING size=6.081156610521163 bep=164.4424
  XRPUSDT: MERGE_PENDING size=1499.4003148440781 bep=0.6669
  BNBUSDT: MERGE_PENDING size=1.7797369121706952 bep=561.8808
  LTCUSDT: MERGE_PENDING size=11.921214605373825 bep=125.8261

====================================================================================================================
MONTHLY BREAKDOWN
====================================================================================================================
period      trades   win%       gross      fees         net    roi%       maxDD     dd%
--------------------------------------------------------------------------------------------------------------------
2024-05         52 100.0%      408.75    -11.35      420.10    4.20      444.17    4.44
2024-06         33 100.0%      225.00     -6.24      231.24    2.31      588.30    5.88
2024-07         56 100.0%      450.00    -11.77      461.77    4.62     1152.90   11.53
2024-08         52 100.0%      390.00    -10.49      400.49    4.00     1202.41   12.02
2024-09         17 100.0%      135.00     -3.60      138.60    1.39      577.76    5.78
2024-10         25 100.0%      150.00     -3.85      153.85    1.54      403.52    4.04
2024-11        130 100.0%     1057.50    -28.44     1085.94   10.86     2215.75   22.16
2024-12         72 100.0%      596.25    -15.90      612.15    6.12     2210.00   22.10
2025-01        119 100.0%     1068.75    -28.45     1097.20   10.97     2306.38   23.06
2025-02        109 100.0%     1065.00    -28.43     1093.43   10.93     1769.24   17.69
2025-03         25 100.0%      195.00     -5.30      200.30    2.00     1642.30   16.42
2025-04         11 100.0%       60.00     -1.60       61.60    0.62     1442.44   14.42
2025-05          0   0.0%        0.00      0.00        0.00    0.00     1041.46   10.41
2025-06          0   0.0%        0.00      0.00        0.00    0.00      842.26    8.42
2025-07         30 100.0%      266.25     -7.21      273.46    2.73     2514.78   25.15
2025-08         99 100.0%      903.75    -24.10      927.85    9.28     1202.19   12.02
2025-09         22 100.0%      153.75     -4.20      157.95    1.58     1825.86   18.26
2025-10         93 100.0%      862.50    -22.85      885.35    8.85     2918.74   29.19
2025-11          5 100.0%       45.00     -1.20       46.20    0.46     1110.79   11.11
2025-12          0   0.0%        0.00      0.00        0.00    0.00      663.92    6.64
2026-01          0   0.0%        0.00      0.00        0.00    0.00     1033.50   10.34
2026-02         46 100.0%      363.75     -9.55      373.30    3.73      423.29    4.23
2026-03         25 100.0%      232.50     -6.15      238.65    2.39      393.65    3.94
2026-04          5 100.0%       30.00     -0.80       30.80    0.31      361.72    3.62
2026-05          0   0.0%        0.00      0.00        0.00    0.00      352.42    3.52
--------------------------------------------------------------------------------------------------------------------
TOTAL         1026 100.0%     8658.75   -231.49     8890.24   88.90     2918.74   29.19

archive        : data/backtests/runs/20260520T120148211880Z_cli_backtest_b4851e3518.json
```

