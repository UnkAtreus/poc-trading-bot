# Dashboard Backtest 1778592815

- Started UTC: `2026-05-12T13:33:35.193642+00:00`
- Duration: `11.5s`
- Exit code: `0`
- Signal: ``
- Symbols: `BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, HYPEUSDT, XAUTUSDT`
- Window: `2026-05-01` to `2026-05-12`
- Initial equity: `30000.0`
- Raw log: `logs/dashboard_backtest_1778592815.txt`

## Command

```
uv run trading-bot backtest --start 2026-05-01 --end 2026-05-12 --symbols BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,HYPEUSDT,XAUTUSDT --initial-equity 30000.0 --by-month --with-risk
```

## Summary

```
BACKTEST REPORT
============================================================
trades         : 11
wins           : 11
losses         : 0
win rate       : 100.00%
gross PnL      : +98.2757 USDT
fees (signed)  : -2.5060 USDT  (negative = rebate)
net PnL        : +100.7817 USDT
max drawdown   : 276.8575 USDT
max DD %       : 0.92%
liquidated     : False
near liq       : False
max margin r.  : 0.11%
min liq dist   : 0.00%
worst unreal.  : -112.1684 USDT
recovery time  : 257.23 h
open exposure  : 5611.9450 USDT

Per-symbol PnL:
------------------------------------------------------------
symbol          n    W    L       gross      fees         net
ETHUSDT         3    3    0     33.0000   -0.7267     33.7267
BNBUSDT         4    4    0     33.0000   -0.7240     33.7240
XAUTUSDT        3    3    0     19.0757   -0.5287     19.6044
SOLUSDT         1    1    0     13.2000   -0.3287     13.5287

long PnL       : +38.8757 USDT
short PnL      : +59.4000 USDT

Final state:
  BTCUSDT: MERGE_PENDING size=0.017071928149294587 bep=77319.9130
  ETHUSDT: MERGE_PENDING size=0.2860271622834391 bep=2307.4732
  SOLUSDT: MERGE_PENDING size=7.856021971150902 bep=84.0120
  XRPUSDT: MERGE_PENDING size=479.27213376746676 bep=1.3771
  BNBUSDT: MERGE_PENDING size=1.0597111083012711 bep=622.8112
  XAUTUSDT: MERGE_PENDING size=0.14254508944153618 bep=4630.1139

====================================================================================================================
MONTHLY BREAKDOWN
====================================================================================================================
period      trades   win%       gross      fees         net    roi%       maxDD     dd%
--------------------------------------------------------------------------------------------------------------------
2026-05         11 100.0%       98.28     -2.51      100.78    0.34      276.86    0.92
--------------------------------------------------------------------------------------------------------------------
TOTAL           11 100.0%       98.28     -2.51      100.78    0.34      276.86    0.92
```

