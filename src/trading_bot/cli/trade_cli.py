# src/trading_bot/cli/trade_cli.py
from __future__ import annotations

import contextlib
import sys

import typer
from rich.panel import Panel

from trading_bot.cli._broker_factory import make_spot_broker
from trading_bot.cli._display import (
    console,
    err_console,
    print_active_trade,
    print_balance_table,
    print_orders_table,
    print_trade_preview,
)
from trading_bot.core.domain.order import Side
from trading_bot.core.domain.trade import TradePlan, TradeStage

app = typer.Typer(help="Spot trading — place and manage trades on Binance.")


def _die(msg: str) -> None:
    err_console.print(f"[bold red]Error:[/bold red] {msg}")
    sys.exit(1)


def _confirm(yes: bool) -> None:
    if yes:
        return
    answer = typer.prompt("Proceed with trade? [y/N]", default="N")
    if answer.strip().lower() not in ("y", "yes"):
        console.print("[dim]Trade cancelled.[/dim]")
        raise typer.Exit()


def _build_plan(symbol, side, quantity, sl, tp) -> TradePlan:
    return TradePlan(
        symbol=symbol, side=side, quantity=quantity,
        initial_stop_loss=sl,
        stages=[TradeStage(take_profit=tp, next_stop_loss=sl)],
    )


@app.command()
def buy(
    symbol: str = typer.Argument(..., help="Trading pair, e.g. BTCUSDT"),
    quantity: float = typer.Argument(..., help="Quantity to buy"),
    sl: float = typer.Option(..., "--sl", help="Stop-loss price"),
    tp: float = typer.Option(..., "--tp", help="Take-profit price"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Place a spot BUY with stop-loss / take-profit."""
    broker = make_spot_broker()
    plan = _build_plan(symbol, Side.BUY, quantity, sl, tp)
    price, balances = None, {}
    with contextlib.suppress(Exception):
        price = broker.get_price(symbol)
    with contextlib.suppress(Exception):
        balances = broker.get_balance()
    print_trade_preview(price, balances, plan)
    _confirm(yes)
    try:
        result = broker.place_trade(plan)
    except Exception as exc:
        _die(str(exc))
    print_active_trade(result)


@app.command()
def sell(
    symbol: str = typer.Argument(..., help="Trading pair, e.g. BTCUSDT"),
    quantity: float = typer.Argument(..., help="Quantity to sell"),
    sl: float = typer.Option(..., "--sl", help="Stop-loss price"),
    tp: float = typer.Option(..., "--tp", help="Take-profit price"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Place a spot SELL with stop-loss / take-profit."""
    broker = make_spot_broker()
    plan = _build_plan(symbol, Side.SELL, quantity, sl, tp)
    price, balances = None, {}
    with contextlib.suppress(Exception):
        price = broker.get_price(symbol)
    with contextlib.suppress(Exception):
        balances = broker.get_balance()
    print_trade_preview(price, balances, plan)
    _confirm(yes)
    try:
        result = broker.place_trade(plan)
    except Exception as exc:
        _die(str(exc))
    print_active_trade(result)


@app.command()
def orders(
    symbol: str | None = typer.Argument(None, help="Filter by trading pair"),
) -> None:
    """List open spot orders."""
    try:
        open_orders = make_spot_broker().get_open_orders(symbol=symbol)
    except Exception as exc:
        _die(str(exc))
    print_orders_table(open_orders)


@app.command()
def balance() -> None:
    """Show spot account balances."""
    try:
        balances = make_spot_broker().get_balance()
    except Exception as exc:
        _die(str(exc))
    print_balance_table(balances)


@app.command()
def cancel(
    symbol: str = typer.Argument(..., help="Trading pair, e.g. BTCUSDT"),
    order_id: int = typer.Argument(..., help="Order ID to cancel"),
) -> None:
    """Cancel an open spot order."""
    try:
        make_spot_broker().cancel_order(symbol, order_id)
    except Exception as exc:
        _die(str(exc))
    msg = f"Order [bold]{order_id}[/bold] on [bold]{symbol}[/bold] cancelled."
    console.print(Panel(msg, style="green"))


if __name__ == "__main__":
    app()
