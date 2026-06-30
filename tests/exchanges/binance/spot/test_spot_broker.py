# tests/exchanges/binance/spot/test_spot_broker.py
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from binance.exceptions import BinanceAPIException

from trading_bot.core.domain.order import Side
from trading_bot.core.domain.trade import ActiveTrade, TradePlan, TradeStage, TradeStatus
from trading_bot.exchanges.binance.common.errors import BrokerError
from trading_bot.exchanges.binance.spot.broker import SpotBroker


def _make_broker(mock_client: MagicMock) -> SpotBroker:
    return SpotBroker(client=mock_client)


def _fake_client() -> MagicMock:
    return MagicMock()


def _buy_plan() -> TradePlan:
    return TradePlan(
        symbol="BTCUSDT", side=Side.BUY, quantity=0.001,
        initial_stop_loss=95000.0,
        stages=[TradeStage(take_profit=105000.0, next_stop_loss=100000.0)],
    )


def _otoco_response() -> dict:
    return {
        "orderListId": 999,
        "orderReports": [
            {"orderId": 1, "status": "FILLED", "fills": [{"qty": "0.001", "price": "100000.0"}]},
            {"orderId": 2, "status": "PENDING_NEW"},
            {"orderId": 3, "status": "PENDING_NEW"},
        ],
    }


def test_place_trade_returns_active_trade():
    client = _fake_client()
    client.get_symbol_ticker.return_value = {"price": "100000.0"}
    client._post.return_value = _otoco_response()

    broker = _make_broker(client)
    result = broker.place_trade(_buy_plan())

    assert isinstance(result, ActiveTrade)
    assert result.plan.symbol == "BTCUSDT"
    assert result.entry_order_id == 1
    assert result.current_tp_order_id == 2
    assert result.current_sl_order_id == 3
    assert result.status == TradeStatus.OPEN
    assert result.entry_price == pytest.approx(100000.0)


def test_place_trade_api_error_raises_broker_error():
    client = _fake_client()
    client.get_symbol_ticker.return_value = {"price": "100000.0"}
    exc = BinanceAPIException(MagicMock(status_code=400), 400, '{"code": -1013, "msg": "bad"}')
    client._post.side_effect = exc

    broker = _make_broker(client)
    with pytest.raises(BrokerError) as exc_info:
        broker.place_trade(_buy_plan())
    assert exc_info.value.original is exc


def test_get_price_returns_float():
    client = _fake_client()
    client.get_symbol_ticker.return_value = {"price": "100000.5"}
    broker = _make_broker(client)
    assert broker.get_price("BTCUSDT") == pytest.approx(100000.5)


def test_get_balance_filters_zero_balances():
    client = _fake_client()
    client.get_account.return_value = {
        "balances": [
            {"asset": "BTC", "free": "0.5", "locked": "0.0"},
            {"asset": "ETH", "free": "0.0", "locked": "0.0"},
        ]
    }
    broker = _make_broker(client)
    result = broker.get_balance()
    assert "BTC" in result
    assert "ETH" not in result


def test_get_positions_returns_empty_list():
    broker = _make_broker(_fake_client())
    assert broker.get_positions() == []


def test_cancel_order_delegates_to_client():
    client = _fake_client()
    client.cancel_order.return_value = {"orderId": 77, "status": "CANCELED"}
    broker = _make_broker(client)
    result = broker.cancel_order("BTCUSDT", 77)
    assert result["status"] == "CANCELED"
    client.cancel_order.assert_called_once_with(symbol="BTCUSDT", orderId=77)


def test_advance_stage_cancels_and_replaces_orders():
    client = _fake_client()
    client.get_symbol_ticker.return_value = {"price": "100000.0"}

    broker = _make_broker(client)
    plan = TradePlan(
        symbol="BTCUSDT", side=Side.BUY, quantity=0.001,
        initial_stop_loss=95000.0,
        stages=[
            TradeStage(take_profit=105000.0, next_stop_loss=100000.0),
            TradeStage(take_profit=110000.0, next_stop_loss=106000.0),
        ],
    )
    trade = ActiveTrade(
        plan=plan, current_stage=0, entry_order_id=1, entry_price=100000.0,
        current_sl_order_id=3, current_tp_order_id=2, status=TradeStatus.OPEN,
    )

    client.cancel_order.return_value = {"status": "CANCELED"}
    client.create_order.return_value = {"orderId": 10, "status": "NEW"}

    updated = broker.advance_stage(trade)

    assert updated.current_stage == 1
    assert updated.status == TradeStatus.OPEN
    assert client.cancel_order.call_count == 2
