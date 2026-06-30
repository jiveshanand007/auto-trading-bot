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


def test_futures_advance_success():
    """advance command calls broker.advance_stage and updates _active_trades."""
    import trading_bot.cli.futures_cli as futures_module

    # Build a multi-stage trade so has_next_stage is True
    plan = TradePlan(
        symbol="BTCUSDT", side=Side.BUY, quantity=0.001,
        initial_stop_loss=95000.0,
        stages=[
            TradeStage(take_profit=102000.0, next_stop_loss=99000.0),
            TradeStage(take_profit=108000.0, next_stop_loss=104000.0),
        ],
        leverage=5,
    )
    multistage_trade = ActiveTrade(
        plan=plan, current_stage=0, entry_order_id=1, entry_price=100000.0,
        current_sl_order_id=2, current_tp_order_id=3, status=TradeStatus.OPEN,
    )
    advanced_trade = ActiveTrade(
        plan=plan, current_stage=1, entry_order_id=1, entry_price=100000.0,
        current_sl_order_id=4, current_tp_order_id=5, status=TradeStatus.OPEN,
    )

    mock_broker = MagicMock()
    mock_broker.advance_stage.return_value = advanced_trade

    with (
        patch(_PATCH, return_value=mock_broker),
        patch.object(futures_module, "_active_trades", {"BTCUSDT": multistage_trade}),
    ):
        result = runner.invoke(app, ["futures", "advance", "BTCUSDT"])

    assert result.exit_code == 0
    mock_broker.advance_stage.assert_called_once_with(multistage_trade)


def test_futures_advance_no_active_trade():
    """advance command exits with error when no active trade exists for symbol."""
    import trading_bot.cli.futures_cli as futures_module

    mock_broker = MagicMock()
    with (
        patch(_PATCH, return_value=mock_broker),
        patch.object(futures_module, "_active_trades", {}),
    ):
        result = runner.invoke(app, ["futures", "advance", "ETHUSDT"])

    assert result.exit_code != 0


def test_futures_advance_final_stage():
    """advance command exits with error when trade is already at the final stage."""
    import trading_bot.cli.futures_cli as futures_module

    # Single-stage trade — has_next_stage is False
    single_stage_trade = _active_trade()

    mock_broker = MagicMock()
    with (
        patch(_PATCH, return_value=mock_broker),
        patch.object(futures_module, "_active_trades", {"BTCUSDT": single_stage_trade}),
    ):
        result = runner.invoke(app, ["futures", "advance", "BTCUSDT"])

    assert result.exit_code != 0
    mock_broker.advance_stage.assert_not_called()


def test_futures_move_sl_success():
    """move-sl command calls broker.update_stop_loss and updates _active_trades."""
    import trading_bot.cli.futures_cli as futures_module

    trade = _active_trade()
    updated_trade = ActiveTrade(
        plan=trade.plan, current_stage=0, entry_order_id=1, entry_price=100000.0,
        current_sl_order_id=10, current_tp_order_id=3, status=TradeStatus.OPEN,
    )

    mock_broker = MagicMock()
    mock_broker.update_stop_loss.return_value = updated_trade

    with (
        patch(_PATCH, return_value=mock_broker),
        patch.object(futures_module, "_active_trades", {"BTCUSDT": trade}),
    ):
        result = runner.invoke(app, ["futures", "move-sl", "BTCUSDT", "97000"])

    assert result.exit_code == 0
    mock_broker.update_stop_loss.assert_called_once_with(trade, 97000.0)


def test_futures_move_sl_no_active_trade():
    """move-sl command exits with error when no active trade exists for symbol."""
    import trading_bot.cli.futures_cli as futures_module

    mock_broker = MagicMock()
    with (
        patch(_PATCH, return_value=mock_broker),
        patch.object(futures_module, "_active_trades", {}),
    ):
        result = runner.invoke(app, ["futures", "move-sl", "ETHUSDT", "1500"])

    assert result.exit_code != 0


def test_futures_buy_stores_active_trade():
    """buy command stores result in _active_trades under the uppercased symbol."""
    import trading_bot.cli.futures_cli as futures_module

    trade = _active_trade()
    mock_broker = MagicMock()
    mock_broker.get_price.return_value = 100000.0
    mock_broker.get_balance.return_value = {}
    mock_broker.place_trade.return_value = trade

    active_trades: dict = {}
    with (
        patch(_PATCH, return_value=mock_broker),
        patch.object(futures_module, "_active_trades", active_trades),
    ):
        result = runner.invoke(
            app,
            ["futures", "buy", "BTCUSDT", "0.001", "--sl", "95000", "--tp", "105000", "--yes"],
        )

    assert result.exit_code == 0
    assert active_trades.get("BTCUSDT") is trade


def test_futures_close_removes_active_trade():
    """close command removes the symbol from _active_trades after success."""
    import trading_bot.cli.futures_cli as futures_module

    trade = _active_trade()
    mock_broker = MagicMock()
    mock_broker.close_position.return_value = {"status": "CLOSED"}

    active_trades: dict = {"BTCUSDT": trade}
    with (
        patch(_PATCH, return_value=mock_broker),
        patch.object(futures_module, "_active_trades", active_trades),
    ):
        result = runner.invoke(app, ["futures", "close", "BTCUSDT"])

    assert result.exit_code == 0
    assert "BTCUSDT" not in active_trades
