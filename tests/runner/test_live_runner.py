from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from trading_bot.market_data.types import Bar, Timeframe
from trading_bot.runner.live_runner import _portfolio_state_from_broker, _process_bar


def _bar(close: float = 50000.0) -> Bar:
    t = datetime(2024, 1, 1, tzinfo=timezone.utc)
    c = Decimal(str(close))
    return Bar(
        symbol="BTCUSDT", timeframe=Timeframe.H1,
        open_time=t, close_time=t + timedelta(hours=1),
        open=c, high=c + Decimal("100"), low=c - Decimal("100"),
        close=c, volume=Decimal("10"),
    )


def _mock_broker(equity: float = 10_000.0):
    broker = MagicMock()
    broker.get_balance.return_value = {"USDT": {"free": equity, "locked": 0.0}}
    broker.get_positions.return_value = []
    broker.place_trade.return_value = MagicMock(entry_order_id=42)
    return broker


def test_portfolio_state_equity_from_balance():
    broker = _mock_broker(equity=12_000.0)
    state = _portfolio_state_from_broker(broker, "BTCUSDT")
    assert state.equity == 12_000.0
    assert state.cash == 12_000.0
    assert state.open_positions == []
    assert not state.is_halted


async def test_process_bar_calls_broker_when_signal_approved():
    from trading_bot.core.domain.order import Side
    from trading_bot.core.domain.signal import Signal
    from trading_bot.risk.manager import RiskManager

    bar = _bar(50000.0)
    broker = _mock_broker()
    risk = RiskManager()

    strategy = MagicMock()
    strategy.on_bar.return_value = Signal(
        symbol="BTCUSDT", side=Side.BUY, quantity=0.001,
        entry_price=50000.0, stop_loss=49000.0, take_profit=52000.0,
        reason="test",
    )

    target = "trading_bot.runner.live_runner.asyncio.to_thread"
    with patch(target, new_callable=AsyncMock) as mock_thread:
        mock_thread.return_value = MagicMock(entry_order_id=1)
        await _process_bar(bar, strategy, risk, broker, dry_run=False)

    mock_thread.assert_called_once()


async def test_process_bar_skips_broker_on_no_signal():
    from trading_bot.risk.manager import RiskManager

    bar = _bar()
    broker = _mock_broker()
    risk = RiskManager()
    strategy = MagicMock()
    strategy.on_bar.return_value = None

    target = "trading_bot.runner.live_runner.asyncio.to_thread"
    with patch(target, new_callable=AsyncMock) as mock_thread:
        await _process_bar(bar, strategy, risk, broker, dry_run=False)

    mock_thread.assert_not_called()


async def test_process_bar_dry_run_skips_broker():
    from trading_bot.core.domain.order import Side
    from trading_bot.core.domain.signal import Signal
    from trading_bot.risk.manager import RiskManager

    bar = _bar(50000.0)
    broker = _mock_broker()
    risk = RiskManager()
    strategy = MagicMock()
    strategy.on_bar.return_value = Signal(
        symbol="BTCUSDT", side=Side.BUY, quantity=0.001,
        entry_price=50000.0, stop_loss=49000.0, take_profit=52000.0,
        reason="test",
    )

    target = "trading_bot.runner.live_runner.asyncio.to_thread"
    with patch(target, new_callable=AsyncMock) as mock_thread:
        await _process_bar(bar, strategy, risk, broker, dry_run=True)

    mock_thread.assert_not_called()


async def test_fault_isolation_one_task_failure_does_not_cancel_others():
    completed = []

    async def _good_task():
        await asyncio.sleep(0)
        completed.append("good")

    async def _bad_task():
        raise RuntimeError("intentional failure")

    results = await asyncio.gather(
        _good_task(), _bad_task(), return_exceptions=True
    )
    assert "good" in completed
    assert isinstance(results[1], RuntimeError)
