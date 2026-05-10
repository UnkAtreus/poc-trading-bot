"""Backtest report rendering."""

from __future__ import annotations

from collections import defaultdict

from bot.backtest.runner import BacktestResult


def render(result: BacktestResult) -> str:
    """Plain-text report. Mirrors the kind of summary the existing `main` bot produces."""
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("BACKTEST REPORT")
    lines.append("=" * 60)
    lines.append(f"trades         : {len(result.trades)}")
    lines.append(f"wins           : {result.wins}")
    lines.append(f"losses         : {result.losses}")
    if result.stopped:
        lines.append(f"stop exits     : {result.stopped}")
    lines.append(f"win rate       : {result.win_rate:.2%}")
    lines.append(f"gross PnL      : {result.total_pnl:+.4f} USDT")
    lines.append(f"fees (signed)  : {result.total_fees:+.4f} USDT  (negative = rebate)")
    lines.append(f"net PnL        : {result.net_pnl:+.4f} USDT")
    lines.append(f"max drawdown   : {result.max_drawdown:.4f} USDT")
    if result.initial_equity > 0:
        lines.append(f"max DD %       : {result.max_drawdown_pct:.2%}")
    lines.append(f"liquidated     : {result.liquidated}")
    lines.append(f"near liq       : {result.near_liquidation}")
    lines.append(f"max margin r.  : {result.margin_ratio_max:.2%}")
    lines.append(f"min liq dist   : {result.min_liq_distance_pct:.2f}%")
    lines.append(f"worst unreal.  : {result.worst_unrealized_loss:.4f} USDT")
    lines.append(f"recovery time  : {result.time_in_recovery / 3600.0:.2f} h")
    lines.append(f"open exposure  : {result.final_open_exposure:.4f} USDT")
    lines.append("")

    # Per-symbol breakdown
    by_sym: dict[str, list] = defaultdict(list)
    for t in result.trades:
        by_sym[t.symbol].append(t)

    lines.append("Per-symbol PnL:")
    lines.append("-" * 60)
    rows = []
    for sym, ts in by_sym.items():
        gross = sum(t.realized_pnl for t in ts)
        # Use the fills-based total so per-symbol reconciles with the global
        # total even when a position is still open at end-of-backtest.
        fees = result.fees_for_symbol(sym)
        wins = sum(1 for t in ts if t.realized_pnl > 0)
        losses = sum(1 for t in ts if t.realized_pnl < 0)
        rows.append((sym, len(ts), wins, losses, gross, fees, gross - fees))
    rows.sort(key=lambda r: -r[6])
    lines.append(f"{'symbol':<12}{'n':>5}{'W':>5}{'L':>5}{'gross':>12}{'fees':>10}{'net':>12}")
    for sym, n, w, l, g, f, net in rows:
        lines.append(f"{sym:<12}{n:>5}{w:>5}{l:>5}{g:>12.4f}{f:>10.4f}{net:>12.4f}")
    lines.append("")

    # Long/short split
    long_pnl = sum(t.realized_pnl for t in result.trades if t.direction.value == "LONG")
    short_pnl = sum(t.realized_pnl for t in result.trades if t.direction.value == "SHORT")
    lines.append(f"long PnL       : {long_pnl:+.4f} USDT")
    lines.append(f"short PnL      : {short_pnl:+.4f} USDT")

    # Final state per symbol
    lines.append("")
    lines.append("Final state:")
    for sym, ctx in result.final_state.items():
        if ctx.state.value != "IDLE":
            lines.append(f"  {sym}: {ctx.state.value} size={ctx.position_size} bep={ctx.bep:.4f}")

    return "\n".join(lines)
