# Recommended8 grid50_best Full Backtest

Run date: 2026-05-21

Profile: `config/profiles/recommended8_grid50_best.yaml`

Window: `2022-05-09` to `2026-05-21` UTC

Symbols:

`UNIUSDT, ETHUSDT, XLMUSDT, LTCUSDT, SOLUSDT, BNBUSDT, XRPUSDT, LINKUSDT`

Command:

```bash
uv run python -m bot.main backtest \
  --start 2022-05-09 \
  --end 2026-05-21 \
  --symbols "UNIUSDT,ETHUSDT,XLMUSDT,LTCUSDT,SOLUSDT,BNBUSDT,XRPUSDT,LINKUSDT" \
  --by-month \
  --with-risk \
  --kline-workers 1 \
  --execution-model realistic \
  --execution-profile mainnet-like
```

Raw log: `logs/backtest_recommended8_grid50_best_2022_05_09_to_2026_05_21_mainnet_like.txt`

Archive: `data/backtests/runs/20260521T053444361874Z_cli_backtest_f27354ef17.json`

## Summary

| Metric | Value |
|---|---:|
| Initial equity | 30,000.00 USDT |
| Trades | 1,901 |
| Wins / Losses | 1,901 / 0 |
| Win rate | 100.00% |
| Gross PnL | +17,243.8787 USDT |
| Fees signed | -467.4640 USDT |
| Net PnL | +17,711.3426 USDT |
| ROI | 59.04% |
| Max drawdown | 10,873.6159 USDT |
| Max DD | 36.25% |
| Liquidated | False |
| Near liquidation | False |
| Worst unrealized | -6,263.8776 USDT |
| Final open exposure | 8,958.8353 USDT |
| Long PnL | +8,923.5959 USDT |
| Short PnL | +8,320.2828 USDT |

Execution: realistic, `mainnet-like`. Params: latency `0.3s`, cancel `0.5s`, slippage `1bps`, passive offset `0.2bps`.

Execution stats: accepted `8,389`, rejected `2`, partial `577`, cancel race `0`, dust `2`, slippage cost `467.4641`.

## Safety Gate Check

This profile is profitable, but it fails the current optimizer safety gates in `config/bot.yaml`:

| Gate | Limit | Result | Pass |
|---|---:|---:|---|
| Max drawdown % | 25.00% | 36.25% | No |
| Final open exposure | 5,000.00 USDT | 8,958.8353 USDT | No |
| Liquidated | false required | false | Yes |
| Near liquidation | false required | false | Yes |

Conclusion: good research candidate, not clean enough for live sizing under current safety gates without reducing exposure or adding stronger stops.

## Per-Symbol PnL

| Symbol | Trades | Wins | Losses | Gross | Fees | Net |
|---|---:|---:|---:|---:|---:|---:|
| XRPUSDT | 438 | 438 | 0 | 4,034.8844 | -109.5496 | 4,144.4339 |
| UNIUSDT | 438 | 438 | 0 | 3,885.0000 | -105.1008 | 3,990.1007 |
| ETHUSDT | 307 | 307 | 0 | 2,804.5997 | -75.9236 | 2,880.5232 |
| LINKUSDT | 226 | 226 | 0 | 2,212.6003 | -59.9780 | 2,272.5782 |
| LTCUSDT | 187 | 187 | 0 | 1,516.9947 | -40.9931 | 1,557.9878 |
| XLMUSDT | 128 | 128 | 0 | 1,309.7997 | -35.6190 | 1,345.4188 |
| BNBUSDT | 96 | 96 | 0 | 769.6000 | -20.9015 | 790.5015 |
| SOLUSDT | 81 | 81 | 0 | 710.4000 | -19.3985 | 729.7985 |

## Final State

| Symbol | State |
|---|---|
| UNIUSDT | `MERGE_PENDING size=138.6118384767335 bep=7.2151` |
| ETHUSDT | `MERGE_PENDING size=0.4263162324499063 bep=2345.9111` |
| XLMUSDT | `MERGE_PENDING size=6055.481718026995 bep=0.3303` |
| LTCUSDT | `DUST_STRANDED size=0.00865457179552842 bep=83.9636` |
| SOLUSDT | `MERGE_PENDING size=25.031358532183894 bep=79.8918` |
| BNBUSDT | `MERGE_PENDING size=3.0375330493088053 bep=329.1816` |
| XRPUSDT | `MERGE_PENDING size=1118.1342989988393 bep=0.8943` |
| LINKUSDT | `MERGE_PENDING size=106.45606284091893 bep=18.7890` |

## Monthly Risk Highlights

| Period | Net | ROI % | MaxDD | DD % | Note |
|---|---:|---:|---:|---:|---|
| 2024-11 | +615.91 | 2.05 | 7,429.71 | 24.77 | Near safety threshold |
| 2025-07 | +114.96 | 0.38 | 9,407.63 | 31.36 | Worst monthly DD |
| 2025-08 | 0.00 | 0.00 | 6,199.02 | 20.66 | No closed trades, high DD |
| 2025-01 | 0.00 | 0.00 | 5,501.60 | 18.34 | No closed trades, high DD |
| 2024-05 | 0.00 | 0.00 | 5,051.71 | 16.84 | No closed trades, high DD |
| 2024-02 | +205.21 | 0.68 | 4,804.78 | 16.02 | High DD |

