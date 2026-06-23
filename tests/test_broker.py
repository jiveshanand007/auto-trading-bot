"""Unit tests for BinanceBroker — all Binance client calls are mocked."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from binance.exceptions import BinanceAPIException

from trading_bot.broker.binance_broker import BinanceBroker, BrokerError, TradeResult

_PATCH = "trading_bot.broker.binance_broker.Client"


def _make_broker(mock_client: MagicMock) -> BinanceBroker:
    with patch(_PATCH, return_value=mock_client):
        return BinanceBroker()


def _fake_client() -> MagicMock:
    return MagicMock()


def test_place_trade_buy_success():
    client = _fake_client()
    client.get_symbol_ticker.return_value = {"price": "100000.0"}
    client.order_market_buy.return_value = {
        "orderId": 42,
        "fills": [{"qty": "0.001", "price": "100000.0"}],
    }
    client.get_order.return_value = {"status": "FILLED"}
    client._post.return_value = {"orderListId": 999}

    broker = _make_broker(client)
    result = broker.place_trade("BTCUSDT", "BUY", 0.001, 95000.0, 105000.0)

    assert isinstance(result, TradeResult)
    assert result.symbol == "BTCUSDT"
    assert result.side == "BUY"
    assert result.quantity == 0.001
    assert result.entry_price == pytest.approx(100000.0)
    assert result.entry_order_id == 42
    assert result.oco_order_list_id == 999
    assert result.stop_loss == 95000.0
    assert result.take_profit == 105000.0


def test_place_trade_invalid_sl_tp_raises():
    client = _fake_client()
    # SL > current_price for a BUY — should fail validation
    client.get_symbol_ticker.return_value = {"price": "100000.0"}

    broker = _make_broker(client)

    with pytest.raises(ValueError):
        broker.place_trade("BTCUSDT", "BUY", 0.001, 105000.0, 110000.0)

    client.order_market_buy.assert_not_called()


def test_place_trade_api_error_raises_broker_error():
    client = _fake_client()
    client.get_symbol_ticker.return_value = {"price": "100000.0"}

    exc = BinanceAPIException(MagicMock(status_code=400), 400, '{"code": -1013, "msg": "bad"}')
    client.order_market_buy.side_effect = exc

    broker = _make_broker(client)

    with pytest.raises(BrokerError) as exc_info:
        broker.place_trade("BTCUSDT", "BUY", 0.001, 95000.0, 105000.0)

    assert exc_info.value.original is exc


def test_get_open_orders_no_symbol():
    client = _fake_client()
    expected = [{"orderId": 1, "symbol": "BTCUSDT"}]
    client.get_open_orders.return_value = expected

    broker = _make_broker(client)
    result = broker.get_open_orders()

    assert result == expected
    client.get_open_orders.assert_called_once_with()


def test_get_balance_filters_zero():
    client = _fake_client()
    client.get_account.return_value = {
        "balances": [
            {"asset": "BTC", "free": "0.5", "locked": "0.0"},
            {"asset": "ETH", "free": "0.0", "locked": "0.0"},
            {"asset": "USDT", "free": "0.0", "locked": "100.0"},
        ]
    }

    broker = _make_broker(client)
    result = broker.get_balance()

    assert "BTC" in result
    assert "USDT" in result
    assert "ETH" not in result


def test_cancel_order():
    client = _fake_client()
    expected = {"orderId": 77, "status": "CANCELED"}
    client.cancel_order.return_value = expected

    broker = _make_broker(client)
    result = broker.cancel_order("BTCUSDT", 77)

    assert result == expected
    client.cancel_order.assert_called_once_with(symbol="BTCUSDT", orderId=77)
