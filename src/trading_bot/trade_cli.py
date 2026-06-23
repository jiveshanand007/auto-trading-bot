from __future__ import annotations

import contextlib
import sys

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(help="Trading bot CLI — place and manage trades on Binance testnet.")
console = Console()
err_console = Console(stderr=True)


def _broker():
    from trading_bot.broker.binance_broker import BinanceBroker

    return BinanceBroker()


def _die(msg: str) -> None:
    err_console.print(f"[bold red]Error:[/bold red] {msg}")
    sys.exit(1)


def _fmt(val: float, decimals: int = 2, prefix: str = "") -> str:
    return f"{prefix}{val:,.{decimals}f}"


def _print_trade_preview(
    broker,
    symbol: str,
    side: str,
    quantity: float,
    sl: float,
    tp: float,
) -> None:
    """Print a full pre-trade summary: price, balance, order details, risk metrics."""
    side_upper = side.upper()
    color = "green" if side_upper == "BUY" else "red"

    price: float | None = None
    balances: dict = {}

    with contextlib.suppress(Exception):
        price = float(broker._client.get_symbol_ticker(symbol=symbol)["price"])

    with contextlib.suppress(Exception):
        balances = broker.get_balance()

    # ── Market + balance ──────────────────────────────────────────────────────
    info = Table.grid(padding=(0, 2))
    info.add_column(style="bold dim")
    info.add_column()

    if price is not None:
        info.add_row("Market price", f"[bold]{_fmt(price, 2, '$')}[/bold]")
        info.add_row("", "")

    base = symbol.replace("USDT", "").replace("BUSD", "")
    quote = "USDT" if "USDT" in symbol else "BUSD"
    for asset in (quote, base):
        b = balances.get(asset, {})
        free = b.get("free", "0")
        locked = b.get("locked", "0")
        info.add_row(
            f"Balance {asset}",
            f"{free} free  /  {locked} locked"
            if float(locked) > 0
            else f"[bold]{free}[/bold] free",
        )

    # ── Order details ─────────────────────────────────────────────────────────
    info.add_row("", "")
    info.add_row("Side", f"[bold {color}]{side_upper}[/bold {color}]")
    info.add_row("Symbol", symbol)
    info.add_row("Quantity", f"{quantity}")
    if price is not None:
        notional = price * quantity
        info.add_row("Notional value", f"~{_fmt(notional, 2, '$')}")

    # ── Risk metrics ──────────────────────────────────────────────────────────
    if price is not None:
        info.add_row("", "")
        sl_dist = abs(price - sl)
        tp_dist = abs(tp - price)
        sl_pct = sl_dist / price * 100
        tp_pct = tp_dist / price * 100
        sl_dollars = sl_dist * quantity
        tp_dollars = tp_dist * quantity
        rr = tp_dist / sl_dist if sl_dist else 0

        info.add_row(
            "Stop loss",
            f"[red]{_fmt(sl, 2, '$')}[/red]  "
            f"([red]-{sl_pct:.2f}%[/red]  risk [red]-{_fmt(sl_dollars, 2, '$')}[/red])",
        )
        info.add_row(
            "Take profit",
            f"[green]{_fmt(tp, 2, '$')}[/green]  "
            f"([green]+{tp_pct:.2f}%[/green]  reward [green]+{_fmt(tp_dollars, 2, '$')}[/green])",
        )
        rr_color = "green" if rr >= 1.5 else "yellow" if rr >= 1.0 else "red"
        info.add_row("Risk : Reward", f"[{rr_color}]1 : {rr:.2f}[/{rr_color}]")

    console.print(
        Panel(
            info,
            title=f"[bold {color}] {side_upper} {symbol} — PRE-TRADE SUMMARY [/bold {color}]",
            border_style=color,
            padding=(1, 2),
        )
    )


def _confirm(yes: bool) -> None:
    if yes:
        return
    answer = typer.prompt("Proceed with trade? [y/N]", default="N")
    if answer.strip().lower() not in ("y", "yes"):
        console.print("[dim]Trade cancelled.[/dim]")
        raise typer.Exit()


def _print_result(result) -> None:
    t = Table(show_header=True, header_style="bold cyan", title="Trade Confirmed")
    t.add_column("Field")
    t.add_column("Value")
    t.add_row("Symbol", result.symbol)
    t.add_row("Side", result.side)
    t.add_row("Quantity", str(result.quantity))
    t.add_row("Entry Price", _fmt(result.entry_price, 2, "$"))
    t.add_row("Stop Loss", _fmt(result.stop_loss, 2, "$"))
    t.add_row("Take Profit", _fmt(result.take_profit, 2, "$"))
    t.add_row("Entry Order ID", str(result.entry_order_id))
    t.add_row("OCO List ID", str(result.oco_order_list_id))
    console.print(t)
    console.print("[bold green]✓ Trade placed successfully[/bold green]")


