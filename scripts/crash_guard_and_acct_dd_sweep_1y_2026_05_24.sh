#!/usr/bin/env bash
set -euo pipefail
# 9 symbols = recommended8 + BTCUSDT. BTC is included so crash_guard
# receives BTC klines for its EMA/return calc; the bot will also trade BTC
# but that's the correct apples-to-apples baseline for this comparison.
SYMS="BTCUSDT,UNIUSDT,ETHUSDT,XLMUSDT,LTCUSDT,SOLUSDT,BNBUSDT,XRPUSDT,LINKUSDT"
START="2025-05-24"
END="2026-05-24"
COMMON="--start $START --end $END --symbols $SYMS --by-month --with-risk --kline-workers 1 --execution-model realistic --execution-profile mainnet-like --margin-usd 100 --max-notional-per-symbol 4000 --max-notional-account 12500 --daily-loss-limit 5000 --initial-equity 30000"

CRASH_GUARD_SIG="crash_guard:inner=trend_filter:inner_inner=grid:inner_inner_anchor_period=200:inner_inner_entry_bps=50:inner_inner_step_bps=25:inner_max_trend_bps=20:btc_ema_period=200:btc_return_bars=1440:btc_drop_bps=500"

run_variant() {
  local label="$1" log="$2"
  shift 2
  echo "=== ${label} start: $(date -u +%FT%TZ) ==="
  uv run python -m bot.main backtest $COMMON "$@" 2>&1 | tee "$log"
  echo "=== ${label} done: $(date -u +%FT%TZ) ==="
}

# Baseline (9-symbol, no stops, no crash_guard).
run_variant "baseline_9sym" "logs/protection_sweep_baseline_9sym_1y_2026_05_24.txt"

# Account-DD circuit breaker sweep.
for pct in 5 10 15 20; do
  run_variant "acct_dd_${pct}pct" "logs/protection_sweep_acct_dd_${pct}pct_1y_2026_05_24.txt" \
    --stop-account-dd-pct "$pct"
done

# Crash guard wrapper on the same signal stack.
run_variant "crash_guard" "logs/protection_sweep_crash_guard_1y_2026_05_24.txt" \
  --signal "$CRASH_GUARD_SIG"

echo "PROTECTION SWEEP COMPLETE  $(date -u +%FT%TZ)"
