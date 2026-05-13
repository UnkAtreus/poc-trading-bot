from __future__ import annotations

import json
import subprocess
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from bot.config import Mode, Settings
from bot.models import Side
from bot.monitoring.ai_context import (
    CRITICAL_EVENTS,
    AiContext,
    build_context,
    iter_ai_events,
    latest_log,
)


Severity = Literal["OK", "WARN", "CRITICAL", "KILL_TRIGGERED"]

EXIT_FAILURE_EVENTS = {"tp_place_rejected", "merge_tp_place_rejected"}
API_FAILURE_EVENTS = {"place_order_failed"} | EXIT_FAILURE_EVENTS
WARN_FAILURE_EVENTS = {"cancel_failed", "cancel_all_failed", "entry_rejected"}


@dataclass(frozen=True)
class MonitorIssue:
    severity: Literal["WARN", "CRITICAL"]
    code: str
    message: str
    symbol: str | None = None


@dataclass(frozen=True)
class MonitorPosition:
    symbol: str
    side: Literal["Buy", "Sell", ""]
    size: float
    avg_price: float
    mark_price: float
    unrealised_pnl: float = 0.0

    @property
    def signed_size(self) -> float:
        if self.side == "Sell":
            return -abs(self.size)
        if self.side == "Buy":
            return abs(self.size)
        return 0.0

    @property
    def notional(self) -> float:
        price = self.mark_price or self.avg_price
        return abs(self.size) * price


@dataclass(frozen=True)
class MonitorOrder:
    symbol: str
    side: Literal["Buy", "Sell"]
    qty: float
    price: float
    link_id: str
    reduce_only: bool
    purpose: str


@dataclass(frozen=True)
class WalletSnapshot:
    total_equity: float
    total_wallet_balance: float
    total_available_balance: float
    usdt_equity: float
    usdt_unrealised_pnl: float
    usdt_cum_realised_pnl: float


@dataclass(frozen=True)
class MonitorSnapshot:
    generated_at_utc: str
    source_log: str | None
    mode: str
    severity: Severity
    kill_triggered: bool
    bot_alive: bool
    latest_heartbeat_ts: str | None
    heartbeat_age_seconds: float | None
    current_states: dict[str, str]
    local_states: dict[str, dict]
    positions: list[MonitorPosition]
    open_orders: list[MonitorOrder]
    wallet: WalletSnapshot | None
    daily_closed_pnl: float | None
    issues: list[MonitorIssue]


