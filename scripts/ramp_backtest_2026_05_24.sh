#!/usr/bin/env bash
set -euo pipefail
SYMS="UNIUSDT,ETHUSDT,XLMUSDT,LTCUSDT,SOLUSDT,BNBUSDT,XRPUSDT,LINKUSDT"
START="2022-05-09"
END="2026-05-24"
COMMON="--start $START --end $END --symbols $SYMS --by-month --with-risk --kline-workers 1 --execution-model realistic --execution-profile mainnet-like"

run_phase() {
  local n="$1" eq="$2" margin="$3" psym="$4" acct="$5" daily="$6"
  local log="logs/ramp_phase${n}_eq${eq}_recommended8_2026_05_24.txt"
  echo "=== Phase $n start: equity=$eq margin=$margin per_sym=$psym acct=$acct daily=$daily ===  $(date -u +%FT%TZ)"
  uv run python -m bot.main backtest $COMMON \
    --margin-usd $margin \
    --max-notional-per-symbol $psym \
    --max-notional-account $acct \
    --daily-loss-limit $daily \
    --initial-equity $eq 2>&1 | tee "$log"
  echo "=== Phase $n done: $(date -u +%FT%TZ) ==="
}

run_phase 1 10000  33 1333  4167  1667
run_phase 2 15000  50 2000  6250  2500
run_phase 3 20000  67 2667  8333  3333
run_phase 4 25000  83 3333 10417  4167
run_phase 5 30000 100 4000 12500  5000

echo "ALL PHASES COMPLETE  $(date -u +%FT%TZ)"
