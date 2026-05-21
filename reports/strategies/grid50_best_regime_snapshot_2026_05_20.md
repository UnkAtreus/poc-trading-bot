# grid50_best Regime Snapshot - 2026-05-20

Current default strategy: `grid50_best`

Signal:

`trend_filter:inner=grid:inner_anchor_period=200:inner_entry_bps=50:inner_step_bps=25:max_trend_bps=20`

Sizing and risk:

- Margin per entry: `100` USDT
- Leverage: `10`
- TP offset: `75` bps
- Per-symbol notional cap: `4,000` USDT
- Account notional cap: `12,500` USDT
- Initial equity for research runs: `30,000` USDT

Mainnet-like execution profile:

- Latency scenarios: `0.15`, `0.3`, `0.5` seconds
- Cancel delay: `0.5` seconds
- Slippage: `1` bps
- Pass-through fill threshold: `0.2` bps
- Full-fill threshold: `1` bps
- Minimum partial fill: `50%`

## Backtest Read

| Window | Read | Realistic annual ROI | Max DD | Result |
|---|---|---:|---:|---|
| `2022-05-09` to `2023-10-30` | Sideways/choppy | `13.82%` | `10.17%` | Good |
| `2024-10-30` to `2026-02-02` | Trend mix | `12.06%` | `22.57%` | Barely passes, risk worse |
| `2024-10-14` to `2026-05-20` | Broad trend window | `10.69%` | `25.47%` | Fails target |
| `2026-01-01` to `2026-05-20` | Current 2026 YTD | `6.06%` | `7.48%` | Too low so far |

## Conclusion

`grid50_best` is regime dependent. It is useful in sideways/choppy markets, but
trend regimes reduce the annualized return and increase drawdown. The next
experiment should not increase sizing first. It should add a regime gate that
pauses or reduces grid entries when market trend is strong.

Candidate controls to test:

- Stricter `max_trend_bps`
- EMA-spread market gate
- ADX market gate
- Size reduction during unsafe trend instead of full pause