@app.command()
def buy(
    symbol: str = typer.Argument(..., help="Trading pair, e.g. BTCUSDT"),
    quantity: float = typer.Argument(..., help="Quantity to buy"),
    sl: float = typer.Option(..., "--sl", help="Stop-loss price"),
    tp: float = typer.Option(..., "--tp", help="Take-profit price"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Place a market BUY with stop-loss / take-profit (OCO)."""
    b = _broker()
    _print_trade_preview(b, symbol, "BUY", quantity, sl, tp)
    _confirm(yes)
    try:
        result = b.place_trade(symbol, "BUY", quantity, sl, tp)
    except (ValueError, Exception) as exc:
        _die(str(exc))
    _print_result(result)


@app.command()
def sell(
    symbol: str = typer.Argument(..., help="Trading pair, e.g. BTCUSDT"),
    quantity: float = typer.Argument(..., help="Quantity to sell"),
    sl: float = typer.Option(..., "--sl", help="Stop-loss price"),
    tp: float = typer.Option(..., "--tp", help="Take-profit price"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Place a market SELL with stop-loss / take-profit (OCO)."""
    b = _broker()
    _print_trade_preview(b, symbol, "SELL", quantity, sl, tp)
    _confirm(yes)
    try:
        result = b.place_trade(symbol, "SELL", quantity, sl, tp)
    except (ValueError, Exception) as exc:
        _die(str(exc))
    _print_result(result)


@app.command()
def price(
    symbol: str = typer.Argument(..., help="Trading pair, e.g. BTCUSDT"),
) -> None:
    """Show current market price and your account balance."""
    b = _broker()

    try:
        current = float(b._client.get_symbol_ticker(symbol=symbol)["price"])
        console.print(
            Panel(
                f"[bold]{symbol}[/bold]  →  [bold yellow]{_fmt(current, 2, '$')}[/bold yellow]",
                title="Market Price",
                border_style="yellow",
            )
        )
    except Exception as exc:
        _die(str(exc))

    try:
        balances = b.get_balance()
        t = Table(show_header=True, header_style="bold cyan", title="Account Balance")
        t.add_column("Asset")
        t.add_column("Free", justify="right")
        t.add_column("Locked", justify="right")
        for asset, amounts in sorted(balances.items()):
            t.add_row(asset, amounts["free"], amounts["locked"])
        console.print(t)
    except Exception as exc:
        err_console.print(f"[yellow]Balance unavailable:[/yellow] {exc}")


@app.command()
def orders(
    symbol: str | None = typer.Argument(None, help="Filter by trading pair"),
) -> None:
    """List open orders, optionally filtered by symbol."""
    try:
        open_orders = _broker().get_open_orders(symbol=symbol)
    except Exception as exc:
        _die(str(exc))

    if not open_orders:
        console.print("[dim]No open orders.[/dim]")
        return

    t = Table(show_header=True, header_style="bold cyan", title="Open Orders")
    for col in ("Symbol", "Order ID", "Side", "Type", "Price", "Qty", "Status"):
        t.add_column(col)
    for o in open_orders:
        side = o.get("side", "")
        color = "green" if side == "BUY" else "red"
        t.add_row(
            o.get("symbol", ""),
            str(o.get("orderId", "")),
            f"[{color}]{side}[/{color}]",
            o.get("type", ""),
            o.get("price", ""),
            o.get("origQty", ""),
            o.get("status", ""),
        )
    console.print(t)


@app.command()
def balance() -> None:
    """Show non-zero asset balances."""
    try:
        balances = _broker().get_balance()
    except Exception as exc:
        _die(str(exc))

    if not balances:
        console.print("[dim]No non-zero balances.[/dim]")
        return

    t = Table(show_header=True, header_style="bold cyan", title="Account Balance")
    t.add_column("Asset")
    t.add_column("Free", justify="right")
    t.add_column("Locked", justify="right")
    for asset, amounts in sorted(balances.items()):
        t.add_row(asset, amounts["free"], amounts["locked"])
    console.print(t)


@app.command()
def cancel(
    symbol: str = typer.Argument(..., help="Trading pair, e.g. BTCUSDT"),
    order_id: int = typer.Argument(..., help="Order ID to cancel"),
) -> None:
    """Cancel an open order by symbol and order ID."""
    try:
        _broker().cancel_order(symbol, order_id)
    except Exception as exc:
        _die(str(exc))

    console.print(
        Panel(
            f"Order [bold]{order_id}[/bold] on [bold]{symbol}[/bold] cancelled.",
            style="green",
        )
    )


if __name__ == "__main__":
    app()
