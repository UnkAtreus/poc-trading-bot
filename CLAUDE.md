# Claude — project guide for `poc-trading-bot`

> Loaded automatically on every session. Read this before exploring source.

## What this bot does

Replica of the existing `main` strategy on Bybit USDT-perp futures: **signal-based 1-minute limit scalping with auto-merge TP at the position BEP**. Per closed 1m candle, a pluggable signal decides direction; an entry limit is placed slightly through the close; if filled, a tight TP limit is placed at the fill; if the TP doesn't fill within 30 minutes of the first un-TP'd fill, all pending TPs are cancelled and replaced with one merged TP at `BEP × (1 ± tp_offset_bps / 10000)`.

**Order sizing:** $114 margin × 10× leverage = $1,140 notional per order. Position can layer (multiple entries before TP fires) — BEP is recomputed on every fill.

**Modes:** `backtest` (offline historical klines), `testnet` (api-testnet.bybit.com), `mainnet`. The same strategy code runs unchanged in all three; only the `ExchangeAdapter` swaps.

**Current symbol note:** `ASTERUSDT` is excluded from `config/symbols.yaml` after
the 2025 TP-100 improvement sweep because it was the main source of high DD in
the larger-lot grid run.

**Latest v2 backtest note (2026-05-02):** v2 is saved at
`reports/strategies/v2.md`. Latest equity-30k comparison is saved at
`reports/v2_backtest_2024_2025_equity30000.md`; raw logs are in
`logs/v2_backtest_2024_equity30000.txt`,
`logs/v2_backtest_2025_equity30000.txt`, and
`logs/v2_backtest_2024_2025_equity30000.txt`. V2 did well in isolated 2025
(+9,858.97 USDT, 32.86% ROI, 8.79% account max DD), but 2024 and continuous
2024-2025 had high account max DD (50.16% and 62.24%), so do not treat v2 as
live-ready without additional drawdown controls.

**Current strategy decision (2026-05-02):** use **v3 crash balanced**. Active
strategy file is `reports/strategies/current.md`; source strategy note is
`reports/strategies/v3_crash_balanced.md`. It wraps v2 with `crash_guard`,
reduces account cap to 20,000, and reduces per-symbol cap to 4,560. It keeps
the 2026 YTD target (+1,803.40 USDT, 6.01% ROI) while reducing max DD to 9.59%
and reducing full-cap 60% crash loss from 30,000 to 12,000. Do not use `hold24`
or other forced stop-loss variants for the current setup.

**Crash prevention note:** downside stress report is
`reports/v2_baseline_downside_stress_btc48000_2026_ytd.md`; crash-control plan
is `reports/crash_prevention_plan.md`; option sweep is
`reports/crash_option_sweep_2026_ytd.md`. v1 and v2 are not the same, so they
were not combined.

**V3 confirmation caveat (2026-05-03):** confirmation report is
`reports/v3_confirmation_backtests_2026-05-03.md`. V3 confirmed isolated 2025
and 2026 YTD, but not continuous 2024-2025 carryover: continuous run still had
62.36% max DD, and stricter 15,000 / 12,500 caps still had 58.53% / 53.58% max
DD. Remaining risk is stale/carryover recovery positions, not only account cap.

**V1/V2 into V3 test (2026-05-03):** report is
`reports/v1_v2_into_v3_backtest_matrix.md`; raw matrix is
`logs/v1_v2_into_v3_backtest_matrix.csv`. `v1v2_agree_into_v3` was best in
2026 YTD (+2,180.62 USDT, 7.27% ROI, 4.80% max DD), but continuous 2024-2025
still had 57.61% max DD. `v1_into_v3` had the lowest continuous DD (36.36%)
but missed the 2026 target (2.50% ROI). Do not combine v1/v2 as the active
strategy yet; current v3 remains the profit-balanced setup.

