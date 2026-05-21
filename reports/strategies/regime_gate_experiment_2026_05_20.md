# Regime Gate Experiment - 2026-05-20

Base strategy:

`trend_filter:inner=grid:inner_anchor_period=200:inner_entry_bps=50:inner_step_bps=25:max_trend_bps=20`

Test window:

`2024-10-30` to `2026-02-02`

Execution model:

`mainnet-like`, latency `0.3s`, with risk caps.

## Baseline

| Candidate | Annual ROI | Max DD | Read |
|---|---:|---:|---|
| `grid50_best` | `12.06%` | `22.57%` | Barely passes target, drawdown high |

Reference: `reports/compare_execution_2024_10_30_to_2026_02_02_grid50_best_mainnet_like.md`

## Gate Tests

| Candidate | Gate behavior | Annual ROI | Max DD | Read |
|---|---|---:|---:|---|
| `grid50_trend15` | Stricter per-symbol `max_trend_bps=15` | `11.82%` | `23.66%` | Worse than baseline |
| `regime_pause_ema25_adx25` | Pause all signals when BTC gate unsafe | `11.14%` | `65.31%` | Rejected; strands exposure |
| `regime_reduce50_ema25_adx25` | 50% size during unsafe BTC regime | `9.94%` | `15.69%` | Safer drawdown, too little ROI |
| `regime_blocknew_ema25_adx25` | Block fresh positions, allow layering | `11.30%` | `65.32%` | Rejected; high open exposure |
| `regime_reduce50_ema50_adx35` | Looser BTC gate, 50% size | `11.26%` | `14.45%` | Best risk reduction, still below target |

## Read

The first gate thresholds, `ema25/adx25`, were too active on 1-minute BTC data:
they marked about `35.6%` of ready minutes unsafe in this window.

Looser thresholds, `ema50/adx35`, marked about `12.2%` unsafe and gave the best
risk improvement. It reduced max drawdown from `22.57%` to `14.45%`, but it also
pulled realistic annual ROI below the `12%` minimum.

Current conclusion: do not set a regime gate as default yet. The gate is useful
as a risk-control tool, but this first version does not meet the return target.
The next viable path is to combine the looser size-reduction gate with either a
slightly higher TP/size profile or a separate strategy for trend regimes.
