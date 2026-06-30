from __future__ import annotations

from typing import Protocol

from trading_bot.core.domain.portfolio import PortfolioState
from trading_bot.core.domain.signal import Signal


class IRiskManager(Protocol):
    def validate(self, signal: Signal, state: PortfolioState) -> Signal | None: ...
