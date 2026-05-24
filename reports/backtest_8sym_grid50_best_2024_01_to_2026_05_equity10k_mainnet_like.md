# 8-sym grid50_best @ $10k equity — full 2024-01 → 2026-05 mainnet-like

Run date: 2026-05-24

Window: `2024-01-01` to `2026-05-24` UTC (~29 months)

Symbols (active set after 2026-05-24 swap):

`UNIUSDT, ETHUSDT, XLMUSDT, LTCUSDT, SOLUSDT, BNBUSDT, XRPUSDT, LINKUSDT`

Strategy: `trend_filter` wrapping `grid` (inner_anchor_period=200, inner_entry_bps=50, inner_step_bps=25, max_trend_bps=20). TP 75 bps.

Sizing: scaled down from the 30k-equity baseline per `equity / 30000` ratio so the strategy's risk profile is preserved.

| Knob | Baseline (30k) | This run (10k) |
|---|---:|---:|
| margin_usd | 100 | **33** |
| leverage | 10 | 10 |
| max_notional_per_symbol_usd | 4,000 | **1,333** |
| max_notional_account_usd | 12,500 | **4,167** |
| daily_loss_limit_usd | 5,000 | **1,667** |
| Notional per order | 1,000 | **330** |

Command:

```bash
uv run python -m bot.main backtest \
  --start 2024-01-01 --end 2026-05-24 \
  --symbols UNIUSDT,ETHUSDT,XLMUSDT,LTCUSDT,SOLUSDT,BNBUSDT,XRPUSDT,LINKUSDT \
  --by-month --with-risk --kline-workers 8 \
  --signal "trend_filter:inner=grid:inner_anchor_period=200:inner_entry_bps=50:inner_step_bps=25:max_trend_bps=20" \
  --tp-offset-bps 75 \
  --margin-usd 33 --leverage 10 \
  --max-notional-per-symbol 1333 --max-notional-account 4167 \
  --daily-loss-limit 1667 \
  --initial-equity 10000 \
  --execution-model realistic --execution-profile mainnet-like
```

Raw log: `/tmp/bt_8sym_10k_mainnet_like.txt`

Archive: `data/backtests/runs/20260524T074156575669Z_cli_backtest_c6e04c3d1b.json`

## Summary (mainnet-like execution)

| Metric | Value |
|---|---:|
| Initial equity | 10,000.00 USDT |
| Trades | 1,474 |
| Wins / Losses | 1,474 / 0 |
| Win rate | 100.00% |
| Gross PnL | +4,493.16 USDT |
| Fees (signed) | -121.82 USDT |
| Net PnL | **+4,614.98 USDT** |
| ROI | **46.15%** |
| Annualized ROI | ~19.1% |
| Max drawdown (USDT) | 2,045.05 |
| Max drawdown % | **20.45%** |
| Worst monthly DD | **17.27%** (2024-11) |
| Worst unrealized | -1,479.62 USDT |
| Liquidated | False |
| Near liquidation | False |
| Max margin ratio | 0.41% |
| Final open exposure | 3,309.05 USDT |
| Long PnL | +2,252.23 USDT |
| Short PnL | +2,241.93 USDT |

Execution params: latency `0.30s`, cancel delay `0.50s`, slippage `1 bps`, pass-through `0.2 bps`, full-fill `1 bps`, min partial fill `50%`.

Execution stats: accepted `6,358`, rejected `2`, partial `359` (5.6%), cancel race `0`, dust `2`, slippage cost `121.82 USDT`.

## Naive vs mainnet-like

| Metric | Naive | Mainnet-like | Δ |
|---|---:|---:|---:|
| Trades | 1,384 | 1,474 | +6.5% |
| Net PnL | +4,924.85 | +4,614.98 | -310 (-6.3%) |
| ROI | 49.25% | 46.15% | -3.10 pp |
| Max DD % | 20.53% | 20.45% | -0.08 pp |
| Worst monthly DD | 17.18% | 17.27% | +0.09 pp |
| Slippage cost | 0 | 121.82 | — |
| Partial fills | 0 | 359 | — |

**Read:** realism costs ~3 pp ROI (essentially the slippage line). Risk profile is unchanged. Strategy is execution-robust.

## Per-symbol PnL (mainnet-like)

| Symbol | Trades | Net (USDT) | Share |
|---|---:|---:|---:|
| LTCUSDT | 476 | 1,525.98 | 33.1% |
| UNIUSDT | 240 | 807.55 | 17.5% |
| ETHUSDT | 222 | 664.60 | 14.4% |
| LINKUSDT | 173 | 570.81 | 12.4% |
| XLMUSDT | 140 | 403.88 | 8.8% |
| SOLUSDT | 131 | 396.30 | 8.6% |
| XRPUSDT | 75 | 195.66 | 4.2% |
| BNBUSDT | 17 | 50.19 | 1.1% |

