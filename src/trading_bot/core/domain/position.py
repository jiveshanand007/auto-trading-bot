from __future__ import annotations

from dataclasses import dataclass

from trading_bot.core.domain.order import MarginType, Side


@dataclass(frozen=True)
class Position:
    symbol: str
    side: Side
    quantity: float
    entry_price: float
    leverage: int
    liquidation_price: float
    unrealized_pnl: float
    margin_type: MarginType
