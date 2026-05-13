# Dashboard Backtest 1778593460

- Started UTC: `2026-05-12T13:44:20.869189+00:00`
- Duration: `31.1s`
- Exit code: `0`
- Signal: ``
- Symbols: `BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, HYPEUSDT, XAUTUSDT`
- Window: `2026-02-01` to `2026-05-01`
- Initial equity: `30000.0`
- Raw log: `logs/dashboard_backtest_1778593460.txt`

## Command

```
uv run trading-bot backtest --start 2026-02-01 --end 2026-05-01 --symbols BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,HYPEUSDT,XAUTUSDT --initial-equity 30000.0 --by-month --with-risk
```

## Summary

```
BACKTEST REPORT
============================================================
trades         : 55
wins           : 55
losses         : 0
win rate       : 100.00%
gross PnL      : +681.3110 USDT
fees (signed)  : -15.0553 USDT  (negative = rebate)
net PnL        : +696.3663 USDT
max drawdown   : 1423.3765 USDT
max DD %       : 4.74%
liquidated     : False
near liq       : False
max margin r.  : 0.19%
min liq dist   : 0.00%
worst unreal.  : -698.6608 USDT
recovery time  : 2131.08 h
open exposure  : 8434.9014 USDT

Per-symbol PnL:
------------------------------------------------------------
symbol          n    W    L       gross      fees         net
XAUTUSDT       24   24    0    291.9110   -6.6079    298.5190
XRPUSDT        19   19    0    224.4000   -4.6134    229.0134
BTCUSDT         6    6    0     85.8000   -1.7853     87.5853
SOLUSDT         5    5    0     72.6000   -1.6520     74.2520
ETHUSDT         1    1    0      6.6000   -0.3307      6.9307

long PnL       : +372.1322 USDT
short PnL      : +309.1788 USDT

Final state:
  BTCUSDT: MERGE_PENDING size=0.00844971688513032 bep=78109.1259
  ETHUSDT: MERGE_PENDING size=0.8150782991454637 bep=2429.2145
  SOLUSDT: MERGE_PENDING size=18.9659447576819 bep=104.3976
  XRPUSDT: MERGE_PENDING size=895.6374421476394 bep=1.4738
  BNBUSDT: MERGE_PENDING size=0.8458180672249792 bep=780.3097
  XAUTUSDT: MERGE_PENDING size=0.4300487044555998 bep=4604.1297

====================================================================================================================
MONTHLY BREAKDOWN
====================================================================================================================
period      trades   win%       gross      fees         net    roi%       maxDD     dd%
--------------------------------------------------------------------------------------------------------------------
2026-02         26 100.0%      402.60     -8.79      411.39    1.37     1423.38    4.74
2026-03         11 100.0%      138.60     -2.64      141.24    0.47      591.07    1.97
2026-04         18 100.0%      140.11     -3.63      143.74    0.48      464.16    1.55
--------------------------------------------------------------------------------------------------------------------
TOTAL           55 100.0%      681.31    -15.06      696.37    2.32     1423.38    4.74
```

