# Top 13 grid50_best Backtest - 2022-05-09 to 2024-11-04

Run date: 2026-05-20

Date interpretation: user input `09-05-2022 -> 04-11-2024` was run as `2022-05-09` to `2024-11-04` UTC.

Symbols:

`BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, LTCUSDT, ADAUSDT, UNIUSDT, MATICUSDT, XLMUSDT, LINKUSDT, TRXUSDT, XMRUSDT`

Command:

```bash
uv run python -m bot.main backtest \
  --start 2022-05-09 \
  --end 2024-11-04 \
  --symbols "BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT,ADAUSDT,UNIUSDT,MATICUSDT,XLMUSDT,LINKUSDT,TRXUSDT,XMRUSDT" \
  --by-month \
  --with-risk \
  --kline-workers 1 \
  --execution-model realistic \
  --execution-profile mainnet-like
```

Raw log: `logs/backtest_top13_grid50_best_2022_05_09_to_2024_11_04_mainnet_like.txt`

Archive: `data/backtests/runs/20260520T173635757734Z_cli_backtest_83b9238517.json`

## Summary

| Metric | Value |
|---|---:|
| Initial equity | 30,000.00 USDT |
| Trades | 1,447 |
| Wins / Losses | 1,447 / 0 |
| Win rate | 100.00% |
| Gross PnL | +10,086.1999 USDT |
| Fees signed | -273.7962 USDT |
| Net PnL | +10,359.9961 USDT |
| ROI | 34.53% |
| Max drawdown | 4,288.5644 USDT |
| Max DD | 14.30% |
| Liquidated | False |
| Near liquidation | False |
| Worst unrealized | -2,366.3079 USDT |
| Final open exposure | 16,182.2290 USDT |
| Long PnL | +5,024.5932 USDT |
| Short PnL | +5,061.6068 USDT |

Execution: realistic, mainnet-like profile. Params: latency `0.3s`, cancel `0.5s`, slippage `1bps`, passive offset `0.2bps`.

Execution stats: accepted `5,210`, rejected `0`, partial `323`, cancel race `0`, dust `0`, slippage cost `273.7963`.

## Per-Symbol PnL

| Symbol | Trades | Wins | Losses | Gross | Fees | Net |
|---|---:|---:|---:|---:|---:|---:|
| MATICUSDT | 260 | 260 | 0 | 1,850.0002 | -50.0863 | 1,900.0865 |
| LTCUSDT | 218 | 218 | 0 | 1,428.2002 | -38.6856 | 1,466.8857 |
| ETHUSDT | 175 | 175 | 0 | 1,406.0001 | -38.0909 | 1,444.0910 |
| UNIUSDT | 166 | 166 | 0 | 1,095.2000 | -29.7015 | 1,124.9015 |
| XLMUSDT | 150 | 150 | 0 | 828.7999 | -22.5046 | 851.3045 |
| BNBUSDT | 115 | 115 | 0 | 814.0000 | -22.1015 | 836.1015 |
| ADAUSDT | 98 | 98 | 0 | 799.2000 | -21.7030 | 820.9030 |
| TRXUSDT | 97 | 97 | 0 | 628.9999 | -17.1099 | 646.1097 |
| XRPUSDT | 62 | 62 | 0 | 488.4000 | -13.3000 | 501.7000 |
| LINKUSDT | 50 | 50 | 0 | 355.2000 | -9.6030 | 364.8030 |
| BTCUSDT | 33 | 33 | 0 | 207.1999 | -5.7061 | 212.9060 |
| SOLUSDT | 22 | 22 | 0 | 177.5999 | -4.9045 | 182.5045 |
| XMRUSDT | 1 | 1 | 0 | 7.4000 | -0.2992 | 7.6993 |

## Monthly Breakdown

