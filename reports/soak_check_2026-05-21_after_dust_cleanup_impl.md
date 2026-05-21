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

- Start UTC: `2026-05-20T09:04:46.833018+00:00`
- End UTC: `2026-05-21T09:04:46.833018+00:00`
- Source log: `/Users/atreus/Desktop/work/sideproject/poc-trading-bot/logs/testnet_dry_run_20260520_191136.log`

## Auto checks

- Verdict: **FAIL**
  - FAIL: bot restarts 1 > limit 0
  - FAIL: monitor severity is CRITICAL

## Evidence

- Bot restarts in window: `1`
- Heartbeats in window: `1252`
- Max heartbeat gap: `60.3s`
- Entries filled: `599`
- TPs filled: `676`
- Monitor severity: `CRITICAL`
- Bot alive (per monitor): `True`
- Kill switch: `False`

### Tracked event counts (window)

- `position_drift`: 1181
- `dust_stranded`: 118
- `place_order_failed`: 98
- `merge_tp_place_rejected`: 88
- `tp_place_rejected`: 31
- `reconcile.exit_order_missing`: 18

### Per-symbol resting state (non-IDLE)

- `BNBUSDT` state=`DUST_STRANDED` size=`0.009999999999999787` direction=`LONG`, first_fill_ts=`1779352988.054`
- `BTCUSDT` state=`DUST_STRANDED` size=`0.0009999999999999966` direction=`LONG`, first_fill_ts=`1779351126.066`
- `ETHUSDT` state=`DUST_STRANDED` size=`0.009999999999999953` direction=`SHORT`, first_fill_ts=`1779351281.854`
- `XRPUSDT` state=`DUST_STRANDED` size=`0.1` direction=`LONG`, first_fill_ts=`1778855736.527634`

## Question for the LLM

Apply the criteria from the preamble and emit the three answers requested.