**Current rollback to v1 (2026-05-03):** user requested back to v1. Active
`config/bot.yaml` is now v1: margin 66, `trend_filter(grid anchor=200,
entry=30, step=15, max_trend=30)`, TP 100 bps, account cap 50,000, per-symbol
cap 10,000. Fresh continuous report:
`reports/v1_confirm_2024_2025_continuous_equity30000.md`. Result:
+8,484.48 USDT, 28.28% ROI, 36.20% max DD, 21.11% worst monthly DD, 99.20%
win rate. V1 is lower profit than v3 but much lower continuous carryover DD.

**Same-lot version comparison (2026-05-03):** report is
`reports/version_compare_same_lot_matrix.md`; raw CSV is
`logs/version_compare_same_lot_matrix.csv`. Tested v1 with the same lot size as
v2/v3 (`114 USDT` margin, 10x). V1 no longer has a DD advantage: continuous
2024-2025 max DD was v1 62.52%, v2 62.24%, v3 62.36%. Recommendation from this
fair lot-size test: v3 is the practical live choice because it keeps v2-like
2026 ROI with lower 2026 DD and lower full-cap crash exposure; v2 is best pure
PnL; v1 same-lot is not recommended.

**Current market similarity (2026-05-03):** report is
`reports/current_market_similarity.md`. Using cached Bybit daily data for BTC,
ETH, SOL, XRP, BNB, and LTC, the current 30-day basket shape is closest to
late-2024 recovery/range windows, especially windows ending 2024-11-03,
2024-10-31, and 2024-10-07. Read: positive 30-day basket, weak negative 7-day
pullback, moderate DD; closer to post-pump consolidation than crash.

**V3 2021-now backtest (2026-05-03):** report is
`reports/v3_backtest_2021_now_equity30000.md`; raw retry log is
`logs/v3_backtest_2021_now_equity30000_raw_retry1.txt`; clean output is
`logs/v3_backtest_2021_now_equity30000_clean.txt`. Window was 2021-01-01 to
2026-05-04 UTC with partial May 2026 data. Result: +21,744.03 USDT net on
30,000 equity, 72.48% ROI, 99.19% win rate, but 11,417.61 USDT / 38.06%
overall max DD. Important caveat: it had a 16-month zero-trade stretch from
2022-06 through 2023-09 and ended with seven symbols still in `MERGE_PENDING`;
v3 is profitable historically but not a clean monthly-income profile as-is.

## Trading flow

Long side:

1. On every closed 1m candle, compute the configured signal first.
2. If the signal says LONG, place a post-only Buy limit at `close - entry_offset_bps`.
   With the current config, `entry_offset_bps: 5`, so this is `close - 0.05%`.
3. If the Buy fills, immediately place a Sell TP at `fill_price + tp_offset_bps`.
   `tp_offset_bps: 10` means `+0.1%`; `tp_offset_bps: 1` means `+0.01%`.
4. If the Buy is still unfilled at the next candle close, cancel it and evaluate
   the new candle/signal again.
5. If the Buy filled but the Sell TP did not fill, wait for the merge timer
   (`merge_timer.seconds: 1800`, 30 minutes from the first fill). Then cancel
   all pending TPs and place one merged Sell TP at `BEP + tp_offset_bps`.

Short side is symmetric:

1. The signal says SHORT, so the bot places a post-only Sell entry above the
   close by `entry_offset_bps`.
2. If the Sell fills, it places a Buy TP at `fill_price - tp_offset_bps`.
3. If that TP does not fill before the merge timer expires, it cancels pending
   TPs and places one merged Buy TP at `BEP - tp_offset_bps`.

This is **signal-based limit scalp + auto-merge TP at BEP**. It is not a
free-running grid that opens at every distance regardless of signal. Even the
`grid` engine only emits signals; the state machine still controls entry,
unfilled-entry cancellation, TP placement, layering, and BEP merge behavior.

## Commands

Always use `uv` for Python (see `~/.claude/projects/.../memory/feedback_uv_for_python.md`). **Never** `pip` or `python -m venv` directly.