## Monthly Totals

| Period | Trades | Net | ROI % | MaxDD | DD % |
|---|---:|---:|---:|---:|---:|
| 2022-05 | 99 | +1,131.58 | 3.77 | 2,162.14 | 7.21 |
| 2022-06 | 0 | 0.00 | 0.00 | 3,319.48 | 11.06 |
| 2022-07 | 51 | +585.21 | 1.95 | 1,079.56 | 3.60 |
| 2022-08 | 9 | +91.10 | 0.30 | 1,570.77 | 5.24 |
| 2022-09 | 62 | +600.31 | 2.00 | 1,236.99 | 4.12 |
| 2022-10 | 34 | +288.89 | 0.96 | 603.98 | 2.01 |
| 2022-11 | 141 | +1,311.52 | 4.37 | 1,795.63 | 5.99 |
| 2022-12 | 35 | +243.19 | 0.81 | 1,036.59 | 3.46 |
| 2023-01 | 77 | +706.61 | 2.36 | 316.20 | 1.05 |
| 2023-02 | 18 | +152.10 | 0.51 | 538.55 | 1.80 |
| 2023-03 | 81 | +820.81 | 2.74 | 746.65 | 2.49 |
| 2023-04 | 71 | +615.49 | 2.05 | 377.36 | 1.26 |
| 2023-05 | 43 | +340.98 | 1.14 | 616.01 | 2.05 |
| 2023-06 | 96 | +715.43 | 2.38 | 988.68 | 3.30 |
| 2023-07 | 64 | +593.10 | 1.98 | 584.76 | 1.95 |
| 2023-08 | 47 | +425.29 | 1.42 | 792.63 | 2.64 |
| 2023-09 | 22 | +98.80 | 0.33 | 511.60 | 1.71 |
| 2023-10 | 63 | +683.99 | 2.28 | 692.77 | 2.31 |
| 2023-11 | 53 | +425.90 | 1.42 | 797.97 | 2.66 |
| 2023-12 | 39 | +303.91 | 1.01 | 1,798.99 | 6.00 |
| 2024-01 | 46 | +326.91 | 1.09 | 971.20 | 3.24 |
| 2024-02 | 19 | +205.21 | 0.68 | 4,804.78 | 16.02 |
| 2024-03 | 81 | +721.82 | 2.41 | 3,892.53 | 12.98 |
| 2024-04 | 0 | 0.00 | 0.00 | 2,573.21 | 8.58 |
| 2024-05 | 0 | 0.00 | 0.00 | 5,051.71 | 16.84 |
| 2024-06 | 0 | 0.00 | 0.00 | 1,981.68 | 6.61 |
| 2024-07 | 12 | +106.30 | 0.35 | 2,018.52 | 6.73 |
| 2024-08 | 102 | +1,033.59 | 3.45 | 544.28 | 1.81 |
| 2024-09 | 25 | +212.46 | 0.71 | 656.13 | 2.19 |
| 2024-10 | 33 | +266.05 | 0.89 | 890.52 | 2.97 |
| 2024-11 | 50 | +615.91 | 2.05 | 7,429.71 | 24.77 |
| 2024-12 | 0 | 0.00 | 0.00 | 4,612.63 | 15.38 |
| 2025-01 | 0 | 0.00 | 0.00 | 5,501.60 | 18.34 |
| 2025-02 | 10 | +53.20 | 0.18 | 4,889.04 | 16.30 |
| 2025-03 | 16 | +220.39 | 0.73 | 2,818.69 | 9.40 |
| 2025-04 | 62 | +592.79 | 1.98 | 2,060.86 | 6.87 |
| 2025-05 | 64 | +501.81 | 1.67 | 3,115.96 | 10.39 |
| 2025-06 | 69 | +584.13 | 1.95 | 3,106.72 | 10.36 |
| 2025-07 | 12 | +114.96 | 0.38 | 9,407.63 | 31.36 |
| 2025-08 | 0 | 0.00 | 0.00 | 6,199.02 | 20.66 |
| 2025-09 | 0 | 0.00 | 0.00 | 3,360.79 | 11.20 |
| 2025-10 | 105 | +1,147.69 | 3.83 | 3,779.36 | 12.60 |
| 2025-11 | 13 | +151.80 | 0.51 | 1,104.82 | 3.68 |
| 2025-12 | 0 | 0.00 | 0.00 | 595.12 | 1.98 |
| 2026-01 | 1 | +7.80 | 0.03 | 735.95 | 2.45 |
| 2026-02 | 33 | +349.59 | 1.17 | 229.94 | 0.77 |
| 2026-03 | 0 | 0.00 | 0.00 | 215.53 | 0.72 |
| 2026-04 | 30 | +266.00 | 0.89 | 199.29 | 0.66 |
| 2026-05 | 13 | +98.70 | 0.33 | 333.38 | 1.11 |
| TOTAL | 1,901 | +17,711.34 | 59.04 | 9,407.63 | 31.36 |

## Notes

- All eight symbols loaded with 49 cached months.
- No `empty_klines`, rate-limit warning, traceback, runtime error, or CLI error appeared in the log.
- The command used `--symbols` for the recommended 8 basket. The boot banner still showed the configured default symbol count from `config/symbols.yaml`, which was not changed.
