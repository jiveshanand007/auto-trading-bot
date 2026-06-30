from __future__ import annotations

from dataclasses import dataclass

from trading_bot.core.domain.position import Position


@dataclass(frozen=True)
class PortfolioState:
    equity: float
    cash: float
    open_positions: list[Position]
    daily_start_equity: float
    is_halted: bool
