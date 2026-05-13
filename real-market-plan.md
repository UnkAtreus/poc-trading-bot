# Real Market Test Plan

Goal: test the bot on the real market with minimum capital risk before scaling.

This plan is not designed to prove guaranteed profit. It is designed to prove:

- API keys, permissions, and exchange order flow work correctly on mainnet.
- The bot can place, cancel, sync, and close orders without state mismatch.
- Position sizing, caps, and kill switches behave correctly with real fills.
- Trade logs are complete enough to audit every entry, exit, fee, and PnL.

Current production-size config is too large for a first real-money test:

- Current margin per trade: `66 USDT`
- Current leverage: `10x`
- Current notional per trade: `660 USDT`
- Active symbols: `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `XRPUSDT`, `BNBUSDT`, `HYPEUSDT`, `XAUTUSDT`
- Approximate multi-symbol notional if several symbols trigger: thousands of USDT

Do not start real-market testing with the current production-size settings.

## Phase 1 - Mainnet Plumbing Test

Purpose: prove real exchange connectivity and order safety, not strategy profit.

Recommended equity:

- `100-300 USDT`

Recommended config:

```yaml
sizing:
  margin_usd: 2
  leverage: 1

risk:
  max_notional_per_symbol_usd: 20
  max_notional_account_usd: 50
  daily_loss_limit_usd: 10
```

Symbol scope:

- Use only `BTCUSDT` or `ETHUSDT`.
- Disable all other symbols.

Run length:

- 1-3 trading days.

Required checks:

- Bot starts on mainnet only after explicit confirmation.
- Open orders appear correctly on exchange UI.
- Entry orders use expected price, quantity, side, and orderLinkId.
- TP/exit orders are `reduceOnly`.
- Bot does not open duplicate unexpected positions.
- Reconcile logic correctly adopts or resets positions.
- Kill switch stops new orders.
- Manual exchange close is detected by bot.

Pass criteria:

- No unexpected position flips.
- No unmanaged open position after bot stop.
- No repeated `place_order_failed`.
- No local/exchange position mismatch lasting longer than one reconcile cycle.
- Every order can be traced from log to exchange history.

Stop criteria:

- Any unexpected order side.
- Any position larger than configured cap.
- Any bot/exchange state mismatch that does not self-correct.
- Any API error that prevents exits.

## Phase 2 - Small Strategy Test

Purpose: test strategy behavior with real fills, spread, fee, and slippage.

Recommended equity:

- `1,000-2,000 USDT`

Recommended config:

```yaml
sizing:
  margin_usd: 5
  leverage: 2

risk:
  max_notional_per_symbol_usd: 100
  max_notional_account_usd: 300
  daily_loss_limit_usd: 20
```

Symbol scope:

- Use 2-3 high-liquidity symbols only.
- Suggested: `BTCUSDT`, `ETHUSDT`, `SOLUSDT`.
- Keep `HYPEUSDT` disabled unless specifically tested with a smaller cap.

Run length:

- 1-2 weeks.

Required checks:

- Compare real fills against backtest assumptions.
- Track maker/taker fee difference.
- Track slippage from intended entry and exit price.
- Track funding cost.
- Track rejected, cancelled, partially filled, and immediately filled orders.
- Confirm monthly/daily PnL report matches exchange closed PnL.

Pass criteria:

- Real trade logs match exchange history.
- No liquidation or near-liquidation event.
- Daily loss remains below configured limit.
- Bot closes positions correctly without manual intervention.
- PnL calculation matches exchange closed PnL within fee/funding tolerance.

Stop criteria:

- Daily loss limit hit.
- Two or more serious sync mismatches in one week.
- Exit order cannot be created or cancelled.
- More than one unexpected immediate open/close cycle without a clear reason.

## Phase 3 - Controlled Scale Test

Purpose: test whether the strategy remains stable with more symbols and larger notional.

Recommended equity:

- Minimum: `5,000 USDT`
- Preferred: `10,000 USDT+`

Recommended starting config:

```yaml
sizing:
  margin_usd: 10
  leverage: 2

