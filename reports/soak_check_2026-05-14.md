# Soak Check

You are auditing a single soak day for a Bybit USDT-perp testnet trading bot.
The team wants ≥7 consecutive clean days before promoting to mainnet.

Read the evidence below and answer:

1. Does this day count as CLEAN toward the 7-day window? (yes / no)
2. If no, which specific signal(s) disqualify it?
3. Anything else worth investigating before tomorrow's check?

A clean day means: no CRITICAL alerts; zero reconcile.failed / fatal order
rejections; heartbeat continuous (gaps < 2 min); no symbols stuck in
ENTRY_PENDING / MERGE_PENDING / IN_POSITION_TP_PENDING past the merge timer;
no kill switch trip; ≥ a few real round-trip trades (silence with zero
trades doesn't validate the lifecycle).


## Window

- Start UTC: `2026-05-13T04:22:45.359384+00:00`
- End UTC: `2026-05-14T04:22:45.359384+00:00`
- Source log: `/Users/atreus/Desktop/work/sideproject/poc-trading-bot/logs/testnet_dry_run_20260514_042012.log`

## Auto checks

- Verdict: **FAIL**
  - FAIL: bot restarts 1 > limit 0
  - FAIL: monitor severity is WARN

## Evidence

- Bot restarts in window: `1`
- Heartbeats in window: `0`
- Max heartbeat gap: `n/a (need ≥2 heartbeats)`
- Entries filled: `0`
- TPs filled: `0`
- Monitor severity: `WARN`
- Bot alive (per monitor): `True`
- Kill switch: `False`

### Tracked event counts (window)

- All tracked events: 0

### Per-symbol resting state (non-IDLE)

- All symbols IDLE.

## Question for the LLM

Apply the criteria from the preamble and emit the three answers requested.
