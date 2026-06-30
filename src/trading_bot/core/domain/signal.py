from __future__ import annotations

from dataclasses import dataclass

from trading_bot.core.domain.order import Side


@dataclass(frozen=True)
class Signal:
    symbol: str
    side: Side
    quantity: float
    entry_price: float
    stop_loss: float
    take_profit: float
    reason: str
