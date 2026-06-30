from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"
    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"


class MarginType(str, Enum):
    ISOLATED = "ISOLATED"
    CROSS = "CROSS"


@dataclass(frozen=True)
class TradeResult:
    symbol: str
    side: Side
    quantity: float
    entry_price: float
    entry_order_id: int
    stop_loss_order_id: int
    take_profit_order_id: int
    stop_loss: float
    take_profit: float
    raw_response: dict
