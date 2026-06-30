from __future__ import annotations

from typing import Protocol

from trading_bot.core.domain.trade import ActiveTrade


class ITradeStore(Protocol):
    def save(self, trade: ActiveTrade) -> None: ...
    def get_active(self, symbol: str) -> ActiveTrade | None: ...
    def get_all_active(self) -> list[ActiveTrade]: ...
