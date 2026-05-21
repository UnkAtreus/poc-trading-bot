#!/usr/bin/env bash
# Re-create the batch_optimize_stability shards + dashboard tmux sessions after
# a reboot. Each shard runs with --resume, so already-completed candidates are
# skipped (per-candidate progress is flushed to the shard CSV after every run).
#
# Usage:
#   bash scripts/relaunch_shards.sh
#
# Spawned tmux sessions:
#   batch_optimize    -> 8 windows (shard0..shard7) running the optimizer
#   dashboard         -> web (uvicorn :8080), tracker, throttle
#
# Commands are passed directly to tmux's $SHELL -c, so panes do NOT load the
# slow interactive .zshrc and do NOT suffer the ZLE-init send-keys race.

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

START="2024-01-01"
END="2026-05-01"
SYMBOLS="BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT"
MARGINS="10,20,30,50,66,80,100"
LEVERAGES="3,5,10"
ACCOUNT_CAPS="5000,7500,10000,12500,15000,20000"
SYMBOL_CAPS="500,1000,1500,2000,3000,4000"
TP_OFFSETS="30,50,75,100"
SHARD_COUNT=8
LIGHT_COUNT=4
HEAVY_COUNT=8
INITIAL_EQUITY=30000
SIGNAL="trend_filter"
CSV_PREFIX="logs/batch_optimize_stability_2024_2026_core"
REPORT_PREFIX="reports/batch_optimize_stability_2024_2026_core"
LOG_PREFIX="logs/batch_optimize_stability"

shard_cmd() {
  local i=$1
  printf '%s' "uv run python scripts/batch_optimize_stability.py \
--start ${START} --end ${END} --symbols ${SYMBOLS} \
--margins ${MARGINS} --leverages ${LEVERAGES} \
--account-caps ${ACCOUNT_CAPS} --symbol-caps ${SYMBOL_CAPS} \
--tp-offsets ${TP_OFFSETS} \
--target-monthly-roi-pct 0.5 --min-positive-month-pct 70 \
--min-target-month-pct 50 --max-non-positive-stretch 2 \
--max-worst-monthly-dd-pct 10 \
--shard-count ${SHARD_COUNT} --shard-index ${i} --resume \
2>&1 | tee -a ${LOG_PREFIX}_shard${i}of${SHARD_COUNT}.log"
}

# Wipe stale sessions so this script is idempotent.
tmux kill-session -t batch_optimize 2>/dev/null || true
tmux kill-session -t dashboard 2>/dev/null || true

mkdir -p logs reports data/state/backtests

# 8 shard windows in a single session.
for i in $(seq 0 $((SHARD_COUNT - 1))); do
  cmd="$(shard_cmd "$i")"
  if [ "$i" = "0" ]; then
    tmux new-session -d -s batch_optimize -n "shard0" -c "$REPO" "$cmd"
  else
    tmux new-window -t batch_optimize -n "shard$i" -c "$REPO" "$cmd"
  fi
done

# Dashboard server (uvicorn).
dashboard_cmd="DASHBOARD_PASSWORD=devpass uv run python scripts/run_dashboard.py \
--host 127.0.0.1 --port 8080 2>&1 | tee -a logs/dashboard_server.log"
tmux new-session -d -s dashboard -n web -c "$REPO" "$dashboard_cmd"

# Tracker: re-uses existing registry entries for in-progress shards (idempotent).
tracker_cmd="uv run python scripts/track_shard_registry.py \
--shard-count ${SHARD_COUNT} \
--csv-prefix ${CSV_PREFIX} \
--report-prefix ${REPORT_PREFIX} \
--log-prefix ${LOG_PREFIX} \
--start ${START} --end ${END} \
--signal ${SIGNAL} --symbols ${SYMBOLS} \
--initial-equity ${INITIAL_EQUITY} \
2>&1 | tee -a logs/track_shard_registry.log"
tmux new-window -t dashboard -n tracker -c "$REPO" "$tracker_cmd"

# Schedule supervisor: 4 active in light hours, 8 in heavy hours (Bangkok).
throttle_cmd="uv run python scripts/throttle_shards.py \
--light-count ${LIGHT_COUNT} --heavy-count ${HEAVY_COUNT} --poll-seconds 60 \
2>&1 | tee -a logs/throttle_shards.log"
tmux new-window -t dashboard -n throttle -c "$REPO" "$throttle_cmd"

cat <<EOF
relaunched:
  batch_optimize: $(tmux list-windows -t batch_optimize | wc -l | tr -d ' ') windows
  dashboard:      $(tmux list-windows -t dashboard | wc -l | tr -d ' ') windows

verify:
  tmux ls
  curl -s http://127.0.0.1:8080/healthz
  open http://127.0.0.1:8080/backtests   # login admin / devpass
EOF
