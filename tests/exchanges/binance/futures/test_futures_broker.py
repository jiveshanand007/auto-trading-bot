from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from binance.exceptions import BinanceAPIException

from trading_bot.core.domain.order import Side
from trading_bot.core.domain.position import Position
from trading_bot.core.domain.trade import ActiveTrade, TradePlan, TradeStage, TradeStatus
from trading_bot.exchanges.binance.common.errors import BrokerError
from trading_bot.exchanges.binance.futures.broker import FuturesBroker


def _make_broker(mock_client: MagicMock) -> FuturesBroker:
    return FuturesBroker(client=mock_client)


def _fake_client() -> MagicMock:
    return MagicMock()


def _buy_plan(stages=None) -> TradePlan:
    if stages is None:
        stages = [TradeStage(take_profit=105000.0, next_stop_loss=100000.0)]
    return TradePlan(
        symbol="BTCUSDT", side=Side.BUY, quantity=0.001,
        initial_stop_loss=95000.0, stages=stages, leverage=5,
    )


def _entry_response(order_id: int = 1) -> dict:
    return {"orderId": order_id, "status": "FILLED", "avgPrice": "100000.0"}


def _order_response(order_id: int) -> dict:
    return {"orderId": order_id, "status": "NEW"}


def test_place_trade_returns_active_trade():
    client = _fake_client()
    client.futures_symbol_ticker.return_value = {"price": "100000.0"}
    client.futures_create_order.side_effect = [
        _entry_response(1),
        _order_response(2),
        _order_response(3),
    ]

    broker = _make_broker(client)
    result = broker.place_trade(_buy_plan())

    assert isinstance(result, ActiveTrade)
    assert result.entry_order_id == 1
    assert result.current_sl_order_id == 2
    assert result.current_tp_order_id == 3
    assert result.status == TradeStatus.OPEN
    assert result.entry_price == pytest.approx(100000.0)


def test_place_trade_sets_leverage_and_margin_type():
    client = _fake_client()
    client.futures_symbol_ticker.return_value = {"price": "100000.0"}
    client.futures_create_order.side_effect = [
        _entry_response(1), _order_response(2), _order_response(3)
    ]

    broker = _make_broker(client)
    broker.place_trade(_buy_plan())

    client.futures_change_leverage.assert_called_once_with(symbol="BTCUSDT", leverage=5)
    client.futures_change_margin_type.assert_called_once()


def test_place_trade_api_error_raises_broker_error():
    client = _fake_client()
    client.futures_symbol_ticker.return_value = {"price": "100000.0"}
    exc = BinanceAPIException(MagicMock(status_code=400), 400, '{"code": -1013, "msg": "bad"}')
    client.futures_create_order.side_effect = exc

    broker = _make_broker(client)
    with pytest.raises(BrokerError):
        broker.place_trade(_buy_plan())


def test_advance_stage_cancels_and_replaces():
    client = _fake_client()
    client.futures_cancel_order.return_value = {"status": "CANCELED"}
    client.futures_create_order.side_effect = [_order_response(10), _order_response(11)]

    broker = _make_broker(client)
    plan = _buy_plan(stages=[
        TradeStage(take_profit=105000.0, next_stop_loss=100000.0),
        TradeStage(take_profit=110000.0, next_stop_loss=106000.0),
    ])
    trade = ActiveTrade(
        plan=plan, current_stage=0, entry_order_id=1, entry_price=100000.0,
        current_sl_order_id=2, current_tp_order_id=3, status=TradeStatus.OPEN,
    )

    updated = broker.advance_stage(trade)

    assert updated.current_stage == 1
    assert updated.current_sl_order_id == 10
    assert updated.current_tp_order_id == 11
    assert updated.status == TradeStatus.OPEN
    assert client.futures_cancel_order.call_count == 2


def test_advance_stage_no_next_raises():
    client = _fake_client()
    broker = _make_broker(client)
    plan = _buy_plan()
    trade = ActiveTrade(
        plan=plan, current_stage=0, entry_order_id=1, entry_price=100000.0,
        current_sl_order_id=2, current_tp_order_id=3, status=TradeStatus.OPEN,
    )
    with pytest.raises(BrokerError, match="No next stage"):
        broker.advance_stage(trade)


def test_get_balance_returns_futures_account():
    client = _fake_client()
    client.futures_account.return_value = {
        "availableBalance": "1000.0",
        "totalMarginBalance": "1100.0",
        "totalUnrealizedProfit": "100.0",
    }
    broker = _make_broker(client)
    result = broker.get_balance()
    assert result["availableBalance"] == "1000.0"


def test_get_positions_maps_to_position_objects():
    client = _fake_client()
    client.futures_position_information.return_value = [
        {
            "symbol": "BTCUSDT",
            "positionAmt": "0.001",
            "entryPrice": "100000.0",
            "leverage": "5",
            "liquidationPrice": "80000.0",
            "unrealizedProfit": "50.0",
            "marginType": "isolated",
        },
        {"symbol": "ETHUSDT", "positionAmt": "0.0"},
    ]
    broker = _make_broker(client)
    positions = broker.get_positions()
    assert len(positions) == 1
    assert positions[0].symbol == "BTCUSDT"
    assert isinstance(positions[0], Position)


def test_get_positions_filtered_by_symbol():
    client = _fake_client()
    client.futures_position_information.return_value = []
    broker = _make_broker(client)
    broker.get_positions(symbol="BTCUSDT")
    client.futures_position_information.assert_called_once_with(symbol="BTCUSDT")
