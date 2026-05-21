# Top 12 grid50_best backtests: 24m and 6m

- Run date: 2026-05-20
- Strategy/config: current `grid50_best` config from `config/bot.yaml`
- Signal: `trend_filter` wrapping `grid`, anchor 200, entry 50 bps, step 25 bps, max trend 20 bps
- Sizing/risk: 100 USDT margin, 10x leverage, 4,000 USDT per-symbol cap, 12,500 USDT account cap
- Execution: realistic `mainnet-like` profile, 0.3s latency, 0.5s cancel delay, 1 bps slippage, 0.2 bps pass-through
- Initial equity: 30,000 USDT
- Requested symbols: BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, LTCUSDT, ADAUSDT, UNIUSDT, MATICUSDT, XLMUSDT, LINKUSDT, TRXUSDT

## Summary

| Window | Range | Symbols with data | Net PnL | ROI | Max DD | Max DD % | Trades | Win rate | Final open exposure | Archive |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 24m | 2024-05-20 to 2026-05-20 | 12 | +13,083.17 | 43.61% | 9,991.84 | 33.31% | 1,741 | 100.00% | 10,835.50 | `data/backtests/runs/20260520T165431667155Z_cli_backtest_65156f94e6.json` |
| 6m | 2025-11-20 to 2026-05-20 | 11 | +2,136.79 | 7.12% | 4,879.33 | 16.26% | 288 | 100.00% | 7,681.56 | `data/backtests/runs/20260520T165727464263Z_cli_backtest_6a75ed034b.json` |

Raw successful logs:

- `logs/backtest_top12_grid50_best_24m_mainnet_like_2026_05_20_retry1.txt`
- `logs/backtest_top12_grid50_best_6m_mainnet_like_2026_05_20.txt`

## 24m per-symbol PnL

| Symbol | Trades | Net PnL |
|---|---:|---:|
| LTCUSDT | 332 | +2,541.57 |
| UNIUSDT | 246 | +1,884.32 |
| SOLUSDT | 230 | +1,725.30 |
| ETHUSDT | 217 | +1,656.90 |
| BNBUSDT | 193 | +1,352.90 |
| LINKUSDT | 149 | +1,170.49 |
| XRPUSDT | 86 | +699.30 |
| BTCUSDT | 93 | +684.00 |
| XLMUSDT | 99 | +661.29 |
| ADAUSDT | 60 | +478.90 |
| TRXUSDT | 28 | +159.70 |
| MATICUSDT | 8 | +68.50 |

## 6m per-symbol PnL

| Symbol | Trades | Net PnL |
|---|---:|---:|
| UNIUSDT | 56 | +433.29 |
| XLMUSDT | 57 | +357.29 |
| ETHUSDT | 32 | +281.31 |
| XRPUSDT | 37 | +273.69 |
| BTCUSDT | 23 | +205.20 |
| SOLUSDT | 17 | +174.90 |
| LINKUSDT | 25 | +167.30 |
| ADAUSDT | 10 | +83.80 |
| BNBUSDT | 19 | +83.60 |
| TRXUSDT | 9 | +53.30 |
| LTCUSDT | 3 | +23.10 |

## Notes

- `MATICUSDT` had partial historical data in the 24m run and no klines in the 6m window, so the 6m run effectively covered 11 symbols.
- Both runs avoided liquidation and near-liquidation flags.
- The 24m run has strong PnL but high global max DD at 33.31% and high final open exposure at 10,835.50 USDT.
- The 6m run has lower DD at 16.26%, but also ended with 7,681.56 USDT open exposure and no closed trades after March 2026.
