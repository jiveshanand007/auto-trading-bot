"""Unit tests for the trade CLI (cli/trade_cli.py) — make_spot_broker is mocked."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from trading_bot.cli.trade_cli import app
from trading_bot.core.domain.order import Side
from trading_bot.core.domain.trade import ActiveTrade, TradePlan, TradeStage, TradeStatus
from trading_bot.exchanges.binance.common.errors import BrokerError

# Patch the factory function used inside cli/trade_cli.py
_PATCH_BROKER = "trading_bot.cli.trade_cli.make_spot_broker"

runner = CliRunner()


def _active_trade(side: str = "BUY") -> ActiveTrade:
    s = Side(side)
    sl, tp = (95000.0, 105000.0) if s == Side.BUY else (105000.0, 95000.0)
    plan = TradePlan(
        symbol="BTCUSDT", side=s, quantity=0.001,
        initial_stop_loss=sl,
        stages=[TradeStage(take_profit=tp, next_stop_loss=sl)],
    )
    return ActiveTrade(
        plan=plan, current_stage=0, entry_order_id=1, entry_price=100000.0,
        current_sl_order_id=10, current_tp_order_id=11, status=TradeStatus.OPEN,
    )


def test_buy_command_success():
    mock_broker = MagicMock()
    mock_broker.get_price.return_value = 100000.0
    mock_broker.get_balance.return_value = {}
    mock_broker.place_trade.return_value = _active_trade("BUY")

    with patch(_PATCH_BROKER, return_value=mock_broker):
        result = runner.invoke(
            app, ["buy", "BTCUSDT", "0.001", "--sl", "95000", "--tp", "105000", "--yes"]
        )

    assert result.exit_code == 0
    assert "Trade placed" in result.output


def test_sell_command_success():
    mock_broker = MagicMock()
    mock_broker.get_price.return_value = 100000.0
    mock_broker.get_balance.return_value = {}
    mock_broker.place_trade.return_value = _active_trade("SELL")

    with patch(_PATCH_BROKER, return_value=mock_broker):
        result = runner.invoke(
            app, ["sell", "BTCUSDT", "0.001", "--sl", "105000", "--tp", "95000", "--yes"]
        )

    assert result.exit_code == 0
    assert "Trade placed" in result.output


def test_buy_broker_error_exits_nonzero():
    mock_broker = MagicMock()
    mock_broker.get_price.return_value = 100000.0
    mock_broker.get_balance.return_value = {}
    mock_broker.place_trade.side_effect = BrokerError("API down")

    with patch(_PATCH_BROKER, return_value=mock_broker):
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

    with patch(_PATCH_BROKER, return_value=mock_broker):
        result = runner.invoke(app, ["orders"])

    assert result.exit_code == 0


def test_balance_command():
    mock_broker = MagicMock()
    mock_broker.get_balance.return_value = {"BTC": {"free": "0.5", "locked": "0.0"}}

    with patch(_PATCH_BROKER, return_value=mock_broker):
        result = runner.invoke(app, ["balance"])

    assert result.exit_code == 0
    assert "BTC" in result.output


def test_cancel_command():
    mock_broker = MagicMock()
    mock_broker.cancel_order.return_value = {"orderId": 12345, "status": "CANCELED"}

    with patch(_PATCH_BROKER, return_value=mock_broker):
        result = runner.invoke(app, ["cancel", "BTCUSDT", "12345"])

    assert result.exit_code == 0
    mock_broker.cancel_order.assert_called_once_with("BTCUSDT", 12345)


def test_run_command_missing_config_exits_nonzero(tmp_path):
    missing_config = tmp_path / "does-not-exist.yaml"

    result = runner.invoke(app, ["run", "--config", str(missing_config)])

    assert result.exit_code != 0
    assert "Config file not found" in result.output


def test_run_command_calls_live_runner_main(tmp_path):
    config_path = tmp_path / "runner.yaml"
    config_path.write_text("symbols: []\n")

    with patch("trading_bot.runner.live_runner.main") as mock_main:
        result = runner.invoke(app, ["run", "--config", str(config_path), "--dry-run"])

    assert result.exit_code == 0
    mock_main.assert_called_once_with(str(config_path), True)
