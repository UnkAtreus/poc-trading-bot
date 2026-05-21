# Dashboard Backtest 1779295017

- Started UTC: `2026-05-20T16:36:57.240291+00:00`
- Duration: `3.1s`
- Exit code: `1`
- Signal: `rg_trend_grid_a200_e50_s25_t20_ema25_adx25_reduce0_5`
- Full signal: `regime_gate:inner=trend_filter:inner_inner=grid:inner_inner_anchor_period=200:inner_inner_entry_bps=50:inner_inner_step_bps=25:inner_max_trend_bps=20:max_adx=25:max_ema_spread_bps=25:unsafe_action=reduce:unsafe_size_scale=0.5`
- Symbols: `BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, ADA, UNI, MATIC, XLM, LINK, TRX`
- Window: `2025-11-20` to `2026-05-20`
- Initial equity: `30000.0`
- Margin / leverage: `100.0` USDT × `10`
- TP / caps: TP `75.0` bps, account cap `12500.0`, symbol cap `4000.0`
- Daily loss limit: `5000.0`
- Raw log: `logs/dashboard_backtest_1779295017.txt`

## Command

```
uv run trading-bot backtest --start 2025-11-20 --end 2026-05-20 --symbols BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,ADA,UNI,MATIC,XLM,LINK,TRX --initial-equity 30000.0 --by-month --with-risk --signal regime_gate:inner=trend_filter:inner_inner=grid:inner_inner_anchor_period=200:inner_inner_entry_bps=50:inner_inner_step_bps=25:inner_max_trend_bps=20:max_adx=25:max_ema_spread_bps=25:unsafe_action=reduce:unsafe_size_scale=0.5 --margin-usd 100.0 --leverage 10 --max-notional-account 12500.0 --max-notional-per-symbol 4000.0 --tp-offset-bps 75.0 --daily-loss-limit 5000.0
```

## Summary

