from __future__ import annotations

from trading_bot.core.domain.order import Side
from trading_bot.core.domain.trade import TradePlan


def validate(plan: TradePlan, current_price: float) -> None:
    sl = plan.initial_stop_loss
    tp = plan.stages[0].take_profit

    if plan.side == Side.BUY:
        if not (sl < current_price < tp):
            raise ValueError(
                f"BUY validation failed: stop_loss={sl} must be < "
                f"current_price={current_price} < take_profit={tp}"
            )
    else:
        if not (tp < current_price < sl):
            raise ValueError(
                f"SELL validation failed: take_profit={tp} must be < "
                f"current_price={current_price} < stop_loss={sl}"
            )
