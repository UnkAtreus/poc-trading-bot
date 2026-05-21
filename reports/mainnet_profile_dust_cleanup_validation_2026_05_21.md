# Dust Cleanup And Mainnet Profile Validation

Generated: 2026-05-21

## Implemented

- Added `dust_cleanup` config with `enabled`, `max_attempts`, and `retry_seconds`.
- Added live exchange `close_position_market()` using Bybit reduce-only market close with `qty=0`.
- Wired orchestrator reconcile to submit bounded dust cleanup attempts only while a symbol is already `DUST_STRANDED`.
- Added loadable profile directories:
  - `config/profiles/mainnet_canary_uni_eth`
  - `config/profiles/mainnet_canary4_uni_eth_xlm_ltc`
  - `config/profiles/mainnet_real_recommended8`
- Added `--config-dir` support to the main CLI and live monitor.

## Testnet Cleanup

Mode verified as `testnet` before cleanup.

Closed and cleared these stranded testnet positions:

- `BNBUSDT` long `0.01`, close order accepted, exchange reported flat.
- `BTCUSDT` long `0.001`, close order accepted, exchange reported flat.
- `ETHUSDT` short `0.01`, close order accepted, exchange reported flat.
- `XRPUSDT` long `0.1`, close order accepted, exchange reported flat.

Local state files for those symbols were reset to `IDLE` only after exchange reported flat.

## Active Testnet Canary

- tmux session: `testnet_canary_uni_eth`
- profile: `config/profiles/mainnet_canary_uni_eth`
- symbols: `UNIUSDT`, `ETHUSDT`
- log: `logs/testnet_canary_uni_eth_20260521_160616.log`
- monitor: `reports/live_monitor.md`
- alerts: `reports/live_alerts.md`

Latest monitor result:

- severity: `OK`
- issues: `0`
- bot alive: `True`
- positions: none
- open orders: none
- states: `UNIUSDT=IDLE`, `ETHUSDT=IDLE`

## Validation Commands Passed

- `uv run python -m compileall src/bot/config.py src/bot/exchange/base.py src/bot/exchange/bybit_live.py src/bot/strategy/orchestrator.py src/bot/main.py`
- `uv run python -m compileall scripts/monitor_live.py`
- `uv run pytest tests/unit/test_orchestrator_order_rejections.py tests/unit/test_soak_check.py -q`
- `uv run pytest tests/unit/test_backtest_e2e.py::test_realistic_partial_entry_can_strand_dust_tp tests/unit/test_simulator_fills.py::test_realistic_rejects_below_min_notional -q`
- Profile load check for canary2, canary4, and real8.

## Promotion Path

1. Keep current `UNIUSDT` + `ETHUSDT` canary running until operation is clean.
2. Expand to `config/profiles/mainnet_canary4_uni_eth_xlm_ltc` after clean operation.
3. Use `config/profiles/mainnet_real_recommended8` only after canary4 is clean and mainnet launch is explicitly confirmed.
