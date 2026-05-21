# Dashboard Backtest 1779295077

- Started UTC: `2026-05-20T16:37:57.056259+00:00`
- Duration: `52.4s`
- Exit code: `1`
- Signal: `rg_trend_grid_a200_e50_s25_t20_ema25_adx25_reduce0_5`
- Full signal: `regime_gate:inner=trend_filter:inner_inner=grid:inner_inner_anchor_period=200:inner_inner_entry_bps=50:inner_inner_step_bps=25:inner_max_trend_bps=20:max_adx=25:max_ema_spread_bps=25:unsafe_action=reduce:unsafe_size_scale=0.5`
- Symbols: `BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, ADAUSDT, UNIUSDT, MATICUSDT, XLMUSDT, LINKUSDT, TRXUSDT`
- Window: `2025-11-20` to `2026-05-20`
- Initial equity: `30000.0`
- Margin / leverage: `100.0` USDT × `10`
- TP / caps: TP `75.0` bps, account cap `12500.0`, symbol cap `4000.0`
- Daily loss limit: `5000.0`
- Raw log: `logs/dashboard_backtest_1779295077.txt`

## Command

```
uv run trading-bot backtest --start 2025-11-20 --end 2026-05-20 --symbols BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,ADAUSDT,UNIUSDT,MATICUSDT,XLMUSDT,LINKUSDT,TRXUSDT --initial-equity 30000.0 --by-month --with-risk --signal regime_gate:inner=trend_filter:inner_inner=grid:inner_inner_anchor_period=200:inner_inner_entry_bps=50:inner_inner_step_bps=25:inner_max_trend_bps=20:max_adx=25:max_ema_spread_bps=25:unsafe_action=reduce:unsafe_size_scale=0.5 --margin-usd 100.0 --leverage 10 --max-notional-account 12500.0 --max-notional-per-symbol 4000.0 --tp-offset-bps 75.0 --daily-loss-limit 5000.0
```

## Summary

```
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1775001600000&end=1775493659999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1775001600000&end=1775433659999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1775001600000&end=1775373659999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1775001600000&end=1775313659999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1775001600000&end=1775253659999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1775001600000&end=1775193659999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1775001600000&end=1775133659999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1775001600000&end=1775073659999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1775001600000&end=1775013659999&limit=1000 "HTTP/1.1 200 OK"
[2m2026-05-20T16:38:46.013055Z[0m [[32m[1minfo     [0m] [1mklines.fetch_month            [0m [36msymbol[0m=[35mUNIUSDT[0m [36mym[0m=[35m2026-05[0m
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1779295126012&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1779235139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1779175139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1779115139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1779055139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1778995139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1778935139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1778875139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1778815139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1778755139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1778695139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1778635139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1778575139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1778515139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1778455139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1778395139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1778335139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1778275139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1778215139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1778155139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1778095139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1778035139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1777975139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1777915139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1777855139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1777795139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1777735139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1777675139999&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNIUSDT&interval=1&start=1777593600000&end=1777615139999&limit=1000 "HTTP/1.1 200 OK"
[2m2026-05-20T16:38:49.348027Z[0m [[32m[1minfo     [0m] [1mklines.range_loaded           [0m [36mcached_months[0m=[35m0[0m [36mend_ms[0m=[35m1779235200000[0m [36mmonths[0m=[35m7[0m [36mstart_ms[0m=[35m1763596800000[0m [36msymbol[0m=[35mUNIUSDT[0m
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
    df = _load_month(cdir, symbol, y, m, testnet=testnet)
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/atreus/Desktop/work/sideproject/poc-trading-bot/src/bot/backtest/downloader.py", line 141, in _load_month
    df = fetch_klines(symbol, start_ms, min(end_ms, now_ms), testnet=testnet)
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/atreus/Desktop/work/sideproject/poc-trading-bot/src/bot/backtest/downloader.py", line 56, in fetch_klines
    raise RuntimeError(f"bybit error: {data}")
RuntimeError: bybit error: {'retCode': 10016, 'retMsg': 'svc error: Get kline failed', 'result': {}, 'retExtInfo': {}, 'time': 1779295080869}
```