class BybitMonitorClient:
    def __init__(self, settings: Settings):
        from pybit.unified_trading import HTTP

        self.settings = settings
        self.http = HTTP(
            testnet=settings.env.mode is Mode.TESTNET,
            api_key=settings.env.bybit_api_key,
            api_secret=settings.env.bybit_api_secret,
        )

    def get_positions(self, symbols: list[str]) -> list[MonitorPosition]:
        positions: list[MonitorPosition] = []
        for symbol in symbols:
            r = self.http.get_positions(category="linear", symbol=symbol)
            for p in r.get("result", {}).get("list", []):
                size = float(p.get("size") or 0.0)
                if size == 0.0:
                    continue
                positions.append(
                    MonitorPosition(
                        symbol=symbol,
                        side=p.get("side") or "",
                        size=size,
                        avg_price=float(p.get("avgPrice") or 0.0),
                        mark_price=float(p.get("markPrice") or 0.0),
                        unrealised_pnl=float(p.get("unrealisedPnl") or 0.0),
                    )
                )
        return positions

    def get_open_orders(self, symbols: list[str]) -> list[MonitorOrder]:
        orders: list[MonitorOrder] = []
        for symbol in symbols:
            r = self.http.get_open_orders(category="linear", symbol=symbol)
            for o in r.get("result", {}).get("list", []):
                link_id = o.get("orderLinkId", "")
                parts = link_id.split("-")
                purpose = parts[2] if len(parts) >= 3 else "unknown"
                orders.append(
                    MonitorOrder(
                        symbol=symbol,
                        side=o.get("side", ""),
                        qty=float(o.get("qty") or 0.0),
                        price=float(o.get("price") or 0.0),
                        link_id=link_id,
                        reduce_only=_parse_bool(o.get("reduceOnly")),
                        purpose=purpose,
                    )
                )
        return orders

    def get_wallet(self) -> WalletSnapshot | None:
        r = self.http.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        rows = r.get("result", {}).get("list", [])
        if not rows:
            return None
        account = rows[0]
        coin = next((c for c in account.get("coin", []) if c.get("coin") == "USDT"), {})
        return WalletSnapshot(
            total_equity=float(account.get("totalEquity") or 0.0),
            total_wallet_balance=float(account.get("totalWalletBalance") or 0.0),
            total_available_balance=float(account.get("totalAvailableBalance") or 0.0),
            usdt_equity=float(coin.get("equity") or 0.0),
            usdt_unrealised_pnl=float(coin.get("unrealisedPnl") or 0.0),
            usdt_cum_realised_pnl=float(coin.get("cumRealisedPnl") or 0.0),
        )

    def get_daily_closed_pnl(self, symbols: list[str], now_ts: float | None = None) -> float:
        now = datetime.fromtimestamp(now_ts or time.time(), tz=timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_ms = int(day_start.timestamp() * 1000)
        end_ms = int(now.timestamp() * 1000)
        total = 0.0
        for symbol in symbols:
            r = self.http.get_closed_pnl(
                category="linear",
                symbol=symbol,
                startTime=start_ms,
                endTime=end_ms,
                limit=100,
            )
            total += sum(float(row.get("closedPnl") or 0.0) for row in r.get("result", {}).get("list", []))
        return total


def run_monitor(
    settings: Settings,
    *,
    log_dir: Path = Path("logs"),
    log_file: Path | None = None,
    state_dir: Path = Path("data/state"),
    process_pattern: str | None = None,
    tmux_session: str | None = None,
    heartbeat_stale_seconds: float = 180.0,
    repeated_failure_threshold: int = 3,
    failure_window_seconds: float = 900.0,
    write_kill: bool = False,
    client: BybitMonitorClient | None = None,
) -> MonitorSnapshot:
    source_log = log_file or latest_log(log_dir, "*.log")
    context = build_context(source_log)
    client = client or BybitMonitorClient(settings)
    positions = client.get_positions(settings.symbols.active)
    orders = client.get_open_orders(settings.symbols.active)
    wallet = client.get_wallet()
    daily_closed_pnl = client.get_daily_closed_pnl(settings.symbols.active)
    bot_alive = check_bot_alive(process_pattern=process_pattern, tmux_session=tmux_session)
    local_states = load_local_states(state_dir)

    snapshot = evaluate_snapshot(
        settings=settings,
        context=context,
        local_states=local_states,
        positions=positions,
        open_orders=orders,
        wallet=wallet,
        daily_closed_pnl=daily_closed_pnl,
        bot_alive=bot_alive,
        heartbeat_stale_seconds=heartbeat_stale_seconds,
        now_ts=time.time(),
        repeated_failure_threshold=repeated_failure_threshold,
        failure_window_seconds=failure_window_seconds,
    )
    if write_kill and any(i.severity == "CRITICAL" for i in snapshot.issues):
        state_dir.mkdir(parents=True, exist_ok=True)
        kill_path = state_dir / "KILL"
        kill_path.write_text(
            f"Created by monitor at {snapshot.generated_at_utc}\n",
            encoding="utf-8",
        )
        snapshot = replace(snapshot, severity="KILL_TRIGGERED", kill_triggered=True)
    return snapshot


def evaluate_snapshot(
    *,
    settings: Settings,
    context: AiContext,
    local_states: dict[str, dict],
    positions: list[MonitorPosition],
    open_orders: list[MonitorOrder],
    wallet: WalletSnapshot | None,
    daily_closed_pnl: float | None,
    bot_alive: bool,
    heartbeat_stale_seconds: float,
    now_ts: float,
    repeated_failure_threshold: int,
    failure_window_seconds: float = 900.0,
) -> MonitorSnapshot:
    issues: list[MonitorIssue] = []
    latest_heartbeat_ts = _latest_heartbeat_ts(Path(context.source_log))
    heartbeat_age = None
    if latest_heartbeat_ts is None:
        issues.append(MonitorIssue("WARN", "heartbeat_missing", "No heartbeat found in log"))
    else:
        heartbeat_age = max(0.0, now_ts - _parse_ts(latest_heartbeat_ts))
        if heartbeat_age > heartbeat_stale_seconds:
            severity = "CRITICAL" if positions else "WARN"
            issues.append(
                MonitorIssue(
                    severity,
                    "heartbeat_stale",
                    f"Latest heartbeat is stale: {heartbeat_age:.0f}s old",
                )
            )

    if not bot_alive:
        severity = "CRITICAL" if positions else "WARN"
        issues.append(MonitorIssue(severity, "bot_not_alive", "Bot process/session is not alive"))

    total_notional = 0.0
    for pos in positions:
        total_notional += pos.notional
        cap = settings.per_symbol_max_notional(pos.symbol)
        if pos.notional > cap:
            issues.append(
                MonitorIssue(
                    "CRITICAL",
                    "symbol_cap_exceeded",
                    f"Position notional {pos.notional:.2f} exceeds cap {cap:.2f}",
                    pos.symbol,
                )
            )
        local = local_states.get(pos.symbol)
        if _local_mismatch(local, pos):
            issues.append(
                MonitorIssue(
                    "WARN",
                    "local_exchange_mismatch",
                    "Exchange position does not match local state",
                    pos.symbol,
                )
            )
        if not _has_reduce_only_exit(pos, open_orders):
            issues.append(
                MonitorIssue(
                    "CRITICAL",
                    "missing_reduce_only_exit",
                    "Open exchange position has no reduce-only TP/exit order",
                    pos.symbol,
                )
            )

    account_cap = settings.bot.risk.max_notional_account_usd
    if total_notional > account_cap:
        issues.append(
            MonitorIssue(
                "CRITICAL",
                "account_cap_exceeded",
                f"Total open notional {total_notional:.2f} exceeds account cap {account_cap:.2f}",
            )
        )

    if daily_closed_pnl is not None and daily_closed_pnl <= -settings.bot.risk.daily_loss_limit_usd:
        issues.append(
            MonitorIssue(
                "CRITICAL",
                "daily_loss_limit",
                f"Daily closed PnL {daily_closed_pnl:.2f} breached loss limit",
            )
        )

    issues.extend(_log_failure_issues(context, repeated_failure_threshold, now_ts, failure_window_seconds))

    severity: Severity = "OK"
    if any(i.severity == "CRITICAL" for i in issues):
        severity = "CRITICAL"
    elif issues:
        severity = "WARN"

    return MonitorSnapshot(
        generated_at_utc=datetime.fromtimestamp(now_ts, tz=timezone.utc).isoformat(),
        source_log=context.source_log,
        mode=settings.env.mode.value,
        severity=severity,
        kill_triggered=False,
        bot_alive=bot_alive,
        latest_heartbeat_ts=latest_heartbeat_ts,
        heartbeat_age_seconds=heartbeat_age,
        current_states=context.current_states,
        local_states=local_states,
        positions=positions,
        open_orders=open_orders,
        wallet=wallet,
        daily_closed_pnl=daily_closed_pnl,
        issues=issues,
    )


def check_bot_alive(*, process_pattern: str | None, tmux_session: str | None) -> bool:
    if tmux_session:
        r = subprocess.run(
            ["tmux", "has-session", "-t", tmux_session],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return r.returncode == 0
    if process_pattern:
        r = subprocess.run(
            ["pgrep", "-f", process_pattern],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return r.returncode == 0
    return True


def load_local_states(state_dir: Path) -> dict[str, dict]:
    states: dict[str, dict] = {}
    if not state_dir.exists():
        return states
    for path in state_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        symbol = data.get("symbol") or path.stem
        states[str(symbol)] = data
    return states


def write_monitor_markdown(snapshot: MonitorSnapshot, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Live Monitor",
        "",
        f"- Generated UTC: `{snapshot.generated_at_utc}`",
        f"- Mode: `{snapshot.mode}`",
        f"- Severity: `{snapshot.severity}`",
        f"- Kill triggered: `{snapshot.kill_triggered}`",
        f"- Source log: `{snapshot.source_log or 'n/a'}`",
        f"- Bot alive: `{snapshot.bot_alive}`",
        f"- Latest heartbeat: `{snapshot.latest_heartbeat_ts or 'n/a'}`",
        f"- Heartbeat age seconds: `{_fmt_float(snapshot.heartbeat_age_seconds)}`",
        "",
        "## Issues",
        "",
    ]
    if snapshot.issues:
        for issue in snapshot.issues:
            sym = f" `{issue.symbol}`" if issue.symbol else ""
            lines.append(f"- `{issue.severity}` `{issue.code}`{sym}: {issue.message}")
    else:
        lines.append("- None.")

    lines.extend(["", "## Wallet", ""])
    if snapshot.wallet:
        lines.extend(
            [
                f"- Total equity: `{snapshot.wallet.total_equity:.8f}`",
                f"- Total available balance: `{snapshot.wallet.total_available_balance:.8f}`",
                f"- USDT equity: `{snapshot.wallet.usdt_equity:.8f}`",
                f"- USDT unrealised PnL: `{snapshot.wallet.usdt_unrealised_pnl:.8f}`",
                f"- Daily closed PnL: `{_fmt_float(snapshot.daily_closed_pnl)}`",
            ]
        )
    else:
        lines.append("- Wallet unavailable.")

    lines.extend(["", "## Positions", ""])
    if snapshot.positions:
        for pos in snapshot.positions:
            lines.append(
                f"- `{pos.symbol}` `{pos.side}` size=`{pos.size}` avg=`{pos.avg_price}` "
                f"mark=`{pos.mark_price}` notional=`{pos.notional:.2f}` upnl=`{pos.unrealised_pnl}`"
            )
    else:
        lines.append("- None.")

    lines.extend(["", "## Open Orders", ""])
    if snapshot.open_orders:
        for order in snapshot.open_orders[:80]:
            lines.append(
                f"- `{order.symbol}` `{order.side}` purpose=`{order.purpose}` qty=`{order.qty}` "
                f"price=`{order.price}` reduceOnly=`{order.reduce_only}` link=`{order.link_id}`"
            )
    else:
        lines.append("- None.")

    lines.extend(["", "## Current Bot States", ""])
    if snapshot.current_states:
        for symbol, state in sorted(snapshot.current_states.items()):
            lines.append(f"- `{symbol}`: `{state}`")
    else:
        lines.append("- No heartbeat state found.")

    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_alerts_markdown(snapshot: MonitorSnapshot, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Live Alerts",
        "",
        f"- Generated UTC: `{snapshot.generated_at_utc}`",
        f"- Severity: `{snapshot.severity}`",
        "",
    ]
    actionable = [i for i in snapshot.issues if i.severity == "CRITICAL"] or snapshot.issues
    if actionable:
        for issue in actionable:
            sym = f" `{issue.symbol}`" if issue.symbol else ""
            lines.append(f"- `{issue.severity}` `{issue.code}`{sym}: {issue.message}")
    else:
        lines.append("- No alerts.")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_monitor_jsonl(snapshot: MonitorSnapshot, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        f.write(json.dumps(_jsonable(asdict(snapshot)), sort_keys=True) + "\n")


def append_monitor_history(snapshot: MonitorSnapshot, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    wallet = asdict(snapshot.wallet) if snapshot.wallet else {}
    record = {
        "ts": snapshot.generated_at_utc,
        "severity": snapshot.severity,
        "mode": snapshot.mode,
        "total_equity": wallet.get("total_equity"),
        "total_available_balance": wallet.get("total_available_balance"),
        "usdt_equity": wallet.get("usdt_equity"),
        "usdt_unrealised_pnl": wallet.get("usdt_unrealised_pnl"),
        "usdt_cum_realised_pnl": wallet.get("usdt_cum_realised_pnl"),
        "daily_closed_pnl": snapshot.daily_closed_pnl,
        "open_positions": len(snapshot.positions),
        "open_orders": len(snapshot.open_orders),
    }
    with output.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def _log_failure_issues(
    context: AiContext,
    repeated_failure_threshold: int,
    now_ts: float,
    failure_window_seconds: float,
) -> list[MonitorIssue]:
    issues: list[MonitorIssue] = []
    counts: dict[str, int] = {}
    cutoff = now_ts - failure_window_seconds
    for event in iter_ai_events(Path(context.source_log)):
        try:
            event_ts = _parse_ts(event.ts)
        except ValueError:
            continue
        if event_ts < cutoff:
            continue
        if event.event in API_FAILURE_EVENTS | WARN_FAILURE_EVENTS:
            counts[event.event] = counts.get(event.event, 0) + 1
        if event.event in CRITICAL_EVENTS and _is_fatal_reason(event.fields.get("reason") or event.fields.get("error")):
            issues.append(
                MonitorIssue(
                    "CRITICAL",
                    "fatal_api_error",
                    f"Fatal API/order error detected in {event.event}",
                    event.symbol,
                )
            )

    for event_name in sorted(API_FAILURE_EVENTS | WARN_FAILURE_EVENTS):
        count = counts.get(event_name, 0)
        if count < repeated_failure_threshold:
            continue
        severity: Literal["WARN", "CRITICAL"] = "CRITICAL" if event_name in API_FAILURE_EVENTS else "WARN"
        issues.append(
            MonitorIssue(
                severity,
                "repeated_log_failure",
                f"{event_name} occurred {count} times in the recent monitor window",
            )
        )
    return issues


def _latest_heartbeat_ts(source_log: Path) -> str | None:
    latest = None
    for event in iter_ai_events(source_log):
        if event.event == "heartbeat":
            latest = event.ts
    return latest


def _has_reduce_only_exit(pos: MonitorPosition, orders: list[MonitorOrder]) -> bool:
    exit_side = Side.SELL.value if pos.signed_size > 0 else Side.BUY.value
    exit_qty = sum(
        o.qty
        for o in orders
        if o.symbol == pos.symbol
        and o.reduce_only
        and o.side == exit_side
        and o.purpose in {"tp", "merge"}
    )
    return exit_qty >= abs(pos.size) * 0.99


def _local_mismatch(local: dict | None, pos: MonitorPosition) -> bool:
    if not local:
        return True
    local_state = local.get("state")
    local_size = abs(float(local.get("position_size") or 0.0))
    local_direction = local.get("direction")
    expected_direction = "LONG" if pos.signed_size > 0 else "SHORT"
    if local_state == "IDLE":
        return True
    if local_direction and local_direction != expected_direction:
        return True
    return abs(local_size - abs(pos.size)) > max(1e-6, abs(pos.size) * 0.01)


def _parse_ts(ts: str) -> float:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()


def _parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return bool(value)


def _is_fatal_reason(reason: str | None) -> bool:
    if not reason:
        return False
    low = reason.lower()
    return "errcode: 10024" in low or "regulatory restrictions" in low


def _fmt_float(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _jsonable(value):
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value
