# Dashboard Backtest 1779295097

- Started UTC: `2026-05-20T16:38:17.063492+00:00`
- Duration: `226.5s`
- Exit code: `1`
- Signal: `rg_trend_grid_a200_e50_s25_t20_ema25_adx25_reduce0_5`
- Full signal: `regime_gate:inner=trend_filter:inner_inner=grid:inner_inner_anchor_period=200:inner_inner_entry_bps=50:inner_inner_step_bps=25:inner_max_trend_bps=20:max_adx=25:max_ema_spread_bps=25:unsafe_action=reduce:unsafe_size_scale=0.5`
- Symbols: `BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, ADAUSDT, UNIUSDT, MATICUSDT, XLMUSDT, LINKUSDT, TRXUSDT`
- Window: `2024-05-20` to `2026-05-20`
- Initial equity: `30000.0`
- Margin / leverage: `100.0` USDT × `10`
- TP / caps: TP `75.0` bps, account cap `12500.0`, symbol cap `4000.0`
- Daily loss limit: `5000.0`
- Raw log: `logs/dashboard_backtest_1779295097.txt`

## Command

```
uv run trading-bot backtest --start 2024-05-20 --end 2026-05-20 --symbols BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,ADAUSDT,UNIUSDT,MATICUSDT,XLMUSDT,LINKUSDT,TRXUSDT --initial-equity 30000.0 --by-month --with-risk --signal regime_gate:inner=trend_filter:inner_inner=grid:inner_inner_anchor_period=200:inner_inner_entry_bps=50:inner_inner_step_bps=25:inner_max_trend_bps=20:max_adx=25:max_ema_spread_bps=25:unsafe_action=reduce:unsafe_size_scale=0.5 --margin-usd 100.0 --leverage 10 --max-notional-account 12500.0 --max-notional-per-symbol 4000.0 --tp-offset-bps 75.0 --daily-loss-limit 5000.0
```

## Summary

```
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1761475259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1761415259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1761355259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1761295259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1761235259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1761175259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1761115259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1761055259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1760995259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1760935259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1760875259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1760815259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1760755259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1760695259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1760635259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1760575259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1760515259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1760455259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1760395259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1760335259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1760275259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1760215259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1760155259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1760095259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1760035259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1759975259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1759915259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1759855259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1759795259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1759735259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1759675259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1759615259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1759555259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1759495259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1759435259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1759375259999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1759276800000&end=1759315259999&limit=1000 "HTTP/1.1 200 OK"
[2m2026-05-20T16:42:02.772158Z[0m [[32m[1minfo     [0m] [1mklines.topup                  [0m [36mlatest_ts[0m=[35m1779295080000[0m [36mnow_ms[0m=[35m1779295322758[0m [36msymbol[0m=[35mTRXUSDT[0m [36mym[0m=[35m2026-05[0m
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=TRXUSDT&interval=1&start=1779295080001&end=1779295322758&limit=1000 "HTTP/1.1 200 OK"
[2m2026-05-20T16:42:02.888684Z[0m [[32m[1minfo     [0m] [1mklines.range_loaded           [0m [36mcached_months[0m=[35m7[0m [36mend_ms[0m=[35m1779235200000[0m [36mmonths[0m=[35m25[0m [36mstart_ms[0m=[35m1716163200000[0m [36msymbol[0m=[35mTRXUSDT[0m
Traceback (most recent call last):
  File "/Users/atreus/Desktop/work/sideproject/poc-trading-bot/.venv/bin/trading-bot", line 10, in <module>
    sys.exit(cli())
             ^^^^^
  File "/Users/atreus/Desktop/work/sideproject/poc-trading-bot/src/bot/main.py", line 1195, in cli
    return asyncio.run(_cmd_backtest(args, settings))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/atreus/.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/asyncio/runners.py", line 190, in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
  File "/Users/atreus/.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/asyncio/runners.py", line 118, in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/atreus/.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/asyncio/base_events.py", line 654, in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
  File "/Users/atreus/Desktop/work/sideproject/poc-trading-bot/src/bot/main.py", line 69, in _cmd_backtest
    candles = await _load_candles_by_symbol(args, settings, log_event="backtest.loading")
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/atreus/Desktop/work/sideproject/poc-trading-bot/src/bot/main.py", line 57, in _load_candles_by_symbol
    loaded = await asyncio.gather(*(load_one(sym) for sym in syms))
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/atreus/Desktop/work/sideproject/poc-trading-bot/src/bot/main.py", line 48, in load_one
    df = await asyncio.to_thread(
         ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/atreus/.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/asyncio/threads.py", line 25, in to_thread
    return await loop.run_in_executor(None, func_call)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/atreus/.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/concurrent/futures/thread.py", line 58, in run
    result = self.fn(*self.args, **self.kwargs)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/atreus/Desktop/work/sideproject/poc-trading-bot/src/bot/backtest/downloader.py", line 168, in load_or_fetch
    
  File "/Users/atreus/Desktop/work/sideproject/poc-trading-bot/src/bot/backtest/downloader.py", line 141, in _load_month
    start_ms, end_ms = _month_bounds_ms(year, month)
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/atreus/Desktop/work/sideproject/poc-trading-bot/src/bot/backtest/downloader.py", line 56, in fetch_klines
    retries = 0
        ^^^^^^^^
RuntimeError: bybit error: {'retCode': 10006, 'retMsg': 'Too many visits. Exceeded the API Rate Limit.', 'result': {}, 'retExtInfo': {}, 'time': 1779295209386}
```

