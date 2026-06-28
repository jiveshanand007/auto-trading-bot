from __future__ import annotations

from trading_bot.core.domain.order import Side
from trading_bot.core.domain.trade import TradePlan


def build_otoco(plan: TradePlan, working_price: float) -> dict:
    sl = plan.initial_stop_loss
    tp = plan.stages[0].take_profit
    qty = str(plan.quantity)

    if plan.side == Side.BUY:
        return {
            "symbol": plan.symbol,
            "workingType": "LIMIT",
            "workingSide": "BUY",
            "workingPrice": str(working_price),
            "workingQuantity": qty,
            "workingTimeInForce": "GTC",
            "pendingSide": "SELL",
            "pendingQuantity": qty,
            "pendingAboveType": "LIMIT_MAKER",
            "pendingAbovePrice": str(tp),
            "pendingBelowType": "STOP_LOSS_LIMIT",
            "pendingBelowStopPrice": str(sl),
            "pendingBelowPrice": str(round(sl * 0.999, 2)),
            "pendingBelowTimeInForce": "GTC",
        }
    return {
        "symbol": plan.symbol,
        "workingType": "LIMIT",
        "workingSide": "SELL",
        "workingPrice": str(working_price),
        "workingQuantity": qty,
        "workingTimeInForce": "GTC",
        "pendingSide": "BUY",
        "pendingQuantity": qty,
        "pendingAboveType": "STOP_LOSS_LIMIT",
        "pendingAboveStopPrice": str(sl),
        "pendingAbovePrice": str(round(sl * 1.001, 2)),
        "pendingAboveTimeInForce": "GTC",
        "pendingBelowType": "LIMIT_MAKER",
        "pendingBelowPrice": str(tp),
    }
