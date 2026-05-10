# Current Strategy

Selected: 2026-05-02

Use **v1** while the carryover drawdown problem is unresolved.

## Active Config

- Signal: `trend_filter(inner=grid,inner_anchor_period=200,inner_entry_bps=30,inner_step_bps=15,max_trend_bps=30)`
- Symbols: BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, LTCUSDT, HYPEUSDT, XAUTUSDT
- Excluded: ASTERUSDT
- TP: 100 bps
- Margin/order: 66 USDT
- Leverage: 10x
- Notional/order: 660 USDT
- Risk caps: max_notional_account=50,000, max_notional_per_symbol=10,000, daily_loss_limit=5,000

## Decision

Use v1 as the current selected option. Do not use `hold24` or other forced
stop-loss variants for the current setup.

Reason: fresh continuous confirmation shows v1 has much lower carryover DD than
v3, even though profit is lower.

| Case | Net PnL | ROI | Max DD | Win rate |
|---|---:|---:|---:|---:|
| v1 continuous 2024-2025 | 8,484.48 USDT | 28.28% | 36.20% | 99.20% |
| v3 continuous 2024-2025 | 13,780.52 USDT | 45.94% | 62.36% | 100.00% |
