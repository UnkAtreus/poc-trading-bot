# Dashboard Backtest 1778731164

- Started UTC: `2026-05-14T03:59:24.150606+00:00`
- Duration: `18.8s`
- Exit code: `0`
- Signal: ``
- Symbols: `BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, HYPEUSDT, XAUTUSDT`
- Window: `2026-01-01` to `2026-02-01`
- Initial equity: `30000.0`
- Raw log: `logs/dashboard_backtest_1778731164.txt`

## Command

```
uv run trading-bot backtest --start 2026-01-01 --end 2026-02-01 --symbols BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,HYPEUSDT,XAUTUSDT --initial-equity 30000.0 --by-month --with-risk
```

## Summary

```
BACKTEST REPORT
============================================================
trades         : 49
wins           : 49
losses         : 0
win rate       : 100.00%
gross PnL      : +514.8000 USDT
fees (signed)  : -11.0194 USDT  (negative = rebate)
net PnL        : +525.8194 USDT
max drawdown   : 880.1123 USDT
max DD %       : 2.93%
liquidated     : False
near liq       : False
max margin r.  : 0.16%
min liq dist   : 0.00%
worst unreal.  : -468.5283 USDT
recovery time  : 738.23 h
open exposure  : 6623.4972 USDT

Per-symbol PnL:
------------------------------------------------------------
symbol          n    W    L       gross      fees         net
ETHUSDT        13   13    0    171.6000   -3.6260    175.2260
BNBUSDT        15   15    0    138.6000   -2.8426    141.4426
SOLUSDT         7    7    0     72.6000   -1.5807     74.1807
BTCUSDT         5    5    0     52.8000   -1.1180     53.9180
XAUTUSDT        4    4    0     39.6000   -0.9940     40.5940
XRPUSDT         5    5    0     39.6000   -0.8580     40.4580

long PnL       : +244.2000 USDT
short PnL      : +270.6000 USDT

Final state:
  BTCUSDT: MERGE_PENDING size=0.007486099992433084 bep=88163.3963
  ETHUSDT: MERGE_PENDING size=0.699087740950067 bep=2832.2625
  SOLUSDT: MERGE_PENDING size=10.301172298503918 bep=128.1408
  XRPUSDT: MERGE_PENDING size=336.37112988769866 bep=1.9621
  BNBUSDT: MERGE_PENDING size=0.7421941835253919 bep=889.2552
  XAUTUSDT: MERGE_PENDING size=0.43678480986122314 bep=4533.1247

====================================================================================================================
MONTHLY BREAKDOWN
====================================================================================================================
period      trades   win%       gross      fees         net    roi%       maxDD     dd%
--------------------------------------------------------------------------------------------------------------------
2026-01         49 100.0%      514.80    -11.02      525.82    1.75      880.11    2.93
--------------------------------------------------------------------------------------------------------------------
TOTAL           49 100.0%      514.80    -11.02      525.82    1.75      880.11    2.93
```

