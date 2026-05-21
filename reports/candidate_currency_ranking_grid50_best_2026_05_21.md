# Candidate Currency Ranking for grid50_best

Run date: 2026-05-21

Purpose: rank candidate USDT perpetual symbols for the current `grid50_best` bot based on completed backtests and current Bybit linear instrument status.

Source backtests:

- `reports/backtest_top13_grid50_best_2022_05_09_to_2024_11_04_mainnet_like.md`
- `reports/backtest_top12_grid50_best_24m_6m_mainnet_like_2026_05_20.md`
- `reports/backtest_xmrusdt_grid50_best_continue_2022_05_09_to_2026_05_21_mainnet_like.md`

Current Bybit linear status was checked with `/v5/market/instruments-info`.

## Ranking

| Rank | Symbol | Tier | Decision | Evidence |
|---:|---|---|---|---|
| 1 | UNIUSDT | Core | Use | Strong in old window: `+1,124.90`, 166 trades. Strong recent: 24m `+1,884.32`, 6m `+433.29`. Best balance of profit, activity, and recency. |
| 2 | ETHUSDT | Core | Use | Consistent across all windows: old `+1,444.09`, 24m `+1,656.90`, 6m `+281.31`. High liquidity and stable availability. |
| 3 | XLMUSDT | Core | Use | Strong old and recent fit: old `+851.30`, 24m `+661.29`, 6m `+357.29`. Good trade frequency in recent window. |
| 4 | LTCUSDT | Core / monitor | Use, but monitor recency | Very strong old and 24m: old `+1,466.89`, 24m `+2,541.57`. Weak 6m: only 3 trades, `+23.10`, so size less aggressively than the top 3. |
| 5 | SOLUSDT | Core / medium | Use | Weak old window: `+182.50`, but strong recent behavior: 24m `+1,725.30`, 6m `+174.90`. Good candidate if prioritizing current regime. |
| 6 | BNBUSDT | Secondary core | Use | Strong old and 24m: old `+836.10`, 24m `+1,352.90`; modest 6m `+83.60`. Good stabilizer, but not top recent producer. |
| 7 | XRPUSDT | Secondary core | Use | Old result moderate: `+501.70`; recent 6m strong relative to rank: `+273.69`. Good add after core basket. |
| 8 | LINKUSDT | Secondary | Use | Moderate old `+364.80`, good 24m `+1,170.49`, decent 6m `+167.30`. Useful but below XRP on recent output. |
| 9 | ADAUSDT | Secondary | Small size | Good old `+820.90`, but weaker recent: 24m `+478.90`, 6m `+83.80`. Keep only if basket needs more coverage. |
| 10 | BTCUSDT | Defensive / low yield | Small size | Very liquid but low bot yield: old `+212.91`, 24m `+684.00`, 6m `+205.20`. Good operationally, not the best PnL match. |
| 11 | TRXUSDT | Low priority | Watch | Old `+646.11`, but weak recent: 24m `+159.70`, 6m `+53.30`. Lower edge than alternatives. |
| 12 | XMRUSDT | Watch only | Not core | Old cutoff only 1 trade, `+7.70`. Extended to 2026 gave `+1,124.89`, but most realized PnL came in 2024-12 to 2025-04 and it still ends merge-pending. Use only small or keep watch. |
| 13 | MATICUSDT | Exclude live | Do not use directly | Historical old-window result was best: `+1,900.09`, but current Bybit linear status is `Closed`. Use `POLUSDT` only after a fresh POL backtest. |

## Recommended Baskets

Conservative 5-symbol basket:

`UNIUSDT, ETHUSDT, XLMUSDT, LTCUSDT, SOLUSDT`

Balanced 8-symbol basket:

`UNIUSDT, ETHUSDT, XLMUSDT, LTCUSDT, SOLUSDT, BNBUSDT, XRPUSDT, LINKUSDT`

Expanded 10-symbol basket:

`UNIUSDT, ETHUSDT, XLMUSDT, LTCUSDT, SOLUSDT, BNBUSDT, XRPUSDT, LINKUSDT, ADAUSDT, BTCUSDT`

Avoid for now:

`MATICUSDT` because the contract is closed, `XMRUSDT` as a core symbol because it can sit merge-pending for long periods, and `TRXUSDT` unless more coverage is needed.

## Practical Notes

- The bot's closed-trade win rate is not useful for ranking here because all tested sets showed `100%` closed-trade wins. The real differentiators are realized PnL, trade frequency, recency, drawdown/open exposure behavior, and whether the symbol remains tradable.
- `MATICUSDT` should be replaced with a dedicated `POLUSDT` test before being considered for live trading.
- `LTCUSDT` has the strongest 24m result but weak recent activity, so it is ranked below the most consistent recent candidates.
- `XMRUSDT` is tradable, but the bot held a merge-pending position for a long time. It should not be sized like a core asset without more stress testing.
