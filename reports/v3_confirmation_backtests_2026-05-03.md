# V3 Confirmation Backtests

Generated: 2026-05-03

## Active Config

- Strategy: v3 crash balanced
- Signal: `crash_guard(inner=trend_filter(inner=grid,inner_anchor_period=100,inner_entry_bps=30,inner_step_bps=15,max_trend_bps=15),btc_ema_period=200,btc_return_bars=1440,btc_drop_bps=500)`
- TP: 100 bps
- Margin/order: 114 USDT
- Leverage: 10x
- Account cap: 20,000 USDT
- Per-symbol cap: 4,560 USDT
- Initial equity: 30,000 USDT
- HYPE cap: 300 USDT

## Confirmation Summary

| Run | Date range | Net PnL | ROI | Max DD | Max DD % | Trades | Win rate | Read |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026 YTD | 2026-01-01 to 2026-05-03 | 1,803.40 | 6.01% | 2,876.71 | 9.59% | 97 | 100.00% | Confirmed |
| 2025 only | 2025-01-01 to 2026-01-01 | 9,450.20 | 31.50% | 2,612.47 | 8.71% | 492 | 98.98% | Confirmed |
| 2024-2025 continuous | 2024-01-01 to 2026-01-01 | 13,780.52 | 45.94% | 18,708.05 | 62.36% | 676 | 100.00% | Not safe |

## Stricter Continuous Checks

These checks were added because the active 20k cap still had high continuous
drawdown.

| Run | Account cap | Per-symbol cap | Net PnL | ROI | Max DD | Max DD % | Trades | Win rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| v3 cap15 | 15,000 | 3,420 | 12,938.10 | 43.13% | 17,560.12 | 58.53% | 763 | 98.69% |
| v3 cap12.5 | 12,500 | 2,280 | 8,605.48 | 28.68% | 16,075.01 | 53.58% | 717 | 100.00% |

## Conclusion

V3 is confirmed for isolated 2025 and 2026 YTD.

V3 is **not confirmed as live-safe** for the continuous 2024-2025 carryover
case. Even stricter caps still leave 53-58% account max drawdown in the
continuous two-year run.

This means the remaining problem is not only max exposure. The strategy also
needs a rule for stale/carryover recovery positions, such as:

- close/reduce positions after a max age,
- stop adding to symbols with large unrealized loss,
- hard account drawdown de-risk,
- or separate crash hedge/short overlay.

## Raw Logs

- `logs/v3_confirm_2026_ytd_to_2026-05-03_equity30000.txt`
- `logs/v3_confirm_2025_equity30000.txt`
- `logs/v3_confirm_2024_2025_equity30000.txt`
- `logs/v3_confirm_cap15_2024_2025_equity30000.txt`
- `logs/v3_confirm_cap12500_2024_2025_equity30000.txt`
