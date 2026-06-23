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


def _otoco_response(order_id: int = 42, order_list_id: int = 999) -> dict:
    return {
        "orderListId": order_list_id,
        "contingencyType": "OTO",
        "orderReports": [
            {
                "orderId": order_id,
                "status": "FILLED",
                "fills": [{"qty": "0.001", "price": "100000.0"}],
            },
            {"orderId": order_id + 1, "status": "PENDING_NEW"},
            {"orderId": order_id + 2, "status": "PENDING_NEW"},
        ],
    }


def test_place_trade_buy_success():
    client = _fake_client()
    client.get_symbol_ticker.return_value = {"price": "100000.0"}
    client._post.return_value = _otoco_response()

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
    # Single OTOCO call — no separate market order or OCO post
    client._post.assert_called_once()
    assert "otoco" in client._post.call_args[0][0]


def test_place_trade_sell_success():
    client = _fake_client()
    client.get_symbol_ticker.return_value = {"price": "100000.0"}
    client._post.return_value = _otoco_response()

    broker = _make_broker(client)
    result = broker.place_trade("BTCUSDT", "SELL", 0.001, 105000.0, 95000.0)

    assert result.side == "SELL"
    data_sent = client._post.call_args[1]["data"]
    assert data_sent["workingSide"] == "SELL"
    assert data_sent["pendingSide"] == "BUY"


def test_place_trade_invalid_sl_tp_raises():
    client = _fake_client()
    client.get_symbol_ticker.return_value = {"price": "100000.0"}

    broker = _make_broker(client)

    with pytest.raises(ValueError):
        broker.place_trade("BTCUSDT", "BUY", 0.001, 105000.0, 110000.0)

    client._post.assert_not_called()


def test_place_trade_api_error_raises_broker_error():
    client = _fake_client()
    client.get_symbol_ticker.return_value = {"price": "100000.0"}

    exc = BinanceAPIException(MagicMock(status_code=400), 400, '{"code": -1013, "msg": "bad"}')
    client._post.side_effect = exc

    broker = _make_broker(client)

    with pytest.raises(BrokerError) as exc_info:
        broker.place_trade("BTCUSDT", "BUY", 0.001, 95000.0, 105000.0)

    assert exc_info.value.original is exc


def test_place_trade_entry_price_from_fills():
    """Verify weighted-average fill price is computed correctly."""
    client = _fake_client()
    client.get_symbol_ticker.return_value = {"price": "100000.0"}
    client._post.return_value = {
        "orderListId": 1,
        "orderReports": [
            {
                "orderId": 1,
                "fills": [
                    {"qty": "0.0005", "price": "99000.0"},
                    {"qty": "0.0005", "price": "101000.0"},
                ],
            }
        ],
    }

    broker = _make_broker(client)
    result = broker.place_trade("BTCUSDT", "BUY", 0.001, 95000.0, 105000.0)

    assert result.entry_price == pytest.approx(100000.0)


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
