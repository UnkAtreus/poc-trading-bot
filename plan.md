# Plan: Resumable Batch Optimizer

## Goal

Replace the current long `optimize-stability` CLI run with a batch optimizer that can safely handle large grids such as 3,024+ candidates without losing progress.

The current optimizer is too slow for large sweeps because it:

- keeps all results in memory
- prints the table only after every candidate finishes
- cannot resume after interruption
- gives no progress estimate
- retests many duplicate/low-value parameter combinations

The new optimizer should write one result row per completed candidate and be resumable.

## Requirements

- Load candle data once per run.
- Generate candidate grid from CLI arguments.
- Before running a candidate, check whether it already exists in the output CSV.
- After each candidate finishes, append one row to CSV immediately.
- Print progress:

```text
[153/3024] margin=30 leverage=5 account_cap=7500 symbol_cap=1000 tp=50 safe=True stable=False elapsed=01:22:10 eta=25:40:00
```

- Support resume:

```bash
uv run python scripts/batch_optimize_stability.py --resume ...
```

- Produce:

```text
logs/batch_optimize_stability_2024_2026_core.csv
reports/batch_optimize_stability_2024_2026_core.md
```

## Output CSV Columns

Each completed candidate writes one row:

```text
candidate_id
start
end
symbols
margin_usd
leverage
account_cap
symbol_cap
tp_offset_bps
trades
wins
losses
win_rate_pct
net_pnl
roi_pct
max_drawdown
max_drawdown_pct
liquidated
near_liquidation
min_liq_distance_pct
margin_ratio_max
worst_unrealized_loss
final_open_exposure
months
positive_month_pct
target_month_pct
avg_monthly_roi_pct
median_monthly_roi_pct
worst_monthly_roi_pct
worst_monthly_dd_pct
longest_non_positive_stretch
stability_score
safe
stable
launch_pass
elapsed_seconds
error
```

## Safety Gates

Candidate is `safe=False` if any are true:

```text
liquidated = true
near_liquidation = true
max_drawdown_pct > 25
final_open_exposure > 5000
```

Candidate is `stable=False` if any are true:

```text
positive_month_pct < 70
target_month_pct < 50
longest_non_positive_stretch > 2
worst_monthly_dd_pct > 10
```

Candidate is `launch_pass=True` only if:

```text
safe = true
stable = true
```

## Pruning Rules

Add conservative pruning before running a candidate:

- Skip if `margin_usd * leverage > symbol_cap`.
  - Reason: one order already exceeds per-symbol cap.
- Skip if `margin_usd * leverage > account_cap`.
  - Reason: one order already exceeds account cap.
- Skip if `symbol_cap * symbol_count < margin_usd * leverage`.
  - Defensive duplicate of impossible exposure capacity.
- Optional later: skip candidates whose account cap is much higher than launch open-exposure gate unless testing aggressive mode.

Skipped candidates should still write a CSV row with:

```text
safe=false
stable=false
launch_pass=false
error="pruned:<reason>"
```

## Resume Logic

Candidate identity:

```text
candidate_id = sha1(
  start,end,symbols,signal,margin_usd,leverage,account_cap,symbol_cap,tp_offset_bps,stops
)
```

On startup:

1. If CSV exists, load completed `candidate_id` values.
2. Generate full grid.
3. Skip completed candidates.
4. Continue appending new rows.

This allows stopping and restarting safely.

## Report Generation

After the CSV is complete or partially complete, generate a markdown report:

```bash
uv run python scripts/batch_optimize_stability.py --report-only \
  --csv logs/batch_optimize_stability_2024_2026_core.csv \
  --output-report reports/batch_optimize_stability_2024_2026_core.md
```

Report sections:

- Run config
- Candidate count
- Completed count
- Pruned count
- Error count
- Launch-pass count
- Top 20 launch-pass candidates
- Top 20 safe but not stable candidates
- Top 20 by stability score
- Worst 20 by drawdown
- Recommended lot size
- Decision: `trade`, `reduce_size`, or `no_trade`

## Implementation Steps

1. Create `scripts/batch_optimize_stability.py`.
2. Reuse existing functions:
   - `load_or_fetch`
   - `df_to_candles`
   - `run_backtest`
   - `RiskManager`
   - `build_signal`
   - `analyze_stability`
3. Add candidate grid generation.
4. Add candidate ID hashing.
5. Add CSV append writer.
6. Add resume loader.
7. Add pruning.
8. Add progress and ETA.
9. Add report-only mode.
10. Smoke test with `--max-candidates 3`.
11. Run unit tests.

## Example Command

```bash
uv run python scripts/batch_optimize_stability.py \
  --start 2024-01-01 \
  --end 2026-05-01 \
  --symbols BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,LTCUSDT \
  --margins 10,20,30,50,66,80,100 \
  --leverages 3,5,10 \
  --account-caps 5000,7500,10000,12500,15000,20000 \
  --symbol-caps 500,1000,1500,2000,3000,4000 \
  --tp-offsets 30,50,75,100 \
  --target-monthly-roi-pct 0.5 \
  --min-positive-month-pct 70 \
  --min-target-month-pct 50 \
  --max-non-positive-stretch 2 \
  --max-worst-monthly-dd-pct 10 \
  --output-csv logs/batch_optimize_stability_2024_2026_core.csv \
  --output-report reports/batch_optimize_stability_2024_2026_core.md \
  --resume
```

## Acceptance Criteria

- Can stop and restart without losing completed rows.
- Writes CSV after every candidate.
- Shows progress and ETA.
- Produces markdown report from partial or complete CSV.
- Smoke run completes successfully.
- Existing unit tests pass.
- Full 3,024-candidate grid can be run overnight with visible progress.

