# src/trading_bot/cli/trade_cli.py
from __future__ import annotations

import contextlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer
from rich.panel import Panel

from trading_bot.analytics.metrics import compare_strategies, compute_metrics
from trading_bot.backtest.engine import run_backtest
from trading_bot.backtest.simulated_broker import SimulatedBroker
from trading_bot.cli._broker_factory import make_spot_broker
from trading_bot.cli._display import (
    console,
    err_console,
    print_active_trade,
    print_balance_table,
    print_orders_table,
    print_trade_preview,
)
from trading_bot.cli.futures_cli import futures_app
from trading_bot.core.domain.order import Side
from trading_bot.core.domain.trade import TradePlan, TradeStage
from trading_bot.market_data.storage import ParquetBarStore
from trading_bot.market_data.types import Timeframe
from trading_bot.research.optimizer import optimize as run_optimize
from trading_bot.risk.manager import RiskManager
from trading_bot.strategy.ma_crossover import MACrossoverStrategy
from trading_bot.strategy.rsi import RSIStrategy

_STRATEGY_MAP = {
    "ma-crossover": MACrossoverStrategy,
    "rsi": RSIStrategy,
}

_PARAM_GRIDS = {
    "ma-crossover": {"fast": [5, 9, 14, 21], "slow": [21, 50, 100, 200]},
    "rsi": {"period": [7, 14, 21], "oversold": [25, 30, 35], "overbought": [65, 70, 75]},
}

_DATA_ROOT = Path("data")

_SPARKLINE_CHARS = "▁▂▃▄▅▆▇█"


def _sparkline(values: list[float], width: int = 32) -> str:
    if not values:
        return ""
    lo, hi = min(values), max(values)
    span = hi - lo or 1.0
    step = len(values) / width
    chars = _SPARKLINE_CHARS
    result = []
    for i in range(width):
        idx = min(int(i * step), len(values) - 1)
        bucket = int((values[idx] - lo) / span * (len(chars) - 1))
        result.append(chars[bucket])
    return "".join(result)

app = typer.Typer(help="Spot trading — place and manage trades on Binance.")
app.add_typer(futures_app, name="futures")


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


@app.command()
def backtest(
    strategy: Annotated[
        list[str], typer.Option("--strategy", help="Strategy: ma-crossover, rsi")
    ] = ["ma-crossover"],  # noqa: B006
    symbol: str = typer.Option("BTCUSDT", "--symbol", help="Trading pair"),
    timeframe: str = typer.Option("H1", "--timeframe", help="Candle timeframe"),
    start: str = typer.Option(..., "--start", help="Start date YYYY-MM-DD"),
    end: str = typer.Option(..., "--end", help="End date YYYY-MM-DD"),
    capital: float = typer.Option(10_000.0, "--capital", help="Initial capital (USDT)"),
    fee: float = typer.Option(0.001, "--fee", help="Fee rate per trade"),
) -> None:
    """Run a backtest for one or more strategies and print a metrics table."""
    try:
        tf = Timeframe(timeframe)
    except ValueError:
        _die(f"Unknown timeframe '{timeframe}'. Valid: {[t.value for t in Timeframe]}")

    unknown = [s for s in strategy if s not in _STRATEGY_MAP]
    if unknown:
        _die(f"Unknown strategy/ies: {unknown}. Valid: {list(_STRATEGY_MAP)}")

    start_dt = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end_dt = datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    store = ParquetBarStore(_DATA_ROOT)
    bars = store.read(symbol, tf, start=start_dt, end=end_dt)

    if not bars:
        console.print(
            f"[yellow]No local data for {symbol}/{timeframe}. Downloading…[/yellow]"
        )
        try:
            from trading_bot.market_data.binance_client import BinanceKlineClient
            from trading_bot.market_data.downloader import KlineDownloader

            downloader = KlineDownloader(BinanceKlineClient(), store)
            n = downloader.download(symbol, tf, start_dt, end_dt)
            console.print(f"[green]Downloaded {n} bars.[/green]")
            bars = store.read(symbol, tf, start=start_dt, end=end_dt)
        except Exception as exc:
            _die(f"Auto-download failed: {exc}")

    if not bars:
        _die(f"No bars available for {symbol}/{timeframe} in {start}..{end}")

    all_metrics = []
    for name in strategy:
        strat = _STRATEGY_MAP[name]()
        result = run_backtest(strat, RiskManager(), SimulatedBroker(capital, fee), bars)
        m = compute_metrics(result)
        all_metrics.append(m)

        if len(strategy) == 1:
            spark = _sparkline(list(result.equity_curve.values))
            console.print(Panel(
                f"[bold]{name}[/bold]  {symbol}/{timeframe}  {start} → {end}\n"
                f"Return: [cyan]{m.total_return_pct:+.2f}%[/cyan]  "
                f"Sharpe: [cyan]{m.sharpe:.2f}[/cyan]  "
                f"MaxDD: [red]{m.max_drawdown_pct:.2f}%[/red]  "
                f"Trades: {m.total_trades}\n"
                f"[dim]{spark}[/dim]",
                title="Backtest Result",
            ))

    if len(strategy) > 1:
        console.print(compare_strategies(all_metrics))


