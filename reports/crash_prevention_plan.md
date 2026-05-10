# Crash Prevention Plan

## Problem

The active v2 baseline can survive the current open position under a BTC 48,000
stress if the account is cross/unified. The bigger danger is if the bot keeps
adding until the full `50,000 USDT` account notional cap and then the market
crashes.

At full cap:

| Market drop | Estimated loss on 50,000 exposure |
|---:|---:|
| 50% | 25,000 USDT |
| 60% | 30,000 USDT |
| 70% | 35,000 USDT |
| 80% | 40,000 USDT |

That is too much for 30,000 USDT equity.

## Prevention Option 1 - Lower Exposure Cap

This is the cleanest first fix.

| Max DD budget | Survive 50% drop | Survive 60% drop | Survive 70% drop | Survive 80% drop |
|---:|---:|---:|---:|---:|
| 15% DD | 9,000 cap | 7,500 cap | 6,429 cap | 5,625 cap |
| 20% DD | 12,000 cap | 10,000 cap | 8,571 cap | 7,500 cap |
| 25% DD | 15,000 cap | 12,500 cap | 10,714 cap | 9,375 cap |
| 30% DD | 18,000 cap | 15,000 cap | 12,857 cap | 11,250 cap |

Recommended conservative cap:

```text
max_notional_account = 12,500 to 15,000
```

This means a 60% market crash costs about:

```text
12,500 exposure × 60% = 7,500 loss
15,000 exposure × 60% = 9,000 loss
```

That is painful but survivable.

## Prevention Option 2 - Per-Symbol Caps

Keep fewer layers on high-crash-risk symbols.

With current v2 order size:

```text
114 margin × 10x = 1,140 notional/order
```

Suggested starting caps:

| Symbol | Suggested cap | Approx max layers |
|---|---:|---:|
| BTCUSDT | 3,420 | 3 |
| ETHUSDT | 3,420 | 3 |
| SOLUSDT | 2,280 | 2 |
| XRPUSDT | 2,280 | 2 |
| BNBUSDT | 2,280 | 2 |
| LTCUSDT | 2,280 | 2 |
| HYPEUSDT | 0-300 | 0 |
| XAUTUSDT | 2,280 | 2 |

Reason: altcoins can fall harder than BTC. The bot should not average down
many layers on every altcoin during the same crash.

## Prevention Option 3 - Crash Mode

When BTC shows crash conditions:

```text
BTC below 4h EMA200
and BTC 24h return < -5%
or BTC 1h ATR spike > 2x normal
```

Then:

```text
1. Stop new long entries.
2. Allow only short entries or no entries.
3. Keep existing TP/merge orders alive.
4. Reduce account cap to emergency cap, e.g. 7,500.
```

This protects the BEP-merge system from averaging down during a waterfall.

## Make Money Option - Hedge Overlay

Do not try to make crash money with the same long recovery grid. Use a separate
small hedge.

Example:

```text
Current long exposure = 12,500
Open BTC/ETH short hedge = 30-50% of exposure
Hedge size = 3,750 to 6,250
```

If market drops 50%:

```text
3,750 short hedge earns about 1,875
6,250 short hedge earns about 3,125
```

This offsets long-position drawdown.

Risk: if market rebounds, the hedge loses money. The hedge needs its own stop.

## Recommended Order

1. First test lower caps: `12,500`, `15,000`, `20,000`.
2. Then test per-symbol caps.
3. Then add crash mode: block new longs in strong BTC downtrend.
4. Last, test hedge overlay. Hedges can help, but they also create whipsaw loss.

## Selected Option After Sweep

The sweep selected the crash-balanced option:

```text
signal = crash_guard(v2 baseline)
max_notional_account = 20,000
max_notional_per_symbol = 4,560
HYPE capped at 300
```

Reason:

```text
2026 YTD ROI stays at 6.01%
2026 YTD max DD improves from 11.03% to 9.59%
60% full-cap crash loss drops from 30,000 to 12,000
2025 sanity check remains strong: 31.50% ROI, 8.71% max DD
```

The stricter 15,000 account-cap option is safer for a deep crash but missed
the 2026 YTD profit target in the sweep.
