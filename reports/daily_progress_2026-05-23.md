# Daily Progress — 2026-05-23

- Generated: 2026-05-23 ~10:55 ICT (03:55 UTC)
- Active mode: `testnet`
- Active tmux session: `testnet_dry_run`
- Active log: `logs/testnet_dry_run_20260522_170216.log`
- Active config: `config/bot.yaml` = `grid50_best` (trend_filter wrapping grid, anchor 200, entry 50 bps, step 25 bps, max_trend 20 bps), margin 100 × 10x, caps 4,000 / 12,500, daily loss 5,000, TP 75 bps, merge timer 1,800s `first_fill`.
- Active symbols: BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, LTCUSDT.

## Run summary

- Bot.start UTC: `2026-05-22T17:02:16Z` (ICT 2026-05-23 00:02).
- Uptime at snapshot: ~17h 53m.
- Process alive: PID 62702 (.venv python -m bot.main run), parent tmux session `testnet_dry_run`.
- Kill switch: not triggered.
- Severity (from `reports/live_monitor.md` at 17:54 UTC): `OK`. No alerts.

### Equity / PnL (last live_monitor snapshot)

- Total equity: `110029.32 USDT` (started 30,000 baseline).
- Total available balance: `110026.55 USDT`.
- USDT unrealised PnL: `0.00560 USDT`.
- Daily closed PnL: `+1266.95 USDT`.

Caveat: daily PnL since the previous testnet session adopted positions into this session — the +1,267 USDT is mostly carry-over realisation, not 17h fresh-strategy proof.

### Per-symbol state (latest)

| Symbol  | State                  | Source                                    |
|---------|------------------------|-------------------------------------------|
| BTCUSDT | IDLE                   | `data/state/BTCUSDT.json` (mtime 10:54)   |
| ETHUSDT | IDLE                   | TP filled 00:56:23Z (0.01 @ 2007.55)      |
| SOLUSDT | IDLE                   | no activity                               |
| XRPUSDT | IDLE                   | no activity                               |
| BNBUSDT | **MERGE_PENDING**      | size 0.12, BEP 142.0, first_fill 02:09:29Z |
| LTCUSDT | IDLE                   | testnet contract not live (see issue)     |

## Event tally (17h log)

| Event                                | Count |
|--------------------------------------|------:|
| heartbeat                            | 652   |
| position_drift                       | 5     |
| reconcile.adopt_exchange_position    | 4     |
| reconcile.size_drift                 | 4     |
| execution_skipped_pre_adopt          | 5     |
| tp_filled                            | 2     |
| reconcile.force_idle                 | 1     |
| set_leverage_error                   | 1     |
| entry_filled                         | 0     |
| entry_blocked / entry_below_min      | 0     |
| tp_place_rejected / merge_tp_rejected| 0     |
| merge_filled                         | 0     |

Note on the 0 `entry_filled`: orchestrator does **not** log successful `place_limit` calls — only failures, blocks, and fills. So entries can be silently placed and cancelled at the next candle without leaving log evidence. The two filled TPs (ETHUSDT, BNBUSDT) both fired against positions that were **adopted via reconcile from the prior session**, not entries opened inside this run. No `entry_filled` for a fresh entry on this run.

## Issues observed

1. **WS private stream goes stale repeatedly.**
   Heartbeat shows `private.status: stale` with `last_msg_age_seconds` climbing past 3,000s before reconnect. Bot survives because `_reconcile_all` polls REST, but on live the gap is a window where local SM state can diverge from exchange. Worth tracking what the reconnect cadence is and whether it's pybit ping/keepalive related.

2. **BNBUSDT stuck in MERGE_PENDING ~1h44m+.**
   Adopted at 02:09:29Z (size 0.21, BEP 142.0). Partial TP fill at 02:10:38Z reduced to 0.14. Reconcile force-corrected to 0.12 at 02:13:06. Merge timer should fire at 02:39:29Z; state file confirms `state: MERGE_PENDING`, but the merge TP at `142 × (1 + 0.0075) = 143.07` hasn't filled. No `merge_filled` event yet. Position is small ($17 notional), but still illustrates the v1 caveat: there is **no exit if BEP recovery never prints**.

