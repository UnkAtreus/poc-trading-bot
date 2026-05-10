# V2 Stop-Loss Sweep - 2024-2025 Continuous

- Date range: `2024-01-01` to `2026-01-01`
- Initial equity: `30,000 USDT`
- Strategy: v2, TP 100 bps, margin/order 114 USDT, leverage 10x
- Target marker: `36% ROI` over two years, equal to 1.5% average per month.
- Stop execution model: forced market/taker close in backtest.
- Raw CSV: `logs/v2_stop_sweep_2024_2025_equity30000.csv`

## Result

Best target-first candidate: `hold24`.

| Case | Net PnL | ROI | Account max DD | Worst monthly DD | Trades | Win rate | Losses | Stop exits | Open symbols | Target? |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hold24 | 10,863.22 | 36.21% | 11.39% | 10.57% | 8965 | 77.99% | 1973 | 2177 | 4 | yes |

## Lowest Account Drawdown

| Case | Net PnL | ROI | Account max DD | Worst monthly DD | Trades | Win rate | Losses | Stop exits | Open symbols | Target? |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| acct10 | -1,943.93 | -6.48% | 10.05% | 10.05% | 118 | 94.92% | 6 | 6 | 0 | no |
| hold24 | 10,863.22 | 36.21% | 11.39% | 10.57% | 8965 | 77.99% | 1973 | 2177 | 4 | yes |
| hold24_acct15 | 10,863.22 | 36.21% | 11.39% | 10.57% | 8965 | 77.99% | 1973 | 2177 | 4 | yes |
| hold24_acct20 | 10,863.22 | 36.21% | 11.39% | 10.57% | 8965 | 77.99% | 1973 | 2177 | 4 | yes |
| hold24_symbol1500 | 10,863.22 | 36.21% | 11.39% | 10.57% | 8965 | 77.99% | 1973 | 2177 | 4 | yes |
| hold24_symbol2000 | 10,863.22 | 36.21% | 11.39% | 10.57% | 8965 | 77.99% | 1973 | 2177 | 4 | yes |
| hold24_symbol1500_acct20 | 10,863.22 | 36.21% | 11.39% | 10.57% | 8965 | 77.99% | 1973 | 2177 | 4 | yes |
| symbol1500 | 4,512.08 | 15.04% | 14.11% | 11.98% | 788 | 98.73% | 10 | 8 | 7 | no |
| symbol1500_acct20 | 4,512.08 | 15.04% | 14.11% | 11.98% | 788 | 98.73% | 10 | 8 | 7 | no |
| acct15 | 1,700.68 | 5.67% | 15.08% | 12.62% | 386 | 98.45% | 6 | 6 | 0 | no |
| bep1000 | 3,597.00 | 11.99% | 16.99% | 12.83% | 5467 | 91.49% | 465 | 455 | 7 | no |
| acct20 | 212.07 | 0.71% | 20.04% | 17.58% | 386 | 98.70% | 5 | 5 | 0 | no |
| symbol1000 | 1,966.14 | 6.55% | 22.31% | 10.33% | 1274 | 98.12% | 24 | 24 | 7 | no |
| symbol2000 | 5,912.61 | 19.71% | 27.15% | 16.42% | 926 | 98.70% | 12 | 7 | 7 | no |
| hold48 | 3,843.31 | 12.81% | 31.41% | 15.31% | 6392 | 83.09% | 1081 | 1137 | 6 | no |
| hold72 | -5,018.67 | -16.73% | 34.49% | 16.02% | 5114 | 85.31% | 751 | 777 | 7 | no |
| bep500 | -6,888.44 | -22.96% | 41.55% | 12.28% | 8584 | 83.91% | 1381 | 1372 | 7 | no |
| bep300 | -8,821.50 | -29.41% | 42.17% | 10.16% | 11702 | 75.58% | 2858 | 2854 | 6 | no |
| baseline | 14,908.50 | 49.70% | 62.24% | 36.46% | 680 | 100.00% | 0 | 0 | 7 | yes |

## Highest ROI