| Period | Trades | Win % | Gross | Fees | Net | ROI % | MaxDD | DD % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2022-05 | 130 | 100.0 | 1,191.40 | -33.41 | 1,224.81 | 4.08 | 3,382.84 | 11.28 |
| 2022-06 | 28 | 100.0 | 199.80 | -5.40 | 205.20 | 0.68 | 3,733.35 | 12.44 |
| 2022-07 | 125 | 100.0 | 888.00 | -24.00 | 912.00 | 3.04 | 916.80 | 3.06 |
| 2022-08 | 66 | 100.0 | 414.40 | -11.21 | 425.61 | 1.42 | 1,462.81 | 4.88 |
| 2022-09 | 59 | 100.0 | 325.60 | -8.80 | 334.40 | 1.11 | 1,418.66 | 4.73 |
| 2022-10 | 31 | 100.0 | 192.40 | -5.20 | 197.60 | 0.66 | 1,061.88 | 3.54 |
| 2022-11 | 89 | 100.0 | 717.80 | -19.39 | 737.19 | 2.46 | 1,339.48 | 4.46 |
| 2022-12 | 14 | 100.0 | 103.60 | -2.80 | 106.40 | 0.35 | 1,072.17 | 3.57 |
| 2023-01 | 79 | 100.0 | 562.40 | -15.10 | 577.50 | 1.92 | 535.33 | 1.78 |
| 2023-02 | 38 | 100.0 | 251.60 | -6.90 | 258.50 | 0.86 | 401.66 | 1.34 |
| 2023-03 | 62 | 100.0 | 407.00 | -11.00 | 418.00 | 1.39 | 808.51 | 2.70 |
| 2023-04 | 31 | 100.0 | 192.40 | -5.20 | 197.60 | 0.66 | 379.42 | 1.26 |
| 2023-05 | 15 | 100.0 | 111.00 | -3.00 | 114.00 | 0.38 | 644.88 | 2.15 |
| 2023-06 | 26 | 100.0 | 177.60 | -4.80 | 182.40 | 0.61 | 868.96 | 2.90 |
| 2023-07 | 6 | 100.0 | 37.00 | -1.00 | 38.00 | 0.13 | 790.94 | 2.64 |
| 2023-08 | 51 | 100.0 | 296.00 | -7.90 | 303.90 | 1.01 | 243.12 | 0.81 |
| 2023-09 | 15 | 100.0 | 74.00 | -2.10 | 76.10 | 0.25 | 315.35 | 1.05 |
| 2023-10 | 79 | 100.0 | 407.00 | -11.00 | 418.00 | 1.39 | 322.85 | 1.08 |
| 2023-11 | 62 | 100.0 | 421.80 | -11.41 | 433.21 | 1.44 | 479.14 | 1.60 |
| 2023-12 | 100 | 100.0 | 725.20 | -19.60 | 744.80 | 2.48 | 973.79 | 3.25 |
| 2024-01 | 54 | 100.0 | 347.80 | -9.40 | 357.20 | 1.19 | 621.68 | 2.07 |
| 2024-02 | 69 | 100.0 | 518.00 | -14.00 | 532.00 | 1.77 | 2,769.59 | 9.23 |
| 2024-03 | 163 | 100.0 | 1,184.00 | -31.99 | 1,215.99 | 4.05 | 2,806.00 | 9.35 |
| 2024-04 | 1 | 100.0 | 7.40 | -0.20 | 7.60 | 0.03 | 1,595.23 | 5.32 |
| 2024-05 | 0 | 0.0 | 0.00 | 0.00 | 0.00 | 0.00 | 2,421.39 | 8.07 |
| 2024-06 | 0 | 0.0 | 0.00 | 0.00 | 0.00 | 0.00 | 745.27 | 2.48 |
| 2024-07 | 7 | 100.0 | 51.80 | -1.40 | 53.20 | 0.18 | 2,685.22 | 8.95 |
| 2024-08 | 0 | 0.0 | 0.00 | 0.00 | 0.00 | 0.00 | 2,635.47 | 8.78 |
| 2024-09 | 2 | 100.0 | 14.80 | -0.40 | 15.20 | 0.05 | 1,900.49 | 6.33 |
| 2024-10 | 44 | 100.0 | 259.00 | -7.00 | 266.00 | 0.89 | 1,285.48 | 4.28 |
| 2024-11 | 1 | 100.0 | 7.40 | -0.20 | 7.60 | 0.03 | 323.14 | 1.08 |
| TOTAL | 1,447 | 100.0 | 10,086.20 | -273.80 | 10,360.00 | 34.53 | 3,733.35 | 12.44 |

## Notes

- XMRUSDT was included and returned valid Bybit linear kline data.
- XMRUSDT hit three temporary Bybit rate-limit warnings during download. The retry/backoff logic handled them and the run completed.
- No `empty_klines`, traceback, runtime error, or CLI error appeared in the log.
- Final state retained open merge-pending positions across all symbols, with total open exposure of `16,182.2290 USDT`.
