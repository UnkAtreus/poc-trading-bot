# TP Target Comparison — 2025 — Initial 3000 USDT

Range: 2025-01-01 to 2026-01-01 UTC
Symbols: ASTERUSDT, BNBUSDT, BTCUSDT, ETHUSDT, HYPEUSDT, LTCUSDT, SOLUSDT, XAUTUSDT, XRPUSDT
Bars: 4,220,816 1m bars
Risk: `--with-risk`
Starting capital for ROI: 3000 USDT

| TP target | TP bps | Best realized row | Trades | Win rate | Net USDT | ROI on 3000 | Open symbols |
|---|---:|---|---:|---:|---:|---:|---:|
| 0.01% | 1 | grid(anchor_period=200, entry_bps=50, step_bps=30) | 220 | 97.7% | 13.02 | 0.43% | 0 |
| 0.1% | 10 | ema_crossover(fast=9, slow=21) | 343 | 86.0% | 77.56 | 2.59% | 0 |
| 1% | 100 | grid(anchor_period=200, entry_bps=50, step_bps=30) | 758 | 99.3% | 1762.24 | 58.74% | 9 |

Important: the 1% top row is not fully closed at year end (`open? = 9`), so
its realized net excludes unresolved exposure. The best 1% row with `open? = 0`
was `grid(anchor_period=400, entry_bps=80, step_bps=40)`: 209 trades, 94.3%
win rate, 374.45 USDT net, 12.48% ROI on 3000 USDT.

Matrix files:

- `reports/compare_2025_active_8strats_tp1bp_by_month_with_risk_matrix.txt`
- `reports/compare_2025_active_8strats_tp10bp_by_month_with_risk_matrix.txt`
- `reports/compare_2025_active_8strats_tp100bp_by_month_with_risk_matrix.txt`
