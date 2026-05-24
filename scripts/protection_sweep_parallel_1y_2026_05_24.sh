#!/usr/bin/env bash
set -euo pipefail
SYMS="BTCUSDT,UNIUSDT,ETHUSDT,XLMUSDT,LTCUSDT,SOLUSDT,BNBUSDT,XRPUSDT,LINKUSDT"
START="2025-05-24"
END="2026-05-24"
COMMON="--start $START --end $END --symbols $SYMS --by-month --with-risk --kline-workers 1 --execution-model realistic --execution-profile mainnet-like --margin-usd 100 --max-notional-per-symbol 4000 --max-notional-account 12500 --daily-loss-limit 5000 --initial-equity 30000"

CRASH_GUARD_SIG="crash_guard:inner=trend_filter:inner_inner=grid:inner_inner_anchor_period=200:inner_inner_entry_bps=50:inner_inner_step_bps=25:inner_max_trend_bps=20:btc_ema_period=200:btc_return_bars=1440:btc_drop_bps=500"

run_async() {
  local label="$1" log="$2"
  shift 2
  echo "=== ${label} start (parallel): $(date -u +%FT%TZ) ==="
  uv run python -m bot.main backtest $COMMON "$@" > "$log" 2>&1 && \
    echo "=== ${label} done: $(date -u +%FT%TZ) ===" || \
    echo "=== ${label} FAILED: $(date -u +%FT%TZ) ==="
}

# Launch all 6 in parallel.
run_async "baseline_9sym"    "logs/protection_sweep_baseline_9sym_1y_2026_05_24.txt" &
run_async "acct_dd_5pct"     "logs/protection_sweep_acct_dd_5pct_1y_2026_05_24.txt"  --stop-account-dd-pct 5 &
run_async "acct_dd_10pct"    "logs/protection_sweep_acct_dd_10pct_1y_2026_05_24.txt" --stop-account-dd-pct 10 &
run_async "acct_dd_15pct"    "logs/protection_sweep_acct_dd_15pct_1y_2026_05_24.txt" --stop-account-dd-pct 15 &
run_async "acct_dd_20pct"    "logs/protection_sweep_acct_dd_20pct_1y_2026_05_24.txt" --stop-account-dd-pct 20 &
run_async "crash_guard"      "logs/protection_sweep_crash_guard_1y_2026_05_24.txt"   --signal "$CRASH_GUARD_SIG" &

wait
echo "PROTECTION SWEEP (PARALLEL) COMPLETE  $(date -u +%FT%TZ)"
