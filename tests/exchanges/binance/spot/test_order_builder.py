from __future__ import annotations

from trading_bot.core.domain.order import Side
from trading_bot.core.domain.trade import TradePlan, TradeStage
from trading_bot.exchanges.binance.spot.order_builder import build_otoco


def _plan(side: Side) -> TradePlan:
    sl, tp = (95000.0, 105000.0) if side == Side.BUY else (105000.0, 95000.0)
    return TradePlan(
        symbol="BTCUSDT", side=side, quantity=0.001,
        initial_stop_loss=sl, stages=[TradeStage(take_profit=tp, next_stop_loss=sl)],
    )


def test_buy_otoco_working_side():
    payload = build_otoco(_plan(Side.BUY), working_price=100100.0)
    assert payload["workingSide"] == "BUY"
    assert payload["pendingSide"] == "SELL"


def test_sell_otoco_working_side():
    payload = build_otoco(_plan(Side.SELL), working_price=99900.0)
    assert payload["workingSide"] == "SELL"
    assert payload["pendingSide"] == "BUY"


def test_buy_otoco_has_required_keys():
    payload = build_otoco(_plan(Side.BUY), working_price=100100.0)
    for key in ("symbol", "workingType", "workingPrice", "workingQuantity",
                "pendingAboveType", "pendingAbovePrice",
                "pendingBelowType", "pendingBelowStopPrice"):
        assert key in payload, f"missing key: {key}"


def test_buy_otoco_prices_are_strings():
    payload = build_otoco(_plan(Side.BUY), working_price=100100.0)
    assert isinstance(payload["workingPrice"], str)
    assert isinstance(payload["pendingAbovePrice"], str)
