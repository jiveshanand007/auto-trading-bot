from __future__ import annotations

import pytest

from trading_bot.core.domain.order import Side
from trading_bot.core.domain.trade import TradePlan, TradeStage
from trading_bot.exchanges.binance.spot.validator import validate


def _buy_plan(sl=95000.0, tp=105000.0) -> TradePlan:
    return TradePlan(
        symbol="BTCUSDT", side=Side.BUY, quantity=0.001,
        initial_stop_loss=sl, stages=[TradeStage(take_profit=tp, next_stop_loss=sl)],
    )


def _sell_plan(sl=105000.0, tp=95000.0) -> TradePlan:
    return TradePlan(
        symbol="BTCUSDT", side=Side.SELL, quantity=0.001,
        initial_stop_loss=sl, stages=[TradeStage(take_profit=tp, next_stop_loss=sl)],
    )


def test_valid_buy_passes():
    validate(_buy_plan(), current_price=100000.0)  # no exception


def test_valid_sell_passes():
    validate(_sell_plan(), current_price=100000.0)  # no exception


def test_buy_sl_above_price_raises():
    with pytest.raises(ValueError, match="BUY validation failed"):
        validate(_buy_plan(sl=105000.0, tp=110000.0), current_price=100000.0)


def test_buy_tp_below_price_raises():
    with pytest.raises(ValueError, match="BUY validation failed"):
        validate(_buy_plan(sl=90000.0, tp=99000.0), current_price=100000.0)


def test_sell_sl_below_price_raises():
    with pytest.raises(ValueError, match="SELL validation failed"):
        validate(_sell_plan(sl=95000.0, tp=90000.0), current_price=100000.0)
