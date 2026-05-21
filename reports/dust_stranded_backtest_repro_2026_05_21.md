# DUST_STRANDED Backtest Repro

Run date: 2026-05-21

Purpose: confirm that `DUST_STRANDED` can be reproduced in the backtest runner and affects the simulated state.

## Repro Setup

Synthetic candles:

```python
[
    Candle("BTCUSDT", 60.0, 100.0, 100.5, 99.5, 100.0, 1.0),
    Candle("BTCUSDT", 120.0, 100.0, 100.5, 99.93, 100.3, 1.0),
]
```

Signal: force one LONG on the first candle, then no further signal.

Sizing:

- Margin: `0.51 USDT`
- Leverage: `10`
- Entry notional: `5.10 USDT`

Execution:

- Realistic mode
- Latency: `0s`
- Cancel delay: `0s`
- Slippage: `0bps`
- Pass-through: `1bps`
- Full fill: `10bps`
- Min partial fill: `25%`

## Result

```text
trades         : 0
wins           : 0
losses         : 0
gross PnL      : +0.0000 USDT
fees (signed)  : -0.0002 USDT
net PnL        : +0.0002 USDT
execution      : realistic
exec stats     : accepted=1 rejected=1 partial=1 cancel_race=0 dust=1 slip_cost=0.0000

Final state:
  BTCUSDT: DUST_STRANDED size=0.017012758505313995 bep=99.9500
```

Key outcome:

- The entry partially filled.
- The TP placement was rejected because the remaining position was below exchange min notional/qty.
- The state machine moved to `DUST_STRANDED`.
- No closed trade was recorded.

## Existing Test Coverage

Confirmed passing:

```bash
uv run pytest \
  tests/unit/test_backtest_e2e.py::test_realistic_partial_entry_can_strand_dust_tp \
  tests/unit/test_simulator_fills.py::test_realistic_rejects_below_min_notional \
  -q
```

Result:

```text
2 passed in 0.16s
```

## Interpretation

Yes, `DUST_STRANDED` is backtestable. It is not only a final report label; it changes behavior because the state machine ignores candle closes and merge timers while stranded. The stranded dust remains in final state until a manual close or an external fill clears it.