3. **`set_leverage_error` for LTCUSDT on testnet.**
   `closed symbol error: This LTCUSDT contract is not live (ErrCode: 110074)`. Testnet-only — confirm LTCUSDT is live on mainnet before switching.

4. **Strategy productivity is low in current testnet market.**
   Two TP fills in 17h, both from prior-session positions. No `entry_blocked`/`risk_halt` events. Either grid50_best simply isn't firing on this stretch of testnet candles, or successful entry placements are silent and getting cancelled at next candle. Cannot tell from logs alone.

5. **Logging gap: no `entry.placed` / `entry.cancelled_on_next_candle` event.**
   Hard to audit how often a signal fires, places, and times out. Worth a small log addition before mainnet.

## Mainnet readiness verdict: **NOT READY**

Three categories must clear before going live:

### A. Strategy validation — **fail**
- Only 2 TPs in 17h soak, both from carried-over positions.
- Per `CLAUDE.md`: "soak on testnet ≥ 1 week before mainnet". Current continuous fresh-config soak is well below that.
- Need a soak that shows N≥30 fresh entries firing through the full lifecycle (entry → TP or entry → merge → close) without manual intervention.

### B. Operational stability — **partial pass**
- 17h continuous uptime, no exceptions, kill switch quiet. Good.
- Reconcile-driven force_idle / adopt_exchange_position both observed and worked. Good.
- WS private repeated stale gaps. **Acceptable on testnet, risky on mainnet.** Needs root-cause check (ping interval, network, pybit version) before live money.

### C. Strategy economics — **fail**
- Carry-over PnL doesn't validate the live signal.
- `grid50_best` 2026-YTD backtest annualised ROI was 6.06% with 7.48% max DD (per `compare_execution_2026_01_01_to_2026_05_20_grid50_best_plus_virtual_mainnet_like.md` baseline figures). Below the 12% annual target referenced in the regime gate notes.
- No `crash_guard` wrapper, no regime gate. The v3 crash-balanced config still exists but isn't loaded; on a sudden adverse trend, max DD historically reached 38% (v3 2021-now backtest).

## Pre-mainnet checklist

| # | Item                                                                       | Status |
|---|----------------------------------------------------------------------------|--------|
| 1 | ≥7-day continuous testnet soak on current `grid50_best`                   | open   |
| 2 | ≥30 fresh entries observed in soak window                                  | open   |
| 3 | WS private stale gap reduced (or documented mitigation)                    | open   |
| 4 | Confirm LTCUSDT mainnet contract live before launch                        | open   |
| 5 | Add `entry.placed` + `entry.cancelled_at_next_candle` log events           | open   |
| 6 | Resolve BNBUSDT MERGE_PENDING (let it close or document manual unstick SOP)| open   |
| 7 | Decision: keep `grid50_best` bare, or layer `crash_guard` / `regime_gate`  | open   |
| 8 | Verify `MAINNET_CONFIRM=YES_I_MEAN_IT` workflow + `data/state/KILL` drill  | open   |
| 9 | Cap sanity for live equity (currently 30k baseline; live wallet may differ)| open   |
| 10| Dry-run dust_cleanup once on mainnet symbol before scaling                 | open   |

## Recommendation

Stay on testnet. Let `testnet_dry_run` continue for at least the rest of this week. Re-run this readiness check after:
- BNBUSDT MERGE_PENDING resolves (or the SOP is written), and
- the log shows ≥30 fresh `tp_filled` + `merge_filled` events without manual intervention, and
- WS private stale gaps either disappear or are explained.

Reconvene on the mainnet vs. testnet question after that soak window.