risk:
  max_notional_per_symbol_usd: 200
  max_notional_account_usd: 800
  daily_loss_limit_usd: 50
```

Scale rules:

- Increase size only after at least 2 stable weeks.
- Increase one variable at a time: symbols, margin, or leverage.
- Do not increase leverage and symbol count together.
- Keep account notional cap far below total equity.
- Keep enough free equity for adverse movement, fees, funding, and manual recovery.

Before using the current larger config:

- Require clean testnet run with detailed execution logs.
- Require clean Phase 1 and Phase 2 reports.
- Require full optimizer and 500 start-date tests to pass.
- Require mainnet order audit report with no unexplained fills.
- Require manual kill switch test.

Pass criteria:

- Stable execution for at least 1 month.
- No unmanaged position after restart.
- No unreconciled exchange/local drift.
- Monthly report includes every trade with entry price, exit price, date, fee, funding, and PnL.
- Strategy remains profitable after real fees, funding, and slippage.

Stop criteria:

- Any near-liquidation warning.
- Any position not protected by reduce-only exit.
- Account drawdown exceeds planned limit.
- Exchange API error prevents close or cancel.
- Real-market PnL materially diverges from backtest without explanation.

## Minimum Recommendation

For first real-market testing:

- Use `100-300 USDT`.
- Use only one symbol.
- Use `1x-2x` leverage.
- Use very small `margin_usd`.
- Treat the run as infrastructure validation, not profit generation.

For serious strategy validation:

- Use `1,000-2,000 USDT`.
- Run at least 1-2 weeks.
- Keep risk caps small.
- Compare every trade against exchange history.

For the current larger config:

- Use at least `5,000 USDT`.
- Prefer `10,000 USDT+`.
- Do not run it until Phase 1 and Phase 2 are clean.

## AI Log Context

Do not paste raw bot logs into AI tools during real-market testing. Raw logs are too large, noisy, and can contain sensitive operational details.

Use the deterministic monitor and compact AI context generator instead:

```bash
uv run python scripts/monitor_live.py --skip-process-check
uv run python scripts/build_ai_context.py
```

For real-market VPS usage, enable process checking and kill switch deliberately:

```bash
uv run python scripts/monitor_live.py --tmux-session mainnet_bot --write-kill
```

The monitor writes:

- `reports/live_monitor.md` for current safety status.
- `reports/live_alerts.md` for attention-needed issues.
- `logs/live_monitor.jsonl` for tool-readable monitor snapshots.

The AI context generator writes:

```bash
uv run python scripts/build_ai_context.py
```

Default outputs:

- `reports/live_ai_context.md` for human and AI review.
- `logs/ai_context.jsonl` for tools or future automation.

Suggested cron:

```cron
* * * * * cd /path/poc-trading-bot && uv run python scripts/monitor_live.py --tmux-session mainnet_bot --write-kill >> logs/monitor_live_cron.log 2>&1
*/5 * * * * cd /path/poc-trading-bot && uv run python scripts/build_ai_context.py >> logs/ai_context_cron.log 2>&1
```

When asking AI to inspect the bot, share or reference `reports/live_ai_context.md` first. Only inspect raw logs if the compact report points to a specific timestamp or unresolved issue.

The monitor checks:

- Bot process/session is alive.
- Latest heartbeat is fresh.
- Exchange positions match local state.
- Every open position has a reduce-only TP/exit order.
- Symbol/account exposure caps are respected.
- Repeated order/API failures in the recent monitor window, default `900s`.
- Wallet equity and daily closed PnL.
- Critical safety issues that should stop new entries.

The AI context report includes:

- Monitor summary and current severity.
- Latest heartbeat states.
- Critical order failures.
- Reconcile and position drift events.
- Entry rejections and risk blocks.
- Event counts.
- Recent important events only.

Kill switch behavior:

- `scripts/monitor_live.py` is report-only unless `--write-kill` is passed.
- With `--write-kill`, critical issues create `data/state/KILL`.
- The bot already treats `data/state/KILL` as a kill switch and blocks new entries/startup.
- V1 does not auto market-close positions; human review is required.
