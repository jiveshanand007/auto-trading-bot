from __future__ import annotations

from typing import Protocol

from trading_bot.core.domain.portfolio import PortfolioState
from trading_bot.core.domain.signal import Signal
from trading_bot.market_data.types import Bar


class IStrategy(Protocol):
    def on_bar(self, bar: Bar, portfolio: PortfolioState) -> Signal | None: ...
    def name(self) -> str: ...
