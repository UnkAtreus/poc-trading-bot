# Max Cap Warning - Visual Explanation

## Simple Idea

Your account equity is:

```text
30,000 USDT deposit
+1,803 USDT realized profit
=31,803 USDT before open-position floating loss
```

The bot risk cap allows:

```text
max_notional_account = 50,000 USDT
```

That means the bot can hold positions larger than your deposit.

## Current Open Size vs Max Cap

Current open entry notional from the 2026 YTD final state:

```text
12,540 USDT open entry notional
```

Visual:

```text
Current open exposure
12.5k / 50k
[█████░░░░░░░░░░░░░░░] 25%

Maximum allowed exposure
50k / 50k
[████████████████████] 100%
```

So the current position is only about one quarter of the allowed max cap.

## BTC 48k Shock

BTC from 78,189 to 48,000 is about:

```text
-38.61%
```

If only the **current open position** gets this type of shock:

```text
Equity after shock ≈ 26,163 USDT
Loss from open positions ≈ -5,641 USDT
```

Visual:

```text
31.8k equity before shock
[████████████████████]

26.2k equity after current-position shock
[████████████████░░░░]

Loss ≈ 5.6k
[████░░░░░░░░░░░░░░░░]
```

This is painful, but the cross/unified account still survives.

## Why Max Cap Is The Warning

If the bot keeps adding until the full `50,000 USDT` cap, then the same -38.61%
market shock is much larger:

```text
50,000 × 38.61% = 19,305 USDT loss
```

Equity estimate:

```text
31,803 USDT equity before shock
-19,305 USDT shock loss
=12,498 USDT left
```

Visual:

```text
31.8k equity before shock
[████████████████████]

12.5k equity after full-cap shock
[████████░░░░░░░░░░░░]

Loss ≈ 19.3k
[████████████░░░░░░░░]
```

## Same Price Drop, Different Position Size

| Exposure | Shock | Estimated loss | Equity left |
|---|---:|---:|---:|
| Current open size, about 12.5k | -38.61% market-wide | -5.6k | 26.2k |
| Full max cap, 50k | -38.61% market-wide | -19.3k | 12.5k |

## Mental Picture

Think of exposure like weight:

```text
Current bot position:
You are carrying 12.5kg.
If market falls, it hurts, but you can still stand.

Full max-cap position:
You are carrying 50kg.
The same market fall hits about 4x harder.
```

## Meaning

The problem is not BTC 48k by itself.

The problem is:

```text
BTC 48k + bot keeps adding + exposure grows to 50k
```

That is why the cap matters.
