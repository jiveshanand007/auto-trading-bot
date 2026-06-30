from __future__ import annotations

import pytest

from trading_bot.core.domain.order import Side
from trading_bot.core.domain.trade import TradePlan, TradeStage
from trading_bot.exchanges.binance.futures.validator import validate


def _plan(side=Side.BUY, sl=95000.0, tp=105000.0, qty=0.001, leverage=5) -> TradePlan:
    return TradePlan(
        symbol="BTCUSDT",
        side=side,
        quantity=qty,
        initial_stop_loss=sl,
        stages=[TradeStage(take_profit=tp, next_stop_loss=sl)],
        leverage=leverage,
    )


def test_valid_long_passes():
    validate(_plan(), current_price=100000.0)


def test_valid_short_passes():
    validate(_plan(side=Side.SELL, sl=105000.0, tp=95000.0), current_price=100000.0)


def test_leverage_zero_raises():
    with pytest.raises(ValueError, match="leverage"):
        validate(_plan(leverage=0), current_price=100000.0)


def test_leverage_above_125_raises():
    with pytest.raises(ValueError, match="leverage"):
        validate(_plan(leverage=126), current_price=100000.0)


def test_buy_sl_above_price_raises():
    with pytest.raises(ValueError, match="BUY validation failed"):
        validate(_plan(sl=105000.0, tp=110000.0), current_price=100000.0)


def test_sell_sl_below_price_raises():
    with pytest.raises(ValueError, match="SELL validation failed"):
        validate(_plan(side=Side.SELL, sl=95000.0, tp=90000.0), current_price=100000.0)


def test_min_notional_too_small_raises():
    with pytest.raises(ValueError, match="notional"):
        validate(_plan(qty=0.00001), current_price=100000.0)
