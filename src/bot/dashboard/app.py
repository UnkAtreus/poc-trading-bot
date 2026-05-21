from __future__ import annotations

import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from bot.dashboard.service import DashboardService


security = HTTPBasic()
PACKAGE_DIR = Path(__file__).parent
BANGKOK_TZ = ZoneInfo("Asia/Bangkok")


def create_app(root: Path | str = ".") -> FastAPI:
    root_path = Path(root).resolve()
    service = DashboardService(root_path)
    app = FastAPI(title="Trading Bot Dashboard")
    app.state.dashboard_service = service
    static_dir = PACKAGE_DIR / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")
    templates.env.filters["bangkok_dt"] = _bangkok_dt
    templates.env.filters["bangkok_date"] = _bangkok_date
    templates.env.filters["bangkok_time"] = _bangkok_time

    def static_url(path: str) -> str:
        rel = path.lstrip("/")
        target = static_dir / rel
        try:
            version = int(target.stat().st_mtime)
        except OSError:
            version = 0
        return f"/static/{rel}?v={version}"

    templates.env.globals["static_url"] = static_url

    def require_auth(credentials: Annotated[HTTPBasicCredentials, Depends(security)]) -> str:
        password = service.password()
        if not password:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="DASHBOARD_PASSWORD is not configured",
            )
        user_ok = secrets.compare_digest(credentials.username, "admin")
        pass_ok = secrets.compare_digest(credentials.password, password)
        if not (user_ok and pass_ok):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid dashboard credentials",
                headers={"WWW-Authenticate": "Basic"},
            )
        return credentials.username

    def render(request: Request, template: str, context: dict) -> HTMLResponse:
        base = {
            "status": service.status(),
            "page": template.rsplit(".", 1)[0],
        }
        base.update(context)
        return templates.TemplateResponse(request, template, base)

    @app.get("/", response_class=HTMLResponse)
    def overview(request: Request, _: str = Depends(require_auth)):
        return render(request, "overview.html", {"summary": service.overview_summary()})

    @app.get("/trading", response_class=HTMLResponse)
    def trading(request: Request, _: str = Depends(require_auth)):
        overview = service.trading_overview()
        return render(
            request,
            "trading.html",
            {"states": service.profile_local_states(), "overview": overview},
        )

    @app.get("/api/trading-overview")
    def api_trading_overview(_: str = Depends(require_auth)):
        return service.trading_overview()

    @app.get("/settings", response_class=HTMLResponse)
    def settings(request: Request, _: str = Depends(require_auth)):
        return render(
            request,
            "settings.html",
            {
                "alerting": service.load_alerting().model_dump(),
                "secrets_masked": service.alert_secrets_masked(),
            },
        )

    @app.get("/alerts", response_class=HTMLResponse)
    def alerts(request: Request, _: str = Depends(require_auth)):
        return render(request, "alerts.html", {"analysis": service.log_analysis()})

    @app.get("/api/log-analysis")
    def api_log_analysis(bucket_minutes: int = 15, _: str = Depends(require_auth)):
        return service.log_analysis(bucket_minutes=max(1, min(bucket_minutes, 240)))

    @app.get("/logs", response_class=HTMLResponse)
    def logs(
        request: Request,
        event: str = "",
        symbol: str = "",
        _: str = Depends(require_auth),
    ):
        return render(
            request,
            "logs.html",
            {"events": service.log_events(event=event, symbol=symbol), "event": event, "symbol": symbol},
        )

    @app.get("/backtests", response_class=HTMLResponse)
    def backtests(request: Request, report: str = "", _: str = Depends(require_auth)):
        report_text = ""
        report_error = ""
        if report:
            try:
                report_text = service.report_text(report)
            except ValueError as e:
                report_error = str(e)
        active_symbols = service.safe_settings().get("symbols", {}).get("active") or []
        return render(
            request,
            "backtests.html",
            {
                "reports": service.backtest_reports(),
                "report": report,
                "report_text": report_text,
                "report_error": report_error,
                "signals": service.available_signals(),
                "active_symbols": active_symbols,
                "jobs": service.list_backtest_jobs(),
            },
        )

    @app.get("/analysis", response_class=HTMLResponse)
    def analysis(request: Request, _: str = Depends(require_auth)):
        data = service.backtest_analysis()
        return render(
            request,
            "analysis.html",
            {
                "analysis": data,
                "signals": service.available_signals(),
            },
        )

    @app.get("/api/backtest-analysis")
    def api_backtest_analysis(
        strategies: str = "",
        symbols: str = "",
        start: str = "",
        end: str = "",
        min_trades: int = 0,
        min_win_rate_pct: float = 0.0,
        hide_zero_trades: bool = True,
        _: str = Depends(require_auth),
    ):
        strategy_list = [s.strip() for s in strategies.split(",") if s.strip()]
        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
        return service.backtest_analysis(
            strategies=strategy_list or None,
            symbols=symbol_list or None,
            start=start or None,
            end=end or None,
            min_trades=max(0, min_trades),
            min_win_rate_pct=max(0.0, min_win_rate_pct),
            hide_zero_trades=hide_zero_trades,
        )

    @app.get("/balance", response_class=HTMLResponse)
    def balance(request: Request, _: str = Depends(require_auth)):
        return render(
            request,
            "balance.html",
            {
                "summary": service.balance_summary(),
                "breakdown": service.positions_breakdown(),
            },
        )

    @app.get("/api/balance-summary")
    def api_balance_summary(_: str = Depends(require_auth)):
        return service.balance_summary()

    @app.get("/alerting", response_class=HTMLResponse)
    def alerting(request: Request, _: str = Depends(require_auth)):
        return render(
            request,
            "alerting.html",
            {
                "alerting": service.load_alerting().model_dump(),
                "secrets_masked": service.alert_secrets_masked(),
            },
        )

    @app.post("/alerting/save")
    def alerting_save(
        enabled: Annotated[str, Form()] = "",
        heartbeat_stale_seconds: Annotated[str, Form()] = "180",
        repeated_failure_threshold: Annotated[str, Form()] = "3",
        failure_window_seconds: Annotated[str, Form()] = "900",
        daily_loss_alert_usd: Annotated[str, Form()] = "5000",
        telegram_enabled: Annotated[str, Form()] = "",
        discord_enabled: Annotated[str, Form()] = "",
        confirm: Annotated[str, Form()] = "",
        _: str = Depends(require_auth),
    ):
        if confirm != "SAVE":
            raise HTTPException(status_code=400, detail="type SAVE to confirm")
        try:
            service.save_alerting_values(locals())
        except (ValueError, TypeError) as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return RedirectResponse("/settings#alerting", status_code=303)

    @app.post("/alerting/secrets/save")
    def alerting_secrets_save(
        telegram_bot_token: Annotated[str, Form()] = "",
        telegram_chat_id: Annotated[str, Form()] = "",
        discord_webhook_url: Annotated[str, Form()] = "",
        confirm: Annotated[str, Form()] = "",
        _: str = Depends(require_auth),
    ):
        if confirm != "SAVE":
            raise HTTPException(status_code=400, detail="type SAVE to confirm")
        service.save_alert_secrets_values(locals())
        return RedirectResponse("/settings#alerting", status_code=303)

    @app.post("/alerting/test")
    def alerting_test(
        channel: Annotated[str, Form()],
        telegram_bot_token: Annotated[str, Form()] = "",
        telegram_chat_id: Annotated[str, Form()] = "",
        discord_webhook_url: Annotated[str, Form()] = "",
        _: str = Depends(require_auth),
    ):
        overrides = {
            "telegram_bot_token": telegram_bot_token,
            "telegram_chat_id": telegram_chat_id,
            "discord_webhook_url": discord_webhook_url,
        }
        result = service.test_alert_delivery(channel, overrides=overrides)
        return JSONResponse(result, status_code=200 if result.get("ok") else 400)

    @app.get("/api/status")
    def api_status(_: str = Depends(require_auth)):
        return service.status()

    @app.get("/api/equity-history")
    def api_equity_history(limit: int = 500, _: str = Depends(require_auth)):
        return {"history": service.equity_history(limit=max(1, min(limit, 5000)))}

    @app.get("/api/positions-breakdown")
    def api_positions_breakdown(_: str = Depends(require_auth)):
        return {"breakdown": service.positions_breakdown()}

    @app.get("/api/backtest-series")
    def api_backtest_series(path: str, _: str = Depends(require_auth)):
        try:
            return service.backtest_csv(path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.get("/api/report")
    def api_report(path: str, _: str = Depends(require_auth)):
        try:
            return {"path": path, "text": service.report_text(path)}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.get("/api/log-events")
    def api_log_events(event: str = "", symbol: str = "", limit: int = 120, _: str = Depends(require_auth)):
        return {"events": service.log_events(event=event, symbol=symbol, limit=limit)}

    @app.post("/actions/kill")
    def action_kill(confirm: Annotated[str, Form()], _: str = Depends(require_auth)):
        if confirm != "KILL":
            raise HTTPException(status_code=400, detail="type KILL to confirm")
        service.create_kill()
        return RedirectResponse("/", status_code=303)

    @app.post("/actions/clear-kill")
    def action_clear_kill(confirm: Annotated[str, Form()], _: str = Depends(require_auth)):
        if confirm != "CLEAR":
            raise HTTPException(status_code=400, detail="type CLEAR to confirm")
        service.clear_kill()
        return RedirectResponse("/", status_code=303)

    @app.post("/actions/regenerate-monitor")
    def action_regenerate_monitor(
        tmux_session: Annotated[str, Form()] = "",
        skip_process_check: Annotated[bool, Form()] = True,
        _: str = Depends(require_auth),
    ):
        service.regenerate_monitor(tmux_session=tmux_session, skip_process_check=skip_process_check)
        return RedirectResponse("/", status_code=303)

    @app.post("/actions/regenerate-ai")
    def action_regenerate_ai(_: str = Depends(require_auth)):
        service.regenerate_ai_context()
        return RedirectResponse("/alerts", status_code=303)

    @app.post("/actions/restart-bot")
    def action_restart_bot(
        confirm: Annotated[str, Form()],
        tmux_session: Annotated[str, Form()] = "testnet_dry_run",
        _: str = Depends(require_auth),
    ):
        try:
            service.restart_bot(tmux_session=tmux_session, confirm=confirm)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return RedirectResponse("/", status_code=303)

    @app.post("/settings/preview")
    def settings_preview(
        margin_usd: Annotated[str, Form()],
        leverage: Annotated[str, Form()],
        entry_offset_bps: Annotated[str, Form()],
        tp_offset_bps: Annotated[str, Form()],
        max_notional_per_symbol_usd: Annotated[str, Form()],
        max_notional_account_usd: Annotated[str, Form()],
        daily_loss_limit_usd: Annotated[str, Form()],
        active_symbols: Annotated[str, Form()],
        _: str = Depends(require_auth),
    ):
        try:
            preview = service.preview_config(locals())
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        return preview

    @app.post("/settings/save")
    def settings_save(
        margin_usd: Annotated[str, Form()],
        leverage: Annotated[str, Form()],
        entry_offset_bps: Annotated[str, Form()],
        tp_offset_bps: Annotated[str, Form()],
        max_notional_per_symbol_usd: Annotated[str, Form()],
        max_notional_account_usd: Annotated[str, Form()],
        daily_loss_limit_usd: Annotated[str, Form()],
        active_symbols: Annotated[str, Form()],
        confirm: Annotated[str, Form()],
        _: str = Depends(require_auth),
    ):
        if confirm != "SAVE":
            raise HTTPException(status_code=400, detail="type SAVE to confirm")
        service.save_config(locals())
        return RedirectResponse("/settings", status_code=303)

    @app.post("/backtests/run")
    async def backtest_run(request: Request, _: str = Depends(require_auth)):
        form = await request.form()
        form_values = {
            "start": form.get("start", ""),
            "end": form.get("end", ""),
            "symbols": form.get("symbols", ""),
            "symbols_extra": form.get("symbols_extra", ""),
            "initial_equity": form.get("initial_equity", "30000"),
            "signal_engine": form.get("signal_engine", ""),
            "signal_params": form.get("signal_params", ""),
            "signal": form.get("signal", ""),
            "symbols_picked": form.getlist("symbols_picked"),
            "margin_usd": form.get("margin_usd", ""),
            "leverage": form.get("leverage", ""),
            "max_notional_account": form.get("max_notional_account", ""),
            "max_notional_per_symbol": form.get("max_notional_per_symbol", ""),
            "tp_offset_bps": form.get("tp_offset_bps", ""),
            "daily_loss_limit": form.get("daily_loss_limit", ""),
        }
        try:
            result = service.start_backtest(form_values)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return JSONResponse(result)

    @app.get("/api/backtests")
    def api_backtests(_: str = Depends(require_auth)):
        return {"jobs": service.list_backtest_jobs()}

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"ok": "true"}

    @app.get("/favicon.ico")
    def favicon() -> Response:
        return Response(status_code=204)

    return app


def _parse_datetime(value) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000.0
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _bangkok_dt(value, fallback: str = "") -> str:
    dt = _parse_datetime(value)
    if dt is None:
        return fallback if value in (None, "") else str(value)
    local = dt.astimezone(BANGKOK_TZ)
    return f"{local.strftime('%b')} {local.day}, {local.year} {local.strftime('%H:%M:%S')} ICT"


def _bangkok_date(value, fallback: str = "") -> str:
    dt = _parse_datetime(value)
    if dt is None:
        return fallback if value in (None, "") else str(value)
    local = dt.astimezone(BANGKOK_TZ)
    return f"{local.strftime('%b')} {local.day}, {local.year}"


def _bangkok_time(value, fallback: str = "") -> str:
    dt = _parse_datetime(value)
    if dt is None:
        return fallback if value in (None, "") else str(value)
    return f"{dt.astimezone(BANGKOK_TZ).strftime('%H:%M:%S')} ICT"


app = create_app()
