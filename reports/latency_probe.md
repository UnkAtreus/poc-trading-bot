# Latency probe — live rolling stats

- Updated: `2026-05-24 10:48:13Z`
- Uptime: `9241s`
- Mode: `testnet`
- Symbol: `UNIUSDT`
- REST probe interval: `5.0s`
- Rolling window size: `200`

## Latency (ms)

| Metric | n | min | p50 | p90 | p99 | max | mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| `rest_server_time_ms` | 200 | 38.51 | 98.34 | 101.41 | 166.75 | 178.44 | 91.8 |
| `ws_kline_age_ms` | 155 | 661.53 | 674.04 | 682.27 | 683.55 | 12599.35 | 750.82 |

## Reference profiles (from `src/bot/backtest/execution.py`)

| Profile | latency | cancel | slippage | min partial |
|---|---:|---:|---:|---:|
| `mainnet-like` | 0.30s | 0.50s | 1.0 bps | 50% |
| `conservative` | 1.00s | 3.00s | 2.0 bps | 25% |

- If observed `rest_server_time_ms.p90` stays under ~200ms and `ws_kline_age_ms.p90` under ~500ms, the live path matches the `mainnet-like` assumptions.
- If either p90 exceeds 1000ms regularly, real execution is closer to the `conservative` profile and the strategy may underperform vs the mainnet-like backtest.
