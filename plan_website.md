# Web Dashboard Implementation Plan

## Summary

Build a password-protected FastAPI dashboard for monitoring the trading bot and controlling only safe operations. The dashboard should be usable locally and on a VPS through SSH tunnel or reverse proxy.

Primary goals:

- Show live bot health, monitor severity, heartbeat, kill switch status, wallet balance, daily PnL, positions, and open orders.
- Show trading/order detail, local bot state, compact AI context, alerts, and filtered log events.
- Show current safe settings: mode, lot size, leverage, symbols, risk caps, offsets, and signal params.
- Support dark/light mode.
- Support safe actions: create/clear kill switch, regenerate monitor report, regenerate AI context, and start controlled backtests.
- Avoid exposing API keys, API secrets, or raw `.env` content.

## Stack

Use a Python-only stack to fit the current repo:

- `FastAPI` for the web app.
- `uvicorn` for serving.
- `Jinja2` for server-rendered HTML.
- Plain CSS/JS for UI, theme toggle, charts, and refresh behavior.

Do not add React/Vite in v1.

Required dependency additions:

```toml
fastapi
uvicorn
jinja2
python-multipart
```

## Security

Dashboard access must require password auth.

Default access model:

- Bind to `127.0.0.1`.
- Access remotely using SSH tunnel:

```bash
ssh -L 8080:127.0.0.1:8080 user@server
```

Environment:

```env
DASHBOARD_PASSWORD=change-this
```

Rules:

- Username: `admin`.
- Password comes from `DASHBOARD_PASSWORD`.
- If `DASHBOARD_PASSWORD` is missing, dashboard routes should return unavailable except `/healthz`.
- Never display `BYBIT_API_KEY`, `BYBIT_API_SECRET`, or full `.env`.
- Mainnet mode must show a persistent warning banner.

## File Layout

Add:

```text
src/bot/dashboard/
  __init__.py
  app.py
  service.py
  templates/
    base.html
    overview.html
    trading.html
    settings.html
    alerts.html
    logs.html
    backtests.html
  static/
    dashboard.css
    dashboard.js

scripts/run_dashboard.py
tests/unit/test_dashboard.py
```

Use existing files as data sources:

```text
reports/live_monitor.md
reports/live_alerts.md
reports/live_ai_context.md
logs/live_monitor.jsonl
logs/ai_context.jsonl
logs/*.log
data/state/*.json
data/state/KILL
config/bot.yaml
config/symbols.yaml
```

## Pages

### Overview

Show:

- Monitor severity.
- Bot alive.
- Latest heartbeat and heartbeat age.
- Kill switch active/inactive.
- Mode: testnet/mainnet.
- Wallet total equity, available balance, USDT equity.
- Daily closed PnL and unrealized PnL.
- Open positions count.
- Open orders count.
- Current bot state per symbol.

Actions:

- Regenerate monitor report.
- Regenerate AI context.
- Create kill switch with typed confirmation `KILL`.
- Clear kill switch with typed confirmation `CLEAR`.

### Trading

Show:

- Open positions table:
  - symbol
  - side
  - size
  - avg/BEP
  - mark price
  - notional
  - unrealized PnL
- Open orders table:
  - symbol
  - side
  - purpose
  - qty
  - price
  - reduceOnly
  - order link id
- Local state table from `data/state/*.json`.
- Compact recent important events from AI context/log parser.

### Balance & Profit

Can be part of Overview in v1.

Show:

- Total equity.
- Wallet balance.
- Available balance.
- Daily closed PnL.
- Unrealized PnL.
- Cumulative realized PnL if available from monitor.

Graph:

- V1 can use latest `logs/live_monitor.jsonl`.
- If monitor history is later appended, graph equity/PnL over time.

### Settings

Show safe config only:

- `sizing.margin_usd`
- `sizing.leverage`
- `offsets.entry_offset_bps`
- `offsets.tp_offset_bps`
- `risk.max_notional_per_symbol_usd`
- `risk.max_notional_account_usd`
- `risk.daily_loss_limit_usd`
- `symbols.active`
- `symbols.overrides`
- `signal.engine`
- `signal.params`

Safe edit behavior:

