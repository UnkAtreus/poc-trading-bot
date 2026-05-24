#!/usr/bin/env bash
set -euo pipefail
SYMS="UNIUSDT,ETHUSDT,XLMUSDT,LTCUSDT,SOLUSDT,BNBUSDT,XRPUSDT,LINKUSDT"
START="2025-05-24"
END="2026-05-24"
COMMON="--start $START --end $END --symbols $SYMS --by-month --with-risk --kline-workers 1 --execution-model realistic --execution-profile mainnet-like --margin-usd 100 --max-notional-per-symbol 4000 --max-notional-account 12500 --daily-loss-limit 5000 --initial-equity 30000"

run_stop() {
  local hours="$1"
  local log="logs/stop_max_hold_${hours}h_recommended8_1y_2026_05_24.txt"
  echo "=== 1y stop-max-hold ${hours}h start: $(date -u +%FT%TZ) ==="
  uv run python -m bot.main backtest $COMMON --stop-max-hold-hours "$hours" 2>&1 | tee "$log"
  echo "=== 1y stop-max-hold ${hours}h done: $(date -u +%FT%TZ) ==="
}

# Baseline (no stop) for direct ROI / DD comparison on the 1y window.
echo "=== 1y baseline (no stop) start: $(date -u +%FT%TZ) ==="
uv run python -m bot.main backtest $COMMON 2>&1 | tee "logs/stop_max_hold_baseline_recommended8_1y_2026_05_24.txt"
echo "=== 1y baseline done: $(date -u +%FT%TZ) ==="

run_stop 24
run_stop 72
run_stop 168
run_stop 336
run_stop 720

echo "STOP-MAX-HOLD 1Y SWEEP COMPLETE  $(date -u +%FT%TZ)"