```bash
# Create / sync env
uv venv --python 3.11
uv pip install -e ".[dev]"

# Tests (53 unit, 4 opt-in integration)
uv run pytest                          # all non-testnet tests
uv run pytest -m testnet               # opt-in: hits api-testnet.bybit.com
uv run pytest tests/unit/test_state_machine.py -v   # focus

# Backtest (klines cached per UTC month under data/klines/{SYMBOL}_{YYYY-MM}.parquet)
uv run python -m bot.main backtest --start 2024-01-01 --end 2024-01-02 --symbols BTCUSDT
uv run python -m bot.main backtest --start 2024-01-01 --end 2025-01-01 --by-month --with-risk \
    --signal "bollinger_bands:period=20:num_std=2.0" \
    --kline-workers 4 \
    --tp-offset-bps 10

# Compare strategies head-to-head on the same data
uv run python -m bot.main compare --start 2024-01-01 --end 2024-02-01 --symbols BTCUSDT \
    --signals "bollinger_bands,zscore:period=50,grid:entry_bps=80:step_bps=40,ema_crossover" \
    --by-month --with-risk --kline-workers 4 --tp-offset-bps 10 --initial-equity 3000

# Full-year comparison sweep; capture the matrix + monthly breakdown to a file.
uv run python -m bot.main compare --start 2024-01-01 --end 2025-01-01 \
    --signals "bollinger_bands:period=20:num_std=2.0,bollinger_bands:period=50:num_std=2.5,zscore:period=50:threshold=2.0,zscore:period=100:threshold=2.5,grid:anchor_period=200:entry_bps=50:step_bps=30,grid:anchor_period=400:entry_bps=80:step_bps=40,ema_crossover:fast=9:slow=21,trend_filter:inner=bollinger_bands:inner_period=20:inner_num_std=2.0:max_trend_bps=30" \
    --by-month --with-risk --kline-workers 4 \
    > reports/compare_2024_active_8strats_by_month_with_risk.txt 2>&1

`--kline-workers N` parallelizes symbol-level kline cache loads/fetches. Keep it
conservative (4 is a good default) because each symbol still paginates Bybit
requests for missing months.

`--tp-offset-bps N` overrides the TP offset for a run without editing
`config/bot.yaml` (1 bp = 0.01%, 10 bps = 0.1%, 100 bps = 1%).

`--initial-equity N` enables ROI and max drawdown percentage reporting in both
the main comparison matrix and `--by-month` breakdown. Max DD is mark-to-market
from candle closes and open positions; liquidation is still not modeled.
Monthly DD resets the peak at the start of each UTC month.

Sizing/risk can be overridden per backtest/compare run without editing
`config/bot.yaml`: `--margin-usd N`, `--leverage N`,
`--max-notional-account N`, `--max-notional-per-symbol N`, and
`--daily-loss-limit N`.

Backtest-only forced-stop flags exist for historical experiments:
`--stop-bep-bps N`, `--stop-symbol-loss N`, `--stop-account-dd-pct N`, and
`--stop-max-hold-hours N`. They are not part of the active strategy.
They simulate taker/market-style forced exits in the backtest runner only; live
orchestration does not yet place real stop or market-close orders from these
flags.

# Live (mode comes from .env)
uv run python -m bot.main run

# Smoke-check Bybit creds before a live soak
uv run python scripts/dry_testnet.py                 # streams klines for 90s
uv run python scripts/dry_testnet.py --place-order   # also round-trips a tiny limit
```

## Repo layout

