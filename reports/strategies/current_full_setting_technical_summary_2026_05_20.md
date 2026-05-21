# Current Full Setting and Technical Summary - 2026-05-20

## Current Default

Active strategy: `grid50_best`

Config source:

- `config/bot.yaml`
- `config/symbols.yaml`

The active bot is **not** using `regime_gate` by default. The active signal is:

```text
trend_filter -> grid
```

Full active signal:

```text
trend_filter:inner=grid:inner_anchor_period=200:inner_entry_bps=50:inner_step_bps=25:max_trend_bps=20
```

## Active Symbols

```text
BTCUSDT
ETHUSDT
SOLUSDT
XRPUSDT
BNBUSDT
LTCUSDT
```

Inactive override still exists:

```text
HYPEUSDT max_notional_per_symbol_usd = 300
```

But `HYPEUSDT` is not in the active symbol list.

## Sizing

```yaml
sizing:
  margin_usd: 100
  leverage: 10
```

Derived notional per entry:

```text
100 USDT margin * 10x = 1,000 USDT notional per entry
```

## Offsets

```yaml
offsets:
  entry_offset_bps: 5
  tp_offset_bps: 75
```

Meaning:

- Entry limit is placed `5 bps` better than candle close.
- TP is placed `75 bps` from entry or weighted BEP.

For LONG:

```text
entry = close - 5 bps
tp    = entry/BEP + 75 bps
```

For SHORT:

```text
entry = close + 5 bps
tp    = entry/BEP - 75 bps
```

## Merge Timer

```yaml
merge_timer:
  seconds: 1800
  policy: first_fill
```

Meaning:

- Timer starts on the first filled entry for a symbol.
- Timer is not reset by later layers.
- After `1800` seconds, or `30` minutes, the bot cancels old TPs and places one merged TP from weighted BEP.

## Fees

```yaml
fees:
  maker_bps: -1.0
  taker_bps: 5.5
```

Meaning:

- Maker fill gets `-1 bps` rebate in simulation.
- Taker or forced exits cost `5.5 bps`.

## Risk

```yaml
risk:
  max_notional_per_symbol_usd: 4000
  max_notional_account_usd: 12500
  max_consecutive_losses: 5
  cooldown_minutes: 60
  daily_loss_limit_usd: 5000
```

Approximate layer limits:

```text
per symbol: 4,000 / 1,000 = about 4 entry layers
account:    12,500 / 1,000 = about 12 total entry layers
```

## Account

```yaml
account:
  initial_equity: 30000
  margin_mode: cross
```

Research/backtests use `30,000` USDT initial equity unless overridden.

## Liquidation Model

```yaml
liquidation:
  enabled: true
  maintenance_margin_rate: 0.005
  near_liq_buffer_pct: 10
  funding_stress_bps: 0
```

Meaning:

- Backtest tracks liquidation and near-liquidation risk.
- Near-liquidation is flagged when distance to liquidation is inside the configured buffer.

## Optimizer Safety Gates

```yaml
optimizer:
  safety_gates:
    reject_liquidated: true
    reject_near_liquidation: true
    max_drawdown_pct: 25
    max_final_open_exposure_usd: 5000
```

A candidate is considered unsafe if:

- It liquidates.
- It gets near liquidation.
- Max drawdown exceeds `25%`.
- Final open exposure exceeds `5,000` USDT.

## Regime Router

```yaml
regime_router:
  enabled: false
  no_trade_on_unsafe: true
```

This router is currently disabled.

## Signal Parameters

```yaml
signal:
  engine: trend_filter
  params:
    inner: grid
    inner_anchor_period: 200
    inner_entry_bps: 50
    inner_step_bps: 25
    max_trend_bps: 20
```

## Grid Signal Logic

The grid signal uses a moving anchor:

```text
anchor = SMA of prior 200 closes
```

It emits a signal when price moves far enough from anchor:

- If price is `50 bps` below anchor, emit LONG.
- If price is `50 bps` above anchor, emit SHORT.
- If price moves another `25 bps` deeper, emit another same-direction layer.
- If price returns near anchor, reset the grid level tracker.

This is a mean-reversion signal. It expects price to return toward the anchor.

## Trend Filter Logic

The trend filter wraps the grid signal.

Default internal EMA values:

```text
ema_fast = 30
ema_slow = 120
```

Trend strength:

```text
trend_bps = abs(EMA_fast - EMA_slow) / EMA_slow * 10000
```

Rule:

```text
if trend_bps > max_trend_bps:
    suppress signal
```

Current threshold:

```text
max_trend_bps = 20
```

So if the local symbol trend is stronger than `20 bps`, the grid signal is blocked.

## State Machine

Main states:

```text
IDLE
ENTRY_PENDING
IN_POSITION_TP_PENDING
MERGE_PENDING
DUST_STRANDED
```

Normal lifecycle:

```text
IDLE
-> signal
-> place entry
-> entry filled
-> place TP
-> TP filled
-> back to IDLE
```

Layering lifecycle:

```text
IN_POSITION_TP_PENDING
-> same-direction signal
-> place another entry
-> layer filled
-> recalculate weighted BEP
-> cancel old TP
-> place new TP from weighted BEP
```

Merge lifecycle:

```text
first fill starts 30-minute timer
timer expires
-> cancel existing TPs
-> place one merge TP from weighted BEP
```

Dust handling:

```text
DUST_STRANDED
```

This state is used when remaining position is too small for exchange minimum notional or quantity. The bot avoids repeated invalid exit orders and waits for manual cleanup or a later fill that makes the position large enough again.

## Execution Backtest Models

Two execution models exist:

```text
naive
realistic
```

Naive:

- Old backtest style.
- Fill assumption is optimistic.

Realistic:

- Adds latency.
- Adds cancel delay.
- Adds slippage.
- Supports partial fill.
- Supports minimum notional/dust handling.
- Requires price pass-through for fills.

Mainnet-like profile:

```text
latency scenarios: 0.15s, 0.3s, 0.5s
cancel delay:      0.5s
slippage:          1 bps
pass-through:      0.2 bps
full-fill:         1 bps
min partial fill:  50%
```

## Regime Gate Status

`regime_gate` is implemented and testable, but it is **not active** in the default config.

Best tested gate variant:

```text
regime_gate:
  max_ema_spread_bps: 50
  max_adx: 35
  unsafe_action: reduce
  unsafe_size_scale: 0.5
```

It wraps the normal signal:

```text
regime_gate -> trend_filter -> grid
```

It checks BTC market regime:

- BTC EMA spread too high means market is trending.
- BTC ADX too high means trend strength is high.
- If unsafe, reduce signal size by `50%`.

Result from tests:

- It reduced drawdown in trend windows.
- It also reduced ROI.
- It is not selected as default yet.

## Recent Backtest Read

Main current strategy, `grid50_best`, mainnet-like execution:

| Window | Realistic annual ROI | Max DD | Read |
|---|---:|---:|---|
| `2022-05-09` to `2023-10-30` | `13.82%` | `10.17%` | Good sideways/choppy window |
| `2024-10-30` to `2026-02-02` | `12.06%` | `22.57%` | Barely passes target, high risk |
| `2024-10-14` to `2026-05-20` | `10.69%` | `25.47%` | Fails 12% target |
| `2026-01-01` to `2026-05-20` | `6.06%` | `7.48%` | Too low so far |

With best tested `regime_gate`:

| Window | Strategy + gate | Annual ROI | Max DD | Read |
|---|---|---:|---:|---|
| `2022-05-09` to `2023-10-30` | `grid50_best + regime_gate` | `12.68%` | `10.17%` | Pass |
| `2024-10-30` to `2026-02-02` | `grid50_best + regime_gate` | `11.26%` | `14.45%` | Safer, but below 12% |

## Technical Summary

This bot is a mean-reversion grid bot with trend filtering, layered recovery,
and BEP-based TP replacement.

It is strongest in sideways/choppy markets:

- Price moves away from SMA anchor.
- Bot enters against the move.
- Price mean-reverts.
- TP closes position.

It is weaker in strong bull/bear trends:

- Price keeps moving away from anchor.
- Bot layers into the adverse move.
- Drawdown and open exposure increase.
- Recovery depends on enough mean reversion before risk caps become restrictive.

Current selected default:

```text
grid50_best
```

Reason:

- Better than old archived current in sideways/choppy market.
- Safer than high-exposure variants.
- Regime gate is promising but not ready as default.

Current recommendation:

```text
Keep grid50_best as default.
Do not enable regime_gate by default yet.
Continue testing reduced-size trend protection plus TP/sizing adjustment.
```
