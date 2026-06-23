from __future__ import annotations

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


@app.command()
def buy(
    symbol: str = typer.Argument(..., help="Trading pair, e.g. BTCUSDT"),
    quantity: float = typer.Argument(..., help="Quantity to buy"),
    sl: float = typer.Option(..., "--sl", help="Stop-loss price"),
    tp: float = typer.Option(..., "--tp", help="Take-profit price"),
) -> None:
    """Place a market BUY order with an OCO stop-loss / take-profit."""
    try:
        result = _broker().place_trade(symbol, "BUY", quantity, sl, tp)
    except ValueError as exc:
        _die(str(exc))
    except Exception as exc:
        _die(str(exc))

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Symbol", result.symbol)
    table.add_row("Side", result.side)
    table.add_row("Quantity", str(result.quantity))
    table.add_row("Entry Price", str(result.entry_price))
    table.add_row("Stop Loss", str(result.stop_loss))
    table.add_row("Take Profit", str(result.take_profit))
    table.add_row("Entry Order ID", str(result.entry_order_id))
    table.add_row("OCO Order List ID", str(result.oco_order_list_id))
    console.print(table)
    console.print("[bold green]✓ Trade placed[/bold green]")


@app.command()
def sell(
    symbol: str = typer.Argument(..., help="Trading pair, e.g. BTCUSDT"),
    quantity: float = typer.Argument(..., help="Quantity to sell"),
    sl: float = typer.Option(..., "--sl", help="Stop-loss price"),
    tp: float = typer.Option(..., "--tp", help="Take-profit price"),
) -> None:
    """Place a market SELL order with an OCO stop-loss / take-profit."""
    try:
        result = _broker().place_trade(symbol, "SELL", quantity, sl, tp)
    except ValueError as exc:
        _die(str(exc))
    except Exception as exc:
        _die(str(exc))

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Symbol", result.symbol)
    table.add_row("Side", result.side)
    table.add_row("Quantity", str(result.quantity))
    table.add_row("Entry Price", str(result.entry_price))
    table.add_row("Stop Loss", str(result.stop_loss))
    table.add_row("Take Profit", str(result.take_profit))
    table.add_row("Entry Order ID", str(result.entry_order_id))
    table.add_row("OCO Order List ID", str(result.oco_order_list_id))
    console.print(table)
    console.print("[bold green]✓ Trade placed[/bold green]")


@app.command()
def orders(
    symbol: str | None = typer.Argument(None, help="Filter by trading pair"),
) -> None:
    """List open orders, optionally filtered by symbol."""
    try:
        open_orders = _broker().get_open_orders(symbol=symbol)
    except Exception as exc:
        _die(str(exc))

    table = Table(show_header=True, header_style="bold cyan")
    for col in ("Symbol", "Order ID", "Side", "Type", "Price", "Quantity", "Status"):
        table.add_column(col)

    for o in open_orders:
        table.add_row(
            o.get("symbol", ""),
            str(o.get("orderId", "")),
            o.get("side", ""),
            o.get("type", ""),
            o.get("price", ""),
            o.get("origQty", ""),
            o.get("status", ""),
        )

    console.print(table)


@app.command()
def balance() -> None:
    """Show non-zero asset balances."""
    try:
        balances = _broker().get_balance()
    except Exception as exc:
        _die(str(exc))

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Asset")
    table.add_column("Free")
    table.add_column("Locked")

    for asset, amounts in sorted(balances.items()):
        table.add_row(asset, amounts["free"], amounts["locked"])

    console.print(table)


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