- Preview YAML before saving.
- Save only after typed confirmation `SAVE`.
- Do not edit `.env` in v1.
- Do not edit API secrets from dashboard.

### Alerts & Logs

Show:

- `reports/live_alerts.md`
- `reports/live_ai_context.md`
- Monitor summary at top.

Raw log access:

- Do not show full raw log by default.
- Provide filtered table:
  - event name
  - symbol
  - severity/level
  - timestamp
  - compact fields
- Limit output to latest 120 rows by default.
- Max 500 rows.

### Backtests

Show:

- Existing reports under `reports/`.
- Existing backtest logs under `logs/backtest*`.
- Open selected report in the page.

Start backtest form:

- start date
- end date
- symbols
- initial equity
- signal

Command must be built from safe arguments only. Do not accept arbitrary shell command text.

Output:

```text
logs/dashboard_backtest_<timestamp>.txt
```

## API / Routes

Read pages:

```text
GET /
GET /trading
GET /settings
GET /alerts
GET /logs
GET /backtests
```

Read APIs:

```text
GET /api/status
GET /api/log-events?event=&symbol=&limit=120
```

Actions:

```text
POST /actions/kill
POST /actions/clear-kill
POST /actions/regenerate-monitor
POST /actions/regenerate-ai
POST /settings/preview
POST /settings/save
POST /backtests/run
```

Health:

```text
GET /healthz
```

## Safe Controls

Kill switch:

- Create `data/state/KILL`.
- Clear `data/state/KILL`.
- Require typed confirmation.

Regenerate monitor:

- Call existing `run_monitor(...)`.
- Write:
  - `reports/live_monitor.md`
  - `reports/live_alerts.md`
  - `logs/live_monitor.jsonl`
- Default dashboard regeneration must not pass `write_kill=True`.

Regenerate AI context:

- Read latest raw log.
- Include `reports/live_monitor.md`.
- Write:
  - `reports/live_ai_context.md`
  - `logs/ai_context.jsonl`

Backtest:

- Run in background with `subprocess.Popen`.
- Use allowlisted arguments only.
- Write output to a timestamped log file.

## UI

Design direction:

- Operational dashboard, not landing page.
- Dense but readable.
- No marketing hero.
- Avoid nested cards.
- Use tables for orders/positions/logs.
- Use small status cards for top-level metrics.

Dark/light mode:

- Toggle button in topbar.
- Store preference in `localStorage`.
- Default to system preference if no saved mode.

Responsive:

- Desktop: metrics grid + tables.
- Mobile: tables scroll horizontally.
- Text must not overlap or overflow buttons.

## Test Plan

Unit tests:

- Auth required on dashboard pages.
- Missing `DASHBOARD_PASSWORD` returns service unavailable.
- `/healthz` works without auth.
- Safe settings payload redacts secrets.
- Kill switch create/clear writes/removes `data/state/KILL`.
- Log event API filters by event and symbol.
- Backtest command builder rejects unsupported signal and unsafe symbols.
- Report path reader rejects paths outside repo.

Manual test:

```bash
export DASHBOARD_PASSWORD=dev
uv run python scripts/run_dashboard.py --host 127.0.0.1 --port 8080
```

Open:

```text
http://127.0.0.1:8080
```

Login:

```text
admin / dev
```

Verify:

- Overview loads.
- Current testnet monitor appears.
- Dark/light toggle works.
- Regenerate monitor works.
- Regenerate AI context works.
- Kill switch create/clear works.
- Settings preview returns YAML.
- Backtest starts and writes output log.

## Acceptance Criteria

Dashboard is ready for v1 when:

- All unit tests pass.
- Dashboard starts locally.
- Auth works.
- No secrets are displayed.
- Current monitor data is visible.
- Current open orders and bot states are visible.
- Kill switch controls work with confirmation.
- AI context and alerts are visible.
- Backtest can be started from safe form inputs.
- UI is readable in dark and light modes.

## Out of Scope for V1

- Auto market-close positions.
- Editing `.env` or API secrets.
- Public internet deployment without reverse proxy/TLS.
- React/Vite frontend.
- Database storage.
- Multi-user roles.
- Telegram/Discord alert configuration UI.
