# Strategy v3 - Crash Balanced

Saved: 2026-05-02

Status: **selected crash-protection upgrade**

## Purpose

Reduce downside risk from the v2 baseline without killing the 2026 YTD profit
target.

## Config

- Signal: `crash_guard(inner=trend_filter(inner=grid,inner_anchor_period=100,inner_entry_bps=30,inner_step_bps=15,max_trend_bps=15),btc_ema_period=200,btc_return_bars=1440,btc_drop_bps=500)`
- Crash guard behavior: when BTC is below EMA200 and BTC 24h return is `<= -5%`, suppress LONG signals. SHORT signals are still allowed.
- Symbols: BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, LTCUSDT, HYPEUSDT, XAUTUSDT
- HYPE cap: 300 USDT, effectively disabled for 1,140 USDT orders
- TP: 100 bps
- Margin/order: 114 USDT
- Leverage: 10x
- Notional/order: 1,140 USDT
- Account notional cap: 20,000 USDT
- Per-symbol cap: 4,560 USDT
- Daily loss limit: 5,000 USDT

## Why This Was Chosen

It keeps the 2026 YTD target while cutting the full-cap crash risk materially.

| Case | 2026 YTD net | 2026 ROI | 2026 max DD | Account cap | 60% full-cap loss |
|---|---:|---:|---:|---:|---:|
| v2 baseline cap50 | 1,803.52 | 6.01% | 11.03% | 50,000 | 30,000 |
| v3 crash balanced | 1,803.40 | 6.01% | 9.59% | 20,000 | 12,000 |
| stricter crash-safe cap15 | 1,675.39 | 5.58% | 8.37% | 15,000 | 9,000 |

2025 sanity check:

| Case | 2025 net | 2025 ROI | 2025 max DD | Win rate |
|---|---:|---:|---:|---:|
| v3 crash balanced | 9,450.20 | 31.50% | 8.71% | 98.98% |
| stricter crash-safe cap15 | 6,458.42 | 21.53% | 15.14% | 98.99% |

## Notes

This is not a hedge. It does not guarantee profit during a crash. It prevents
the most dangerous behavior: adding more LONG exposure while BTC is already in
a sharp downside regime.

The stricter `15,000` account-cap version is safer for a deep crash, but it
missed the 2026 YTD 6% target in this sweep.

## Confirmation Caveat - 2026-05-03

Confirmation report: `reports/v3_confirmation_backtests_2026-05-03.md`.

V3 is confirmed for isolated 2025 and 2026 YTD:

- 2026-01-01 to 2026-05-03: +1,803.40 USDT, 6.01% ROI, 9.59% max DD.
- 2025-01-01 to 2026-01-01: +9,450.20 USDT, 31.50% ROI, 8.71% max DD.

V3 is not confirmed as live-safe for continuous carryover:

- 2024-01-01 to 2026-01-01 continuous: +13,780.52 USDT, but 62.36% max DD.
- Stricter caps at 15,000 and 12,500 still had 58.53% and 53.58% max DD.

The remaining risk is stale/carryover recovery positions, not only account cap.
