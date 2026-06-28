# tests/cli/test_futures_cli.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from trading_bot.cli.trade_cli import app
from trading_bot.core.domain.order import MarginType, Side
from trading_bot.core.domain.position import Position
from trading_bot.core.domain.trade import ActiveTrade, TradePlan, TradeStage, TradeStatus

runner = CliRunner()
_PATCH = "trading_bot.cli.futures_cli.make_futures_broker"


def _active_trade() -> ActiveTrade:
    plan = TradePlan(
        symbol="BTCUSDT", side=Side.BUY, quantity=0.001,
        initial_stop_loss=95000.0,
        stages=[TradeStage(take_profit=105000.0, next_stop_loss=100000.0)],
        leverage=5,
    )
    return ActiveTrade(
        plan=plan, current_stage=0, entry_order_id=1, entry_price=100000.0,
        current_sl_order_id=2, current_tp_order_id=3, status=TradeStatus.OPEN,
    )


def test_futures_buy_success():
    mock_broker = MagicMock()
    mock_broker.get_price.return_value = 100000.0
    mock_broker.get_balance.return_value = {}
    mock_broker.place_trade.return_value = _active_trade()

    with patch(_PATCH, return_value=mock_broker):
        result = runner.invoke(
            app,
            ["futures", "buy", "BTCUSDT", "0.001", "--sl", "95000", "--tp", "105000", "--yes"],
        )
    assert result.exit_code == 0
    mock_broker.place_trade.assert_called_once()


def test_futures_sell_success():
    mock_broker = MagicMock()
    mock_broker.get_price.return_value = 100000.0
    mock_broker.get_balance.return_value = {}
    mock_broker.place_trade.return_value = _active_trade()

    with patch(_PATCH, return_value=mock_broker):
        result = runner.invoke(
            app,
            ["futures", "sell", "BTCUSDT", "0.001", "--sl", "105000", "--tp", "95000", "--yes"],
        )
    assert result.exit_code == 0


def test_futures_positions_command():
    mock_broker = MagicMock()
    mock_broker.get_positions.return_value = [
        Position("BTCUSDT", Side.BUY, 0.001, 100000.0, 5, 80000.0, 50.0, MarginType.ISOLATED)
    ]

    with patch(_PATCH, return_value=mock_broker):
        result = runner.invoke(app, ["futures", "positions"])
    assert result.exit_code == 0


def test_futures_balance_command():
    mock_broker = MagicMock()
    mock_broker.get_balance.return_value = {"availableBalance": "1000.0"}

    with patch(_PATCH, return_value=mock_broker):
        result = runner.invoke(app, ["futures", "balance"])
    assert result.exit_code == 0


def test_futures_multistage_buy():
    mock_broker = MagicMock()
    mock_broker.get_price.return_value = 100000.0
    mock_broker.get_balance.return_value = {}
    mock_broker.place_trade.return_value = _active_trade()

    with patch(_PATCH, return_value=mock_broker):
        result = runner.invoke(
            app,
            [
                "futures", "buy", "BTCUSDT", "0.001",
                "--sl", "95000",
                "--tp", "102000", "--next-sl", "99000",
                "--tp", "108000", "--next-sl", "104000",
                "--tp", "115000",
                "--yes",
            ],
        )
    assert result.exit_code == 0
    call_plan = mock_broker.place_trade.call_args[0][0]
    assert len(call_plan.stages) == 3
