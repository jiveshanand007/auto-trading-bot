from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from trading_bot.core.domain.order import MarginType, Side


@dataclass(frozen=True)
class TradeStage:
    take_profit: float
    next_stop_loss: float


@dataclass(frozen=True)
class TradePlan:
    symbol: str
    side: Side
    quantity: float
    initial_stop_loss: float
    stages: list[TradeStage]
    leverage: int = 1
    margin_type: MarginType = MarginType.ISOLATED

    def __post_init__(self) -> None:
        if not self.stages:
            raise ValueError("TradePlan requires at least one stage")


class TradeStatus(str, Enum):
    OPEN = "OPEN"
    ADVANCING = "ADVANCING"
    CLOSED = "CLOSED"


@dataclass
class ActiveTrade:
    plan: TradePlan
    current_stage: int
    entry_order_id: int
    entry_price: float
    current_sl_order_id: int
    current_tp_order_id: int
    status: TradeStatus

    @property
    def current_stage_def(self) -> TradeStage:
        return self.plan.stages[self.current_stage]

    @property
    def has_next_stage(self) -> bool:
        return self.current_stage + 1 < len(self.plan.stages)
