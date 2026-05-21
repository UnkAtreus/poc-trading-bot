# XMRUSDT grid50_best Continuation Backtest

Run date: 2026-05-21

Intent: continue the XMRUSDT path after the prior `2022-05-09 -> 2024-11-04` run. The CLI does not seed a backtest from a prior final state, so this was run from the original start date through `2026-05-21` to preserve the stateful path.

Strategy/config: current `grid50_best` config, `--with-risk`, realistic execution, `mainnet-like` profile.

## Commands

Checkpoint rerun:

```bash
uv run python -m bot.main backtest \
  --start 2022-05-09 \
  --end 2024-11-04 \
  --symbols XMRUSDT \
  --by-month \
  --with-risk \
  --kline-workers 1 \
  --execution-model realistic \
  --execution-profile mainnet-like
```

Continuation run:

```bash
uv run python -m bot.main backtest \
  --start 2022-05-09 \
  --end 2026-05-21 \
  --symbols XMRUSDT \
  --by-month \
  --with-risk \
  --kline-workers 1 \
  --execution-model realistic \
  --execution-profile mainnet-like
```

## Checkpoint Result: 2022-05-09 to 2024-11-04

Raw log: `logs/backtest_xmrusdt_grid50_best_2022_05_09_to_2024_11_04_mainnet_like.txt`

Archive: `data/backtests/runs/20260521T025354354214Z_cli_backtest_f7063af022.json`

| Metric | Value |
|---|---:|
| Trades | 1 |
| Wins / Losses | 1 / 0 |
| Win rate | 100.00% |
| Gross PnL | +7.4000 USDT |
| Fees signed | -0.2992 USDT |
| Net PnL | +7.6993 USDT |
| ROI | 0.03% |
| Max DD | 1.84% |
| Worst unrealized | -549.8749 USDT |
| Open exposure | 729.8068 USDT |
| Final state | `MERGE_PENDING size=4.653489535465407 bep=214.9140` |

## Continued Result: 2022-05-09 to 2026-05-21

Raw log: `logs/backtest_xmrusdt_grid50_best_2022_05_09_to_2026_05_21_mainnet_like.txt`

Archive: `data/backtests/runs/20260521T025540476876Z_cli_backtest_e4ff830d5c.json`

| Metric | Value |
|---|---:|
| Trades | 109 |
| Wins / Losses | 109 / 0 |
| Win rate | 100.00% |
| Gross PnL | +1,095.2002 USDT |
| Fees signed | -29.6848 USDT |
| Net PnL | +1,124.8850 USDT |
| ROI | 3.75% |
| Max drawdown | 2,885.5244 USDT |
| Max DD | 9.62% |
| Liquidated | False |
| Near liquidation | False |
| Worst unrealized | -2,884.9785 USDT |
| Open exposure | 1,972.6556 USDT |
| Long PnL | +473.5994 USDT |
| Short PnL | +621.6008 USDT |
| Final state | `MERGE_PENDING size=4.869672350183008 bep=205.3321` |

Execution stats: accepted `515`, rejected `0`, partial `25`, cancel race `0`, dust `0`, slippage cost `29.6848`.

## Monthly PnL Highlights

| Period | Trades | Net | ROI % | MaxDD | DD % |
|---|---:|---:|---:|---:|---:|
| 2022-05 | 1 | +7.70 | 0.03 | 452.09 | 1.51 |
| 2024-12 | 55 | +615.79 | 2.05 | 580.22 | 1.93 |
| 2025-01 | 27 | +227.80 | 0.76 | 333.87 | 1.11 |
| 2025-02 | 3 | +38.20 | 0.13 | 575.38 | 1.92 |
| 2025-03 | 4 | +52.84 | 0.18 | 335.09 | 1.12 |
| 2025-04 | 19 | +182.56 | 0.61 | 570.29 | 1.90 |
| TOTAL | 109 | +1,124.88 | 3.75 | 1,871.85 | 6.24 |

## Notes

- The old cutoff result matches the combined top13 run: XMR had only one closed trade before `2024-11-04` and stayed merge-pending.
- Extending the same stateful path through `2026-05-21` adds most of the realized PnL in `2024-12` through `2025-04`.
- The run still ends with an open merge-pending XMR position.
- Kline loading completed with `48` cached months out of `49`; it fetched missing `2025-12` and topped up `2026-05`.
- No `empty_klines`, traceback, runtime error, CLI error, or rate-limit warning appeared in the continuation log.