```
[2m2026-05-20T16:36:57.503157Z[0m [[32m[1minfo     [0m] [1mboot.banner                   [0m [36mleverage[0m=[35m10[0m [36mmargin_per_order[0m=[35m100.0[0m [36mmode[0m=[35mtestnet[0m [36msymbols[0m=[35m6[0m
[2m2026-05-20T16:36:57.936264Z[0m [[32m[1minfo     [0m] [1mbacktest.loading              [0m [36msymbol[0m=[35mBTCUSDT[0m
[2m2026-05-20T16:36:57.936437Z[0m [[32m[1minfo     [0m] [1mbacktest.loading              [0m [36msymbol[0m=[35mETHUSDT[0m
[2m2026-05-20T16:36:57.936543Z[0m [[32m[1minfo     [0m] [1mbacktest.loading              [0m [36msymbol[0m=[35mSOLUSDT[0m
[2m2026-05-20T16:36:57.936712Z[0m [[32m[1minfo     [0m] [1mbacktest.loading              [0m [36msymbol[0m=[35mXRPUSDT[0m
[2m2026-05-20T16:36:58.065218Z[0m [[32m[1minfo     [0m] [1mklines.range_loaded           [0m [36mcached_months[0m=[35m7[0m [36mend_ms[0m=[35m1779235200000[0m [36mmonths[0m=[35m7[0m [36mstart_ms[0m=[35m1763596800000[0m [36msymbol[0m=[35mXRPUSDT[0m
[2m2026-05-20T16:36:58.068458Z[0m [[32m[1minfo     [0m] [1mklines.range_loaded           [0m [36mcached_months[0m=[35m7[0m [36mend_ms[0m=[35m1779235200000[0m [36mmonths[0m=[35m7[0m [36mstart_ms[0m=[35m1763596800000[0m [36msymbol[0m=[35mSOLUSDT[0m
[2m2026-05-20T16:36:58.068682Z[0m [[32m[1minfo     [0m] [1mklines.range_loaded           [0m [36mcached_months[0m=[35m7[0m [36mend_ms[0m=[35m1779235200000[0m [36mmonths[0m=[35m7[0m [36mstart_ms[0m=[35m1763596800000[0m [36msymbol[0m=[35mBTCUSDT[0m
[2m2026-05-20T16:36:58.071700Z[0m [[32m[1minfo     [0m] [1mklines.range_loaded           [0m [36mcached_months[0m=[35m7[0m [36mend_ms[0m=[35m1779235200000[0m [36mmonths[0m=[35m7[0m [36mstart_ms[0m=[35m1763596800000[0m [36msymbol[0m=[35mETHUSDT[0m
[2m2026-05-20T16:36:58.482444Z[0m [[32m[1minfo     [0m] [1mbacktest.loading              [0m [36msymbol[0m=[35mBNBUSDT[0m
[2m2026-05-20T16:36:59.734065Z[0m [[32m[1minfo     [0m] [1mbacktest.loading              [0m [36msymbol[0m=[35mADA[0m
[2m2026-05-20T16:36:59.734242Z[0m [[32m[1minfo     [0m] [1mbacktest.loading              [0m [36msymbol[0m=[35mUNI[0m
[2m2026-05-20T16:36:59.734397Z[0m [[32m[1minfo     [0m] [1mbacktest.loading              [0m [36msymbol[0m=[35mMATIC[0m
[2m2026-05-20T16:36:59.734475Z[0m [[32m[1minfo     [0m] [1mklines.fetch_month            [0m [36msymbol[0m=[35mADA[0m [36mym[0m=[35m2025-11[0m
[2m2026-05-20T16:36:59.734582Z[0m [[32m[1minfo     [0m] [1mklines.fetch_month            [0m [36msymbol[0m=[35mUNI[0m [36mym[0m=[35m2025-11[0m
[2m2026-05-20T16:36:59.734642Z[0m [[32m[1minfo     [0m] [1mklines.fetch_month            [0m [36msymbol[0m=[35mMATIC[0m [36mym[0m=[35m2025-11[0m
[2m2026-05-20T16:36:59.736757Z[0m [[32m[1minfo     [0m] [1mklines.range_loaded           [0m [36mcached_months[0m=[35m7[0m [36mend_ms[0m=[35m1779235200000[0m [36mmonths[0m=[35m7[0m [36mstart_ms[0m=[35m1763596800000[0m [36msymbol[0m=[35mBNBUSDT[0m
[2m2026-05-20T16:37:00.118468Z[0m [[32m[1minfo     [0m] [1mbacktest.loading              [0m [36msymbol[0m=[35mXLM[0m
[2m2026-05-20T16:37:00.118664Z[0m [[32m[1minfo     [0m] [1mklines.fetch_month            [0m [36msymbol[0m=[35mXLM[0m [36mym[0m=[35m2025-11[0m
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=UNI&interval=1&start=1761955200000&end=1764547200000&limit=1000 "HTTP/1.1 200 OK"
[2m2026-05-20T16:37:00.191991Z[0m [[32m[1minfo     [0m] [1mbacktest.loading              [0m [36msymbol[0m=[35mLINK[0m
[2m2026-05-20T16:37:00.192188Z[0m [[32m[1minfo     [0m] [1mklines.fetch_month            [0m [36msymbol[0m=[35mLINK[0m [36mym[0m=[35m2025-11[0m
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=XLM&interval=1&start=1761955200000&end=1764547200000&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=MATIC&interval=1&start=1761955200000&end=1764547200000&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=ADA&interval=1&start=1761955200000&end=1764547200000&limit=1000 "HTTP/1.1 200 OK"
HTTP Request: GET https://api.bybit.com/v5/market/kline?category=linear&symbol=LINK&interval=1&start=1761955200000&end=1764547200000&limit=1000 "HTTP/1.1 200 OK"
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
RuntimeError: bybit error: {'retCode': 10001, 'retMsg': 'params error: Symbol Is Invalid', 'result': {}, 'retExtInfo': {}, 'time': 1779295020325}
```