```
src/bot/
├── main.py                 # CLI entry (backtest | run)
├── config.py               # pydantic Settings; .env + bot.yaml + symbols.yaml
├── logger.py               # structlog (console in dev, JSON optional)
├── models.py               # Order/Fill/Position/Signal/Candle/event dataclasses
├── strategy/
│   ├── states.py           # State enum
│   ├── state_machine.py    # PURE reducer: (Context, Event) -> (Context, [Action])
│   └── orchestrator.py     # async driver — owns 30-min timer, periodic reconcile
├── signals/                 # all plug into the same SM via SignalEngine ABC
│   ├── base.py             # SignalEngine ABC + @register decorator
│   ├── placeholder_rsi.py  # Wilder RSI (default plug; not a real strategy)
│   ├── random_signal.py    # plumbing-test signal
│   ├── bollinger_bands.py  # mean-reversion: long below lower band, short above upper
│   ├── zscore.py           # mean-reversion: long if z<-thr, short if z>+thr
│   ├── grid.py             # anchored grid bot: fires every grid_bps step from SMA anchor
│   ├── ema_cross.py        # trend follower (warning: bleeds with merge-at-BEP)
│   └── trend_filter.py     # wraps another engine; suppresses signals in strong trends
├── exchange/
│   ├── base.py             # ExchangeAdapter ABC — strategy code only sees this
│   ├── bybit_live.py       # pybit unified_trading wrapper (REST + 2 WS streams)
│   └── simulator.py        # in-process backtest fill engine, same ABC
├── risk/manager.py         # caps + cooldowns + KILL switch + mainnet guard
├── persistence/store.py    # atomic per-symbol JSON snapshot
└── backtest/
    ├── runner.py           # walk-forward driver; same SM + signals as live
    ├── downloader.py       # Bybit kline -> parquet cache
    └── report.py           # text PnL report
config/{bot,symbols}.yaml   # strategy + symbol list (pydantic-validated; unknown keys hard-fail)
data/klines/*.parquet       # cached historical klines
data/state/*.json           # per-symbol snapshots; data/state/KILL halts the bot
tests/unit/                 # 53 tests, < 0.2s
tests/integration/          # opt-in (`-m testnet`); hits api-testnet.bybit.com
scripts/dry_testnet.py      # smoke script before a live soak
```

## Hard invariants — DO NOT BREAK

1. `**state_machine.py` is pure.** No I/O, no asyncio, no globals. Inputs: `(Context, Event, Params)`. Output: `Decision(new_ctx, [Action])`. The orchestrator executes actions; the SM never touches the exchange.
2. `**ExchangeAdapter` is the only surface strategy code touches.** Strategy never imports `pybit`, `bybit_live`, or `simulator` directly. Three impls: `BybitLive`, `BybitLive(testnet=True)`, `Simulator`. Adding a new exchange = implementing the ABC.
3. `**PostOnly` for every limit order.** Matches the existing `main` bot's 90%+ maker rate. If Bybit rejects (price would cross), treat as `EntryUnfilled`.
4. **Mainnet guard.** `MODE=mainnet` requires `MAINNET_CONFIRM=YES_I_MEAN_IT`. The pydantic validator and `RiskManager.assert_can_start` both enforce this — never disable.
5. **Kill switch always wins.** `data/state/KILL` (file) or `BOT_KILL=1` (env). Checked before every order. Never bypass.
6. **30-min timer policy: `first_fill`.** Started on the first un-TP'd fill, **not reset by layered fills**, cleared only when position returns to flat. Documented as `merge_timer.policy: first_fill` in `bot.yaml`. A `per_fill` variant is allowed but must be additive (don't remove `first_fill`).
7. **Layered entries stay in `IN_POSITION_TP_PENDING`.** They do **not** transition to `ENTRY_PENDING` — that handler treats fills as fresh first entries and would overwrite BEP. (This was a real bug; tests `test_in_position_layered_signal_places_new_entry` and `test_in_position_layered_fill_recomputes_bep_and_replaces_tp` lock it down.)
   **Also:** unfilled layered entries get cancelled at the *next* candle close (same rule as ENTRY_PENDING) — otherwise the bot stalls. See `test_in_position_unfilled_layered_entry_cancelled_on_next_candle`.
8. **Halt semantics.** `RiskHalt` blocks new entries only. **Never** cancels existing TPs/merges — let positions resolve naturally.
9. **`RiskManager.clock` is injectable.** The backtest runner retargets it to simulation time so cooldowns + daily-loss rolls happen in sim seconds, not wall seconds. **Never** call `time.time()` directly inside the risk manager — always go through `self.clock()`.
10. **Klines cache per UTC month** at `data/klines/{SYMBOL}_{YYYY-MM}.parquet`. `load_or_fetch` assembles the requested range from monthly chunks; only missing months are fetched. Don't change the keying — backtest reproducibility depends on it.

## Adding a new signal

