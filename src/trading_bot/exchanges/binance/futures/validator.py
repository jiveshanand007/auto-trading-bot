from __future__ import annotations

from trading_bot.core.domain.order import Side
from trading_bot.core.domain.trade import TradePlan

_MIN_NOTIONAL = 5.0
_MAX_LEVERAGE = 125


def validate(plan: TradePlan, current_price: float) -> None:
    if not (1 <= plan.leverage <= _MAX_LEVERAGE):
        raise ValueError(f"leverage must be 1–{_MAX_LEVERAGE}, got {plan.leverage}")

    notional = plan.quantity * current_price
    if notional < _MIN_NOTIONAL:
        raise ValueError(
            f"Order notional {notional:.4f} USDT is below minimum {_MIN_NOTIONAL} USDT"
        )

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
