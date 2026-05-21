# Dashboard Backtest 1779209414

- Started UTC: `2026-05-19T16:50:14.031184+00:00`
- Duration: `85.0s`
- Exit code: `0`
- Signal: ``
- Symbols: `BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, HYPEUSDT, XAUTUSDT`
- Window: `2026-01-01` to `2026-05-19`
- Initial equity: `30000.0`
- Raw log: `logs/dashboard_backtest_1779209414.txt`

## Command

```
uv run trading-bot backtest --start 2026-01-01 --end 2026-05-19 --symbols BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,HYPEUSDT,XAUTUSDT --initial-equity 30000.0 --by-month --with-risk
```

## Summary

```
BACKTEST REPORT
============================================================
trades         : 67
wins           : 67
losses         : 0
win rate       : 100.00%
gross PnL      : +712.8000 USDT
fees (signed)  : -14.8381 USDT  (negative = rebate)
net PnL        : +727.6381 USDT
max drawdown   : 1751.8504 USDT
max DD %       : 5.84%
liquidated     : False
near liq       : False
max margin r.  : 0.16%
min liq dist   : 0.00%
worst unreal.  : -758.8475 USDT
recovery time  : 3306.23 h
open exposure  : 4548.8794 USDT
execution      : naive
exec stats     : accepted=502 rejected=0 partial=0 cancel_race=0 dust=0 slip_cost=0.0000

Per-symbol PnL:
------------------------------------------------------------
symbol          n    W    L       gross      fees         net
XAUTUSDT       22   22    0    237.6000   -4.8127    242.4127
ETHUSDT        13   13    0    171.6000   -3.6260    175.2260
BNBUSDT        15   15    0    138.6000   -2.8426    141.4426
SOLUSDT         7    7    0     72.6000   -1.5807     74.1807
BTCUSDT         5    5    0     52.8000   -1.1180     53.9180
XRPUSDT         5    5    0     39.6000   -0.8580     40.4580

long PnL       : +297.0000 USDT
short PnL      : +415.8000 USDT

Final state:
  BTCUSDT: MERGE_PENDING size=0.007486099992433084 bep=88163.3963
  ETHUSDT: MERGE_PENDING size=0.699087740950067 bep=2832.2625
  SOLUSDT: MERGE_PENDING size=10.301172298503918 bep=128.1408
  XRPUSDT: MERGE_PENDING size=336.37112988769866 bep=1.9621
  BNBUSDT: MERGE_PENDING size=0.7421941835253919 bep=889.2552
  XAUTUSDT: MERGE_PENDING size=0.14439442939855704 bep=4570.8135

====================================================================================================================
MONTHLY BREAKDOWN
====================================================================================================================
period      trades   win%       gross      fees         net    roi%       maxDD     dd%
--------------------------------------------------------------------------------------------------------------------
2026-01         49 100.0%      514.80    -11.02      525.82    1.75      880.11    2.93
2026-02          1 100.0%       19.80     -0.26       20.06    0.07     1304.97    4.35
2026-03          8 100.0%       92.40     -1.84       94.24    0.31      594.38    1.98
2026-04          5 100.0%       39.60     -0.79       40.39    0.13      289.10    0.96
2026-05          4 100.0%       46.20     -0.92       47.12    0.16      440.80    1.47
--------------------------------------------------------------------------------------------------------------------
TOTAL           67 100.0%      712.80    -14.84      727.64    2.43     1304.97    4.35

archive        : data/backtests/runs/20260519T165138575034Z_cli_backtest_b09a7bc7b6.json
```

