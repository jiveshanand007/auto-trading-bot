# src/trading_bot/cli/_display.py
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from trading_bot.core.domain.order import Side
from trading_bot.core.domain.position import Position
from trading_bot.core.domain.trade import ActiveTrade, TradePlan

console = Console()
err_console = Console(stderr=True)


def _fmt(val: float, decimals: int = 2, prefix: str = "") -> str:
    return f"{prefix}{val:,.{decimals}f}"


def print_trade_preview(
    current_price: float | None,
    balances: dict,
    plan: TradePlan,
) -> None:
    color = "green" if plan.side == Side.BUY else "red"
    side_str = plan.side.value
    info = Table.grid(padding=(0, 2))
    info.add_column(style="bold dim")
    info.add_column()
    if current_price is not None:
        info.add_row("Market price", f"[bold]{_fmt(current_price, 2, '$')}[/bold]")
        info.add_row("", "")
    base = plan.symbol.replace("USDT", "").replace("BUSD", "")
    quote = "USDT" if "USDT" in plan.symbol else "BUSD"
    for asset in (quote, base):
        b = balances.get(asset, {})
        free = b.get("free", "0") if isinstance(b, dict) else str(b)
        locked = b.get("locked", "0") if isinstance(b, dict) else "0"
        locked_val = float(locked)
        balance_str = (
            f"{free} free  /  {locked} locked"
            if locked_val > 0
            else f"[bold]{free}[/bold] free"
        )
        info.add_row(f"Balance {asset}", balance_str)
    info.add_row("", "")
    info.add_row("Side", f"[bold {color}]{side_str}[/bold {color}]")
    info.add_row("Symbol", plan.symbol)
    info.add_row("Quantity", str(plan.quantity))
    if current_price is not None:
        notional = current_price * plan.quantity
        info.add_row("Notional value", f"~{_fmt(notional, 2, '$')}")
        info.add_row("", "")
        sl = plan.initial_stop_loss
        tp = plan.stages[0].take_profit
        sl_dist = abs(current_price - sl)
        tp_dist = abs(tp - current_price)
        sl_pct = sl_dist / current_price * 100
        tp_pct = tp_dist / current_price * 100
        sl_dollars = sl_dist * plan.quantity
        tp_dollars = tp_dist * plan.quantity
        rr = tp_dist / sl_dist if sl_dist else 0
        sl_str = (
            f"[red]{_fmt(sl, 2, '$')}[/red]"
            f"  ([red]-{sl_pct:.2f}%[/red]  risk [red]-{_fmt(sl_dollars, 2, '$')}[/red])"
        )
        tp_str = (
            f"[green]{_fmt(tp, 2, '$')}[/green]"
            f"  ([green]+{tp_pct:.2f}%[/green]  reward [green]+{_fmt(tp_dollars, 2, '$')}[/green])"
        )
        info.add_row("Stop loss", sl_str)
        info.add_row("Take profit", tp_str)
        rr_color = "green" if rr >= 1.5 else "yellow" if rr >= 1.0 else "red"
        info.add_row("Risk : Reward", f"[{rr_color}]1 : {rr:.2f}[/{rr_color}]")
    if plan.leverage > 1:
        info.add_row("Leverage", f"{plan.leverage}x")
        info.add_row("Margin type", plan.margin_type.value)
    console.print(
        Panel(
            info,
            title=f"[bold {color}] {side_str} {plan.symbol} — PRE-TRADE SUMMARY [/bold {color}]",
            border_style=color,
            padding=(1, 2),
        )
    )


def print_active_trade(trade: ActiveTrade) -> None:
    color = "green" if trade.plan.side == Side.BUY else "red"  # noqa: F841
    t = Table(show_header=True, header_style="bold cyan", title="Trade Confirmed")
    t.add_column("Field")
    t.add_column("Value")
    t.add_row("Symbol", trade.plan.symbol)
    t.add_row("Side", trade.plan.side.value)
    t.add_row("Quantity", str(trade.plan.quantity))
    t.add_row("Entry Price", _fmt(trade.entry_price, 2, "$"))
    t.add_row("Stop Loss", _fmt(trade.plan.initial_stop_loss, 2, "$"))
    t.add_row("Take Profit", _fmt(trade.current_stage_def.take_profit, 2, "$"))
    t.add_row("Stage", f"{trade.current_stage + 1} / {len(trade.plan.stages)}")
    t.add_row("Entry Order ID", str(trade.entry_order_id))
    t.add_row("SL Order ID", str(trade.current_sl_order_id))
    t.add_row("TP Order ID", str(trade.current_tp_order_id))
    console.print(t)
    console.print("[bold green]✓ Trade placed successfully[/bold green]")


def print_orders_table(orders: list[dict]) -> None:
    if not orders:
        console.print("[dim]No open orders.[/dim]")
        return
    t = Table(show_header=True, header_style="bold cyan", title="Open Orders")
    for col in ("Symbol", "Order ID", "Side", "Type", "Price", "Qty", "Status"):
        t.add_column(col)
    for o in orders:
        side = o.get("side", "")
        color = "green" if side == "BUY" else "red"
        t.add_row(
            o.get("symbol", ""), str(o.get("orderId", "")),
            f"[{color}]{side}[/{color}]", o.get("type", ""),
            o.get("price", ""), o.get("origQty", ""), o.get("status", ""),
        )
    console.print(t)


def print_balance_table(balances: dict) -> None:
    if not balances:
        console.print("[dim]No non-zero balances.[/dim]")
        return
    t = Table(show_header=True, header_style="bold cyan", title="Account Balance")
    t.add_column("Asset")
    t.add_column("Free", justify="right")
    t.add_column("Locked", justify="right")
    for asset, amounts in sorted(balances.items()):
        if isinstance(amounts, dict):
            t.add_row(asset, str(amounts.get("free", "")), str(amounts.get("locked", "")))
        else:
            t.add_row(asset, str(amounts), "—")
    console.print(t)


def print_positions_table(positions: list[Position]) -> None:
    if not positions:
        console.print("[dim]No open positions.[/dim]")
        return
    t = Table(show_header=True, header_style="bold cyan", title="Open Positions")
    for col in ("Symbol", "Side", "Qty", "Entry", "Liq Price", "PnL", "Leverage", "Margin"):
        t.add_column(col)
    for p in positions:
        color = "green" if p.side == Side.BUY else "red"
        pnl_color = "green" if p.unrealized_pnl >= 0 else "red"
        t.add_row(
            p.symbol,
            f"[{color}]{p.side.value}[/{color}]",
            str(p.quantity),
            _fmt(p.entry_price, 2, "$"),
            _fmt(p.liquidation_price, 2, "$"),
            f"[{pnl_color}]{_fmt(p.unrealized_pnl, 2, '$')}[/{pnl_color}]",
            f"{p.leverage}x",
            p.margin_type.value,
        )
    console.print(t)