LTC remains the workhorse (one-third of all PnL). BNB is dead weight (1% contribution). UNI/LINK/XLM are well-placed additions.

## Monthly breakdown

| Period | Trades | Net | ROI% | Max DD | DD% |
|---|---:|---:|---:|---:|---:|
| 2024-01 | 130 | +381.44 | 3.81 | 254.49 | 2.54 |
| 2024-02 | 126 | +361.31 | 3.61 | 428.40 | 4.28 |
| 2024-03 | 156 | +431.39 | 4.31 | 1,083.77 | 10.84 |
| 2024-04 | 57 | +185.56 | 1.86 | 282.76 | 2.83 |
| 2024-05 | 4 | +17.59 | 0.18 | 657.16 | 6.57 |
| 2024-06 | 16 | +47.62 | 0.48 | 180.87 | 1.81 |
| 2024-07 | 0 | 0.00 | 0.00 | 458.70 | 4.59 |
| 2024-08 | 71 | +245.78 | 2.46 | 134.74 | 1.35 |
| 2024-09 | 17 | +37.54 | 0.38 | 102.36 | 1.02 |
| 2024-10 | 22 | +52.68 | 0.53 | 260.48 | 2.60 |
| **2024-11** | **76** | **+270.93** | **2.71** | **1,727.32** | **17.27** ⚠ |
| 2024-12 | 93 | +368.64 | 3.69 | 1,107.66 | 11.08 |
| 2025-01 | 107 | +373.61 | 3.74 | 1,362.92 | 13.63 |
| 2025-02 | 94 | +366.16 | 3.66 | 935.29 | 9.35 |
| 2025-03 | 16 | +60.26 | 0.60 | 827.85 | 8.28 |
| 2025-04 | 0 | 0.00 | 0.00 | 729.62 | 7.30 |
| 2025-05 | 30 | +92.80 | 0.93 | 416.92 | 4.17 |
| 2025-06 | 37 | +112.51 | 1.13 | 382.85 | 3.83 |
| **2025-07** | **22** | **+68.03** | **0.68** | **1,657.83** | **16.58** ⚠ |
| 2025-08 | 72 | +193.08 | 1.93 | 1,064.53 | 10.65 |
| 2025-09 | 38 | +95.37 | 0.95 | 907.66 | 9.08 |
| 2025-10 | 49 | +150.45 | 1.50 | 1,338.73 | 13.39 |
| 2025-11 | 0 | 0.00 | 0.00 | 519.66 | 5.20 |
| 2025-12 | 0 | 0.00 | 0.00 | 325.05 | 3.25 |
| 2026-01 | 1 | +2.51 | 0.03 | 488.41 | 4.88 |
| 2026-02 | 98 | +298.39 | 2.98 | 249.57 | 2.50 |
| 2026-03 | 83 | +258.39 | 2.58 | 91.66 | 0.92 |
| 2026-04 | 42 | +87.70 | 0.88 | 66.91 | 0.67 |
| 2026-05 | 17 | +55.24 | 0.55 | 225.98 | 2.26 |

## Safety gate check

| Gate | Limit | Result | Pass |
|---|---:|---:|:---:|
| reject_liquidated | true | False | ✅ |
| reject_near_liquidation | true | False | ✅ |
| max_drawdown_pct | 25% | 20.45% | ✅ |
| max_final_open_exposure_usd | 5,000 | 3,309 | ✅ |
| daily_loss_limit_usd | 1,667 | not breached | ✅ |

All optimizer safety gates pass at this equity scale.

## Caveats

- 8 symbols still in `MERGE_PENDING` at end-of-window — net PnL counts only realized trades. Open exposure of $3,309 is roughly 33% of starting equity.
- Two stress months bracket the year: 2024-11 (17.27% DD, post-election rally) and 2025-07 (16.58% DD). Both recovered.
- Single-account, no funding fees, no partial-fill modeling for thin books (caveats from `CLAUDE.md`).
- Mainnet-like profile uses local Bybit-mainnet latency measurements as documented in `src/bot/backtest/execution.py`. Conservative profile run (separate report) bumps latency to 1s, slippage to 2 bps.

## Decision

This is the validation run for the **8-symbol portfolio swap committed 2026-05-24** (BTC dropped, UNI/XLM/LINK added). The strategy holds up under mainnet-like execution with ROI/DD = **2.26** (vs 1.78 for the prior 6-symbol baseline at 30k equity). $10k is the practical minimum equity that keeps the historical max DD inside the 25% safety gate after proportional sizing.

---

## Pessimistic stress: conservative execution profile

Same config re-run with the conservative profile to stress-test under harsher assumptions: 1s latency, 3s cancel delay, 2 bps slippage, 1 bps pass-through, 5 bps full-fill, 25% min partial fill.

Raw log: `/tmp/bt_8sym_10k_conservative.txt`

