# Current Coin Graph Types

Generated UTC: 2026-05-03 02:17

| Symbol | Graph type | Last | 24h | 7d | 30d | 1m EMA trend bps | Strategy fit |
|---|---|---:|---:|---:|---:|---:|---|
| BTCUSDT | MIXED / range-trend | 78113.10 | -0.22% | 0.73% | 17.15% | 17.08 | v3 preferred |
| ETHUSDT | MIXED / range-trend | 2300.70 | 0.19% | -0.69% | 11.91% | 18.70 | v3 preferred |
| SOLUSDT | MIXED / range-trend | 83.60 | -0.43% | -2.99% | 5.26% | 19.21 | v3 preferred |
| XRPUSDT | MIXED / range-trend | 1.38 | -0.25% | -2.77% | 5.03% | 21.25 | v3 preferred |
| BNBUSDT | SIDEWAYS / chop | 615.00 | -0.10% | -2.26% | 5.09% | 12.57 | v1/v2/v3 all ok; v2/v3 more active |
| LTCUSDT | SIDEWAYS / chop | 54.94 | -1.01% | -1.75% | 4.77% | 14.68 | v1/v2/v3 all ok; v2/v3 more active |
| HYPEUSDT | SIDEWAYS / chop | 41.06 | -0.48% | -1.01% | 15.51% | 9.44 | v1/v2/v3 all ok; v2/v3 more active |
| XAUTUSDT | SIDEWAYS / chop | 4597.00 | -0.06% | -1.93% | -0.95% | 0.12 | v1/v2/v3 all ok; v2/v3 more active |

Rules used:

- `CRASH-RISK`: 24h return <= -5% and price below 1-day EMA.
- `DOWNTREND`: 7d return <= -8% and price below 1-day EMA.
- `SIDEWAYS`: low short-term EMA trend and 24h move inside +/-3%.
- `MIXED`: not cleanly sideways or trend; use v3 preference because crash guard is safer.
