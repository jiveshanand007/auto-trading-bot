from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from rich.table import Table

from trading_bot.backtest.result import BacktestResult


@dataclass
class AnalyticsResult:
    strategy_name: str
    total_return_pct: float
    cagr: float
    sharpe: float
    sortino: float
    max_drawdown_pct: float
    win_rate_pct: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    total_trades: int
    exposure_pct: float
    equity_curve: pd.Series


def compute_metrics(result: BacktestResult) -> AnalyticsResult:
    eq = result.equity_curve
    initial = result.initial_capital
    final = float(eq.iloc[-1]) if len(eq) > 0 else initial

    total_return_pct = (final - initial) / initial * 100.0

    # CAGR
    if len(eq) >= 2 and isinstance(eq.index, pd.DatetimeIndex):
        years = (eq.index[-1] - eq.index[0]).total_seconds() / (365.25 * 86400)
    else:
        years = 0.0

    if years > 0 and initial > 0:
        try:
            cagr = ((final / initial) ** (1.0 / years) - 1.0) * 100.0
        except OverflowError:
            cagr = total_return_pct
    else:
        cagr = total_return_pct

    # Returns-based stats (bar-level)
    returns = eq.pct_change().dropna()
    ann_factor = math.sqrt(252)

    if len(returns) > 1 and returns.std() > 0:
        sharpe = float(returns.mean() / returns.std() * ann_factor)
    else:
        sharpe = 0.0

    downside = returns[returns < 0]
    if len(downside) > 1 and downside.std() > 0:
        sortino = float(returns.mean() / downside.std() * ann_factor)
    else:
        sortino = 0.0

    # Max drawdown
    running_max = eq.cummax()
    drawdown = (running_max - eq) / running_max.replace(0, np.nan)
    max_drawdown_pct = float(drawdown.max() * 100.0) if len(drawdown) > 0 else 0.0

    # Trade statistics
    trades = result.trades
    total_trades = len(trades)
    wins = [t.pnl for t in trades if t.pnl > 0]
    losses = [t.pnl for t in trades if t.pnl <= 0]

    win_rate_pct = len(wins) / total_trades * 100.0 if total_trades > 0 else 0.0
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0

    gross_loss = abs(sum(losses))
    profit_factor = sum(wins) / gross_loss if gross_loss > 0 else float("inf")

    # Exposure
    n_bars = len(eq)
    if n_bars > 0 and trades:
        exposed: set[int] = set()
        for t in trades:
            exposed.update(range(t.entry_bar_index, t.exit_bar_index + 1))
        exposure_pct = len(exposed) / n_bars * 100.0
    else:
        exposure_pct = 0.0

    return AnalyticsResult(
        strategy_name=result.strategy_name,
        total_return_pct=round(total_return_pct, 4),
        cagr=round(cagr, 4),
        sharpe=round(sharpe, 4),
        sortino=round(sortino, 4),
        max_drawdown_pct=round(max_drawdown_pct, 4),
        win_rate_pct=round(win_rate_pct, 4),
        profit_factor=round(profit_factor, 4),
        avg_win=round(avg_win, 4),
        avg_loss=round(avg_loss, 4),
        total_trades=total_trades,
        exposure_pct=round(exposure_pct, 4),
        equity_curve=eq,
    )


def compare_strategies(metrics: list[AnalyticsResult]) -> Table:
    """Return a Rich table of strategies sorted by Sharpe descending."""
    table = Table(title="Strategy Comparison", show_header=True, header_style="bold cyan")
    table.add_column("Strategy", style="bold")
    table.add_column("Return %", justify="right")
    table.add_column("CAGR %", justify="right")
    table.add_column("Sharpe", justify="right")
    table.add_column("Sortino", justify="right")
    table.add_column("MaxDD %", justify="right")
    table.add_column("WinRate %", justify="right")
    table.add_column("PF", justify="right")
    table.add_column("Trades", justify="right")

    for m in sorted(metrics, key=lambda x: x.sharpe, reverse=True):
        pf = f"{m.profit_factor:.2f}" if math.isfinite(m.profit_factor) else "∞"
        table.add_row(
            m.strategy_name,
            f"{m.total_return_pct:.2f}",
            f"{m.cagr:.2f}",
            f"{m.sharpe:.2f}",
            f"{m.sortino:.2f}",
            f"{m.max_drawdown_pct:.2f}",
            f"{m.win_rate_pct:.2f}",
            pf,
            str(m.total_trades),
        )
    return table
