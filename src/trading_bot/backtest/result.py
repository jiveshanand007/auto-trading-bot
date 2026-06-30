from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from trading_bot.core.domain.order import Side


@dataclass
class ClosedTrade:
    symbol: str
    side: Side
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    entry_bar_index: int
    exit_bar_index: int


@dataclass
class BacktestResult:
    strategy_name: str
    symbol: str
    initial_capital: float
    trades: list[ClosedTrade]
    equity_curve: pd.Series