Archive: `data/backtests/runs/20260524T075135332445Z_cli_backtest_cc239fc8e3.json`

### Summary (conservative execution)

| Metric | Value |
|---|---:|
| Trades | 1,719 |
| Win rate | 100.00% |
| Net PnL | **+3,226.79 USDT** |
| ROI | **32.27%** |
| Annualized ROI | ~13.4% |
| Max drawdown (USDT) | 3,092.99 |
| Max drawdown % | **30.93% ⚠** |
| Worst monthly DD | **29.67%** (2024-11) ⚠ |
| Worst unrealized | -2,446.37 USDT |
| Liquidated | False |
| Near liquidation | False |
| Max margin ratio | 0.53% |
| Final open exposure | 2,985.91 USDT |
| Slippage cost | 172.82 USDT |
| Partial fills | **1,864 (33.5% of orders)** |
| Cancel race | 2 |
| Dust | 5 |
| Rejected | 5 |

### Profile comparison

| Metric | Naive | Mainnet-like | **Conservative** |
|---|---:|---:|---:|
| Trades | 1,384 | 1,474 | 1,719 |
| Net PnL | +4,924.85 | +4,614.98 | **+3,226.79** |
| ROI | 49.25% | 46.15% | **32.27%** |
| Max DD % | 20.53% | 20.45% | **30.93%** |
| Worst monthly DD | 17.18% | 17.27% | **29.67%** |
| Partial fills | 0 | 359 | **1,864** |
| Slippage cost | 0 | 121.82 | 172.82 |
| ROI/DD ratio | 2.40 | 2.26 | **1.04** |

### Per-symbol PnL (conservative)

| Symbol | Trades | Net (USDT) |
|---|---:|---:|
| UNIUSDT | 379 | 747.53 |
| LTCUSDT | 386 | 715.27 |
| ETHUSDT | 336 | 690.56 |
| SOLUSDT | 186 | 376.27 |
| XLMUSDT | 198 | 284.69 |
| XRPUSDT | 108 | 199.63 |
| LINKUSDT | 91 | 163.31 |
| BNBUSDT | 35 | 49.53 |

Notable: under conservative execution, LTC drops from #1 to #2 (UNI takes top). LINK collapses to 91 trades / $163 (vs 173 / $571 under mainnet-like) — likely because LINK relies on tighter fills that the slower cancel delay eats.

### Worst stress months

| Period | Trades | Net | DD% |
|---|---:|---:|---:|
| **2024-11** | 89 | +244.36 | **29.67% ⚠** |
| **2025-07** | 21 | +33.31 | **23.69%** |
| **2025-10** | 0 | 0.00 | **21.44%** |
| 2025-01 | 148 | +277.18 | 15.47% |
| 2025-08 | 0 | 0.00 | 13.66% |

### Safety gate check (conservative)

| Gate | Limit | Result | Pass |
|---|---:|---:|:---:|
| reject_liquidated | true | False | ✅ |
| reject_near_liquidation | true | False | ✅ |
| max_drawdown_pct | 25% | **30.93%** | ❌ |
| max_final_open_exposure_usd | 5,000 | 2,986 | ✅ |
| daily_loss_limit_usd | 1,667 | not breached | ✅ |

**Conservative profile fails the 25% drawdown gate.** Three months exceeded 20% (Nov 2024, Jul 2025, Oct 2025). If the live exchange actually behaves more like the conservative assumptions (1s+ latency, 25% min partial fills), $10k equity is not safe.

### Read

- Conservative is a **harsh** stress: ROI -30% relative to mainnet-like, max DD +51%, partial fills 5× more frequent.
- The 1,864 partial fills (33.5% of orders) cause many entries to leg into position over multiple bars, which delays TP execution and inflates open exposure during adverse moves.
- The current Bybit mainnet measurements (median ~40ms REST, ~35ms WS) are much closer to the mainnet-like profile than the conservative one. Conservative is a worst-case sanity check, not the expected live behavior.
- **At $10k equity, the practical "true" risk is somewhere between mainnet-like (20.45% DD) and conservative (30.93% DD).** A safer alternative is to run at $15k+ equity with the same scaled config: conservative DD would drop to ~20.6%, well inside the gate.

### Sizing recommendation under conservative assumptions

If you want to be conservative-safe (DD ≤ 25%):

| Equity | Margin | Account cap | Conservative DD est. | Safe? |
|---:|---:|---:|---:|:---:|
| 10,000 | 33 | 4,167 | 30.93% | ❌ |
| 12,500 | 42 | 5,210 | 24.7% | ✅ marginal |
| **15,000** | **50** | **6,250** | **~20.6%** | **✅** |
| 20,000 | 67 | 8,333 | ~15.5% | ✅ |
| 30,000 | 100 | 12,500 | ~10.3% | ✅ |

**$15k is the safer minimum** if conservative assumptions are taken seriously.
