# Current Strategy

Selected: 2026-05-20

Use **grid50_best** as the current default strategy.

## Active Config

- Signal: `trend_filter(inner=grid,inner_anchor_period=200,inner_entry_bps=50,inner_step_bps=25,max_trend_bps=20)`
- Symbols: BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, LTCUSDT
- Excluded: ASTERUSDT
- TP: 75 bps
- Margin/order: 100 USDT
- Leverage: 10x
- Notional/order: 1,000 USDT
- Risk caps: max_notional_account=12,500, max_notional_per_symbol=4,000, daily_loss_limit=5,000

## Decision

Use `grid50_best` as the current selected option. Conservative execution did
not clear the 12% annual target, but the mainnet-like execution profile did.

Reference run: `reports/compare_execution_2022_05_09_to_2023_10_30_grid50_best_mainnet_like.md`

| Case | Net PnL | ROI | Max DD | Win rate |
|---|---:|---:|---:|---:|
| grid50_best naive 2022-05-09 to 2023-10-30 | 6,522.52 USDT | 21.74% | 11.37% | 100.00% |
| grid50_best mainnet-like 2022-05-09 to 2023-10-30 | 6,120.27 USDT | 20.40% | 10.17% | 100.00% |
