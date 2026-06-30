from __future__ import annotations

from typing import Protocol

from trading_bot.core.ports.strategy import IStrategy
from trading_bot.market_data.types import Timeframe


class IStrategySelector(Protocol):
    def select(self, symbol: str, timeframe: Timeframe) -> IStrategy: ...
