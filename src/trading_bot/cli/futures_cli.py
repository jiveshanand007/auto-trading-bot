# src/trading_bot/cli/futures_cli.py
from __future__ import annotations

import contextlib
import sys

import typer

from trading_bot.cli._broker_factory import make_futures_broker
from trading_bot.cli._display import (
    console,
    err_console,
    print_active_trade,
    print_balance_table,
    print_orders_table,
    print_positions_table,
    print_trade_preview,
)
from trading_bot.config import get_settings
from trading_bot.core.domain.order import MarginType, Side
from trading_bot.core.domain.trade import TradePlan, TradeStage

futures_app = typer.Typer(help="USDM futures trading — Binance perpetuals.")


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


def _parse_stages(
    tp_values: list[float],
    next_sl_values: list[float],
    initial_sl: float,
) -> list[TradeStage]:
    fallback_sl = next_sl_values[-1] if next_sl_values else initial_sl
    stages = []
    for i, tp in enumerate(tp_values):
        next_sl = next_sl_values[i] if i < len(next_sl_values) else fallback_sl
        stages.append(TradeStage(take_profit=tp, next_stop_loss=next_sl))
    return stages


def _build_futures_plan(
    symbol: str,
    side: Side,
    quantity: float,
    sl: float,
    tp_values: list[float],
    next_sl_values: list[float],
    leverage: int,
    margin: str,
) -> TradePlan:
    return TradePlan(
        symbol=symbol, side=side, quantity=quantity,
        initial_stop_loss=sl,
        stages=_parse_stages(tp_values, next_sl_values, sl),
        leverage=leverage,
        margin_type=MarginType(margin.upper()),
    )


@futures_app.command()
def buy(
    symbol: str = typer.Argument(..., help="Trading pair, e.g. BTCUSDT"),
    quantity: float = typer.Argument(..., help="Contract quantity"),
    sl: float = typer.Option(..., "--sl", help="Initial stop-loss price"),
    tp: list[float] = typer.Option(..., "--tp", help="Take-profit level(s)"),  # noqa: B008
    next_sl: list[float] = typer.Option([], "--next-sl", help="SL after each TP hit"),  # noqa: B008
    leverage: int = typer.Option(0, "--leverage", "-l", help="Leverage (0 = use config default)"),
    margin: str = typer.Option("", "--margin", help="Margin type: isolated or cross"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Open a LONG (BUY) futures position with stop-loss / take-profit."""
    settings = get_settings()
    lev = leverage if leverage > 0 else settings.futures_leverage
    mgn = margin if margin else settings.futures_margin_type
    broker = make_futures_broker()
    plan = _build_futures_plan(symbol, Side.BUY, quantity, sl, tp, next_sl, lev, mgn)
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
        return  # unreachable but satisfies type checker
    print_active_trade(result)


@futures_app.command()
def sell(
    symbol: str = typer.Argument(..., help="Trading pair, e.g. BTCUSDT"),
    quantity: float = typer.Argument(..., help="Contract quantity"),
    sl: float = typer.Option(..., "--sl", help="Initial stop-loss price"),
    tp: list[float] = typer.Option(..., "--tp", help="Take-profit level(s)"),  # noqa: B008
    next_sl: list[float] = typer.Option([], "--next-sl", help="SL after each TP hit"),  # noqa: B008
    leverage: int = typer.Option(0, "--leverage", "-l", help="Leverage (0 = use config default)"),
    margin: str = typer.Option("", "--margin", help="Margin type: isolated or cross"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Open a SHORT (SELL) futures position with stop-loss / take-profit."""
    settings = get_settings()
    lev = leverage if leverage > 0 else settings.futures_leverage
    mgn = margin if margin else settings.futures_margin_type
    broker = make_futures_broker()
    plan = _build_futures_plan(symbol, Side.SELL, quantity, sl, tp, next_sl, lev, mgn)
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
        return  # unreachable but satisfies type checker
    print_active_trade(result)


@futures_app.command()
def positions(
    symbol: str | None = typer.Argument(None, help="Filter by trading pair"),
) -> None:
    """List open futures positions."""
    try:
        pos = make_futures_broker().get_positions(symbol=symbol)
    except Exception as exc:
        _die(str(exc))
        return  # unreachable but satisfies type checker
    print_positions_table(pos)


@futures_app.command()
def orders(
    symbol: str | None = typer.Argument(None, help="Filter by trading pair"),
) -> None:
    """List open futures orders."""
    try:
        open_orders = make_futures_broker().get_open_orders(symbol=symbol)
    except Exception as exc:
        _die(str(exc))
        return  # unreachable but satisfies type checker
    print_orders_table(open_orders)


@futures_app.command()
def balance() -> None:
    """Show futures account balance."""
    try:
        bal = make_futures_broker().get_balance()
    except Exception as exc:
        _die(str(exc))
        return  # unreachable but satisfies type checker
    print_balance_table(bal)


@futures_app.command()
def cancel(
    symbol: str = typer.Argument(..., help="Trading pair"),
    order_id: int = typer.Argument(..., help="Order ID to cancel"),
) -> None:
    """Cancel an open futures order."""
    from rich.panel import Panel

    try:
        make_futures_broker().cancel_order(symbol, order_id)
    except Exception as exc:
        _die(str(exc))
        return  # unreachable but satisfies type checker
    console.print(Panel(
        f"Order [bold]{order_id}[/bold] on [bold]{symbol}[/bold] cancelled.",
        style="green",
    ))


@futures_app.command()
def close(
    symbol: str = typer.Argument(..., help="Trading pair to close"),
) -> None:
    """Market-close an entire futures position."""
    try:
        result = make_futures_broker().close_position(symbol)
    except Exception as exc:
        _die(str(exc))
        return  # unreachable but satisfies type checker
    console.print(f"[bold green]Position closed:[/bold green] {result}")