@app.command()
def optimize(
    strategy: str = typer.Option("ma-crossover", "--strategy", help="Strategy to optimize"),
    symbol: str = typer.Option("BTCUSDT", "--symbol"),
    timeframe: str = typer.Option("H1", "--timeframe"),
    train_ratio: float = typer.Option(0.67, "--train-ratio", help="Fraction used for training"),
    capital: float = typer.Option(10_000.0, "--capital"),
    fee: float = typer.Option(0.001, "--fee"),
) -> None:
    """Grid-search best params on train split, validate on unseen test split."""
    try:
        tf = Timeframe(timeframe)
    except ValueError:
        _die(f"Unknown timeframe '{timeframe}'.")

    if strategy not in _STRATEGY_MAP:
        _die(f"Unknown strategy '{strategy}'. Valid: {list(_STRATEGY_MAP)}")

    store = ParquetBarStore(_DATA_ROOT)
    bars = store.read(symbol, tf)

    if not bars:
        console.print(f"[yellow]No local data for {symbol}/{timeframe}. Downloading…[/yellow]")
        try:
            from trading_bot.market_data.binance_client import BinanceKlineClient
            from trading_bot.market_data.downloader import KlineDownloader

            n = KlineDownloader(BinanceKlineClient(), store).download(
                symbol, tf,
                datetime(2017, 1, 1, tzinfo=timezone.utc),
                datetime.now(tz=timezone.utc),
            )
            console.print(f"[green]Downloaded {n} bars.[/green]")
            bars = store.read(symbol, tf)
        except Exception as exc:
            _die(f"Auto-download failed: {exc}")

    if not bars:
        _die(f"No bars available for {symbol}/{timeframe}.")

    n_train = int(len(bars) * train_ratio)
    n_test = len(bars) - n_train
    console.print(
        f"[dim]Total bars: {len(bars)} | "
        f"Train: {n_train} ({train_ratio:.0%}) | "
        f"Test: {n_test} ({1-train_ratio:.0%})[/dim]"
    )

    param_grid = _PARAM_GRIDS[strategy]
    n_combos = 1
    for v in param_grid.values():
        n_combos *= len(v)
    console.print(f"[dim]Grid: {param_grid} → {n_combos} combinations[/dim]")

    with console.status("[bold green]Optimizing…[/bold green]"):
        result = run_optimize(
            _STRATEGY_MAP[strategy], param_grid, bars,
            train_ratio=train_ratio,
            initial_capital=capital,
            fee_rate=fee,
        )

    tr = result.train_metrics
    te = result.test_metrics
    ratio_color = "green" if result.overfitting_ratio >= 0.5 else "red"

    console.print(Panel(
        f"[bold]Best params:[/bold] {result.best_params}\n"
        f"[bold]Data:[/bold] {result.train_start:%Y-%m-%d} → {result.test_end:%Y-%m-%d}  "
        f"({result.n_total_bars} bars)\n\n"
        f"{'Metric':<18} {'Train':>10} {'Test (OOS)':>12}\n"
        f"{'-'*42}\n"
        f"{'Return %':<18} {tr.total_return_pct:>10.2f} {te.total_return_pct:>12.2f}\n"
        f"{'Sharpe':<18} {tr.sharpe:>10.2f} {te.sharpe:>12.2f}\n"
        f"{'Sortino':<18} {tr.sortino:>10.2f} {te.sortino:>12.2f}\n"
        f"{'Max DD %':<18} {tr.max_drawdown_pct:>10.2f} {te.max_drawdown_pct:>12.2f}\n"
        f"{'Win Rate %':<18} {tr.win_rate_pct:>10.2f} {te.win_rate_pct:>12.2f}\n"
        f"{'Profit Factor':<18} {tr.profit_factor:>10.2f} {te.profit_factor:>12.2f}\n"
        f"{'Trades':<18} {tr.total_trades:>10} {te.total_trades:>12}\n\n"
        f"Overfitting ratio: [{ratio_color}]{result.overfitting_ratio:.2f}[/{ratio_color}]"
        f"  (test÷train Sharpe — target ≥ 0.5)",
        title=f"Optimization: {result.strategy_name} on {symbol}/{timeframe}",
    ))


if __name__ == "__main__":
    app()