| Case | Net PnL | ROI | Account max DD | Worst monthly DD | Trades | Win rate | Losses | Stop exits | Open symbols | Target? |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 14,908.50 | 49.70% | 62.24% | 36.46% | 680 | 100.00% | 0 | 0 | 7 | yes |
| hold24 | 10,863.22 | 36.21% | 11.39% | 10.57% | 8965 | 77.99% | 1973 | 2177 | 4 | yes |
| hold24_acct15 | 10,863.22 | 36.21% | 11.39% | 10.57% | 8965 | 77.99% | 1973 | 2177 | 4 | yes |
| hold24_acct20 | 10,863.22 | 36.21% | 11.39% | 10.57% | 8965 | 77.99% | 1973 | 2177 | 4 | yes |
| hold24_symbol1500 | 10,863.22 | 36.21% | 11.39% | 10.57% | 8965 | 77.99% | 1973 | 2177 | 4 | yes |
| hold24_symbol2000 | 10,863.22 | 36.21% | 11.39% | 10.57% | 8965 | 77.99% | 1973 | 2177 | 4 | yes |
| hold24_symbol1500_acct20 | 10,863.22 | 36.21% | 11.39% | 10.57% | 8965 | 77.99% | 1973 | 2177 | 4 | yes |
| symbol2000 | 5,912.61 | 19.71% | 27.15% | 16.42% | 926 | 98.70% | 12 | 7 | 7 | no |
| symbol1500 | 4,512.08 | 15.04% | 14.11% | 11.98% | 788 | 98.73% | 10 | 8 | 7 | no |
| symbol1500_acct20 | 4,512.08 | 15.04% | 14.11% | 11.98% | 788 | 98.73% | 10 | 8 | 7 | no |
| hold48 | 3,843.31 | 12.81% | 31.41% | 15.31% | 6392 | 83.09% | 1081 | 1137 | 6 | no |
| bep1000 | 3,597.00 | 11.99% | 16.99% | 12.83% | 5467 | 91.49% | 465 | 455 | 7 | no |
| symbol1000 | 1,966.14 | 6.55% | 22.31% | 10.33% | 1274 | 98.12% | 24 | 24 | 7 | no |
| acct15 | 1,700.68 | 5.67% | 15.08% | 12.62% | 386 | 98.45% | 6 | 6 | 0 | no |
| acct20 | 212.07 | 0.71% | 20.04% | 17.58% | 386 | 98.70% | 5 | 5 | 0 | no |
| acct10 | -1,943.93 | -6.48% | 10.05% | 10.05% | 118 | 94.92% | 6 | 6 | 0 | no |
| hold72 | -5,018.67 | -16.73% | 34.49% | 16.02% | 5114 | 85.31% | 751 | 777 | 7 | no |
| bep500 | -6,888.44 | -22.96% | 41.55% | 12.28% | 8584 | 83.91% | 1381 | 1372 | 7 | no |
| bep300 | -8,821.50 | -29.41% | 42.17% | 10.16% | 11702 | 75.58% | 2858 | 2854 | 6 | no |

## Read

The best target-first option is `hold24`: max-hold stop at 24 hours. It is the only tested stop setup that still reaches the 36% two-year target while reducing account max DD sharply, from 62.24% to 11.39%.

Adding account-DD or symbol-loss stops on top of 24h hold did not improve the result. They reduced profit below the 36% two-year target or produced no practical DD improvement versus plain 24h hold.

Max symbol-loss stops reduce DD materially and preserve high win rate, but they do not meet the profit target. Among those, `symbol1500` is the cleanest conservative profile: 15.04% ROI, 14.11% account max DD, 98.73% win rate.

Account-DD hard stops protect the account but stop trading too early, so ROI becomes poor. BEP-bps stops are not suitable here; 300 and 500 bps are net negative, and 1000 bps misses target.

## All Cases

| Case | Net PnL | ROI | Account max DD | Worst monthly DD | Trades | Win rate | Losses | Stop exits | Open symbols | Target? |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 14,908.50 | 49.70% | 62.24% | 36.46% | 680 | 100.00% | 0 | 0 | 7 | yes |
| bep300 | -8,821.50 | -29.41% | 42.17% | 10.16% | 11702 | 75.58% | 2858 | 2854 | 6 | no |
| bep500 | -6,888.44 | -22.96% | 41.55% | 12.28% | 8584 | 83.91% | 1381 | 1372 | 7 | no |
| bep1000 | 3,597.00 | 11.99% | 16.99% | 12.83% | 5467 | 91.49% | 465 | 455 | 7 | no |
| symbol1000 | 1,966.14 | 6.55% | 22.31% | 10.33% | 1274 | 98.12% | 24 | 24 | 7 | no |
| symbol1500 | 4,512.08 | 15.04% | 14.11% | 11.98% | 788 | 98.73% | 10 | 8 | 7 | no |
| symbol2000 | 5,912.61 | 19.71% | 27.15% | 16.42% | 926 | 98.70% | 12 | 7 | 7 | no |
| acct10 | -1,943.93 | -6.48% | 10.05% | 10.05% | 118 | 94.92% | 6 | 6 | 0 | no |
| acct15 | 1,700.68 | 5.67% | 15.08% | 12.62% | 386 | 98.45% | 6 | 6 | 0 | no |
| acct20 | 212.07 | 0.71% | 20.04% | 17.58% | 386 | 98.70% | 5 | 5 | 0 | no |
| hold24 | 10,863.22 | 36.21% | 11.39% | 10.57% | 8965 | 77.99% | 1973 | 2177 | 4 | yes |
| hold48 | 3,843.31 | 12.81% | 31.41% | 15.31% | 6392 | 83.09% | 1081 | 1137 | 6 | no |
| hold72 | -5,018.67 | -16.73% | 34.49% | 16.02% | 5114 | 85.31% | 751 | 777 | 7 | no |
| hold24_acct15 | 10,863.22 | 36.21% | 11.39% | 10.57% | 8965 | 77.99% | 1973 | 2177 | 4 | yes |
| hold24_acct20 | 10,863.22 | 36.21% | 11.39% | 10.57% | 8965 | 77.99% | 1973 | 2177 | 4 | yes |
| hold24_symbol1500 | 10,863.22 | 36.21% | 11.39% | 10.57% | 8965 | 77.99% | 1973 | 2177 | 4 | yes |
| hold24_symbol2000 | 10,863.22 | 36.21% | 11.39% | 10.57% | 8965 | 77.99% | 1973 | 2177 | 4 | yes |
| hold24_symbol1500_acct20 | 10,863.22 | 36.21% | 11.39% | 10.57% | 8965 | 77.99% | 1973 | 2177 | 4 | yes |
| symbol1500_acct20 | 4,512.08 | 15.04% | 14.11% | 11.98% | 788 | 98.73% | 10 | 8 | 7 | no |
