"""Unit tests for the trade CLI (trade_cli.py) — BinanceBroker is mocked."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from trading_bot.client.binance_client import BrokerError, TradeResult
from trading_bot.trade_cli import app

# The CLI creates the broker via a lazy import inside _broker(), so we must
# patch at the source module rather than at trade_cli.
_PATCH = "trading_bot.client.binance_client.BinanceBroker"

runner = CliRunner()


def _trade_result(side: str = "BUY") -> TradeResult:
    sl, tp = (95000.0, 105000.0) if side == "BUY" else (105000.0, 95000.0)
    return TradeResult(
        symbol="BTCUSDT",
        side=side,
        quantity=0.001,
        entry_price=100000.0,
        entry_order_id=1,
        oco_order_list_id=999,
        stop_loss=sl,
        take_profit=tp,
    )


def test_buy_command_success():
    mock_broker = MagicMock()
    mock_broker.place_trade.return_value = _trade_result("BUY")

    with patch(_PATCH, return_value=mock_broker):
        result = runner.invoke(
            app, ["buy", "BTCUSDT", "0.001", "--sl", "95000", "--tp", "105000", "--yes"]
        )

    assert result.exit_code == 0
    assert "Trade placed" in result.output


def test_sell_command_success():
    mock_broker = MagicMock()
    mock_broker.place_trade.return_value = _trade_result("SELL")

    with patch(_PATCH, return_value=mock_broker):
        result = runner.invoke(
            app, ["sell", "BTCUSDT", "0.001", "--sl", "105000", "--tp", "95000", "--yes"]
        )

    assert result.exit_code == 0
    assert "Trade placed" in result.output


def test_buy_broker_error_exits_nonzero():
    mock_broker = MagicMock()
    mock_broker.place_trade.side_effect = BrokerError("API down")

    with patch(_PATCH, return_value=mock_broker):
        result = runner.invoke(
            app, ["buy", "BTCUSDT", "0.001", "--sl", "95000", "--tp", "105000", "--yes"]
        )

    assert result.exit_code != 0
    assert "API down" in result.output


def test_orders_command():
    mock_broker = MagicMock()
    mock_broker.get_open_orders.return_value = [
        {
            "symbol": "BTCUSDT",
            "orderId": 7,
            "side": "BUY",
            "type": "LIMIT",
            "price": "98000",
            "origQty": "0.001",
            "status": "NEW",
        }
    ]

    with patch(_PATCH, return_value=mock_broker):
        result = runner.invoke(app, ["orders"])

    assert result.exit_code == 0


def test_balance_command():
    mock_broker = MagicMock()
    mock_broker.get_balance.return_value = {"BTC": {"free": "0.5", "locked": "0.0"}}

    with patch(_PATCH, return_value=mock_broker):
        result = runner.invoke(app, ["balance"])

    assert result.exit_code == 0
    assert "BTC" in result.output


def test_cancel_command():
    mock_broker = MagicMock()
    mock_broker.cancel_order.return_value = {"orderId": 12345, "status": "CANCELED"}

    with patch(_PATCH, return_value=mock_broker):
        result = runner.invoke(app, ["cancel", "BTCUSDT", "12345"])

    assert result.exit_code == 0
    mock_broker.cancel_order.assert_called_once_with("BTCUSDT", 12345)