```python
# src/bot/signals/my_strategy.py
from bot.signals.base import SignalEngine, register
from bot.models import Candle, Direction, Signal

@register("my_strategy")
class MyStrategy(SignalEngine):
    def __init__(self, **params): ...
    def warmup_bars(self) -> int: ...
    def on_candle(self, candle: Candle) -> Signal | None: ...
```

Then in `config/bot.yaml`:

```yaml
signal:
  engine: my_strategy
  params: { ... }
```

The registry in `signals/base.py` auto-imports the placeholder modules; for new ones, ensure the file is imported somewhere or add it to the lazy-import block at the bottom of `build()`.

## Known limitations / open issues

1. **Same-candle backtest race** — when a layered ENTRY and an OLD TP would both fill in the same 1m candle, the SM's `CancelAllTPs` cannot fire mid-candle in the simulator, so the old TP can fill before being cancelled. Live trading doesn't have this race (orders sequence in milliseconds). See `exchange/simulator.py` docstring. Mitigation: use sparse-cadence signals when judging backtest results.
2. **No partial-fill modeling.** $200 notional vs 1m volume on majors makes this safe, but exotic symbols with thin books would need it.
3. **Funding fees ignored.** 1m scalps rarely hold across funding windows. TODO in `bot.yaml` if it becomes material.
4. `**placeholder_rsi` is a placeholder.** It's only there for plumbing tests — not a real signal. Backtest results with it are not predictive.

## Conventions

- **Decimal vs float:** prices and qtys cross the wire as strings; we cast to `Decimal` only at exchange boundaries (`Instrument.tick_size`, etc.). Internal math uses `float` because the SM and backtest deal in microseconds-per-step.
- `**orderLinkId` scheme:** `{symbol}-{side}-{purpose}-{ulid}` where purpose ∈ {`entry`, `tp`, `merge`}. Lets WS events route to SM intents without `orderId` round-trips. **Never change the format** without updating `_purpose_from_link` and the link-parsing code in runner/orchestrator.
- **Logging:** `structlog`. Use `log.info("event.name", key=value, ...)` — no f-strings, no string concatenation. Names are dotted (`bot.starting`, `entry_blocked`, `reconcile.size_drift`).
- **Tests are fast (~0.2s) and deterministic.** Don't add tests that hit the network unless under `-m testnet`. Don't add `time.sleep` to unit tests; use `freezegun` if you need deterministic clock.
- **Dataclasses are frozen** (`@dataclass(frozen=True)`) wherever they cross the SM boundary. Mutate by `replace()`.

## Where to look when…


| Question                         | File                                                                 |
| -------------------------------- | -------------------------------------------------------------------- |
| "Why did the bot enter here?"    | `signals/<engine>.py` + `_from_idle` in `state_machine.py`           |
| "Why didn't a TP fire?"          | `_from_in_position` / `_from_merge_pending` in `state_machine.py`    |
| "Why was an order rejected?"     | `bybit_live.place_limit` (PostOnly) + risk_manager logs              |
| "Why is the position stuck?"     | `data/state/<symbol>.json` + reconcile loop logs                     |
| "How does the merge timer work?" | `_schedule_merge_timer` + `_fire_merge` in `orchestrator.py`         |
| "Backtest fees look wrong"       | `_record_entry`/`_record_exit` in `backtest/runner.py` (signed fees) |


## Implementation history (for context)

Built bottom-up per `~/.claude/plans/humming-cooking-fountain.md`:

1. Skeleton + config + logger
2. Pure state machine (25 transition tests)
3. Signal ABC + placeholders
4. Persistence (atomic JSON snapshots)
5. Simulator + backtest engine
6. Risk manager
7. Bybit live adapter (REST + 2 WS streams)
8. Orchestrator + main wiring
9. Reconcile loop + heartbeat (this step)
10. Smoke script + opt-in integration tests (this step)

**Next:** swap `placeholder_rsi` for a real signal once chosen; soak on testnet ≥ 1 week before mainnet.

## Out of scope for v1

- Multiple positions per symbol (we model net only)
- Stop-losses (strategy is mean-reversion / BEP-recovery; the merge timer is the only "exit")
- Position flipping on opposite signals (ignored while in position)
- Funding-aware PnL
- Multi-account
