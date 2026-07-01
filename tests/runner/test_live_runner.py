from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trading_bot.market_data.types import Bar, Timeframe
from trading_bot.runner.config import RunnerConfig, StrategyConfig
from trading_bot.runner.live_runner import (
    _DailyEquityTracker,
    _next_bar,
    _portfolio_state_from_broker,
    _process_bar,
    run,
)


def _bar(close: float = 50000.0) -> Bar:
    t = datetime(2024, 1, 1, tzinfo=timezone.utc)
    c = Decimal(str(close))
    return Bar(
        symbol="BTCUSDT", timeframe=Timeframe.H1,
        open_time=t, close_time=t + timedelta(hours=1),
        open=c, high=c + Decimal("100"), low=c - Decimal("100"),
        close=c, volume=Decimal("10"),
    )


def _mock_spot_broker(equity: float = 10_000.0):
    broker = MagicMock()
    broker.get_balance.return_value = {"USDT": {"free": equity, "locked": 0.0}}
    broker.get_positions.return_value = []
    broker.place_trade.return_value = MagicMock(entry_order_id=42)
    return broker


async def test_portfolio_state_equity_from_spot_balance():
    broker = _mock_spot_broker(equity=12_000.0)
    state = await _portfolio_state_from_broker(broker, "BTCUSDT", "spot", _DailyEquityTracker())
    assert state.equity == 12_000.0
    assert state.cash == 12_000.0
    assert state.open_positions == []
    assert not state.is_halted
    broker.get_positions.assert_called_once_with()


async def test_portfolio_state_spot_equity_includes_locked_cash_is_free_only():
    broker = MagicMock()
    broker.get_balance.return_value = {"USDT": {"free": "7000.0", "locked": "3000.0"}}
    broker.get_positions.return_value = []
    state = await _portfolio_state_from_broker(broker, "BTCUSDT", "spot", _DailyEquityTracker())
    assert state.equity == 10_000.0
    assert state.cash == 7_000.0


async def test_portfolio_state_spot_missing_quote_asset_defaults_to_zero():
    broker = MagicMock()
    broker.get_balance.return_value = {"BTC": {"free": "1.0", "locked": "0.0"}}
    broker.get_positions.return_value = []
    state = await _portfolio_state_from_broker(broker, "BTCUSDT", "spot", _DailyEquityTracker())
    assert state.equity == 0.0
    assert state.cash == 0.0


async def test_portfolio_state_futures_balance_parsed_from_account_payload():
    broker = MagicMock()
    broker.get_balance.return_value = {
        "availableBalance": "1000.0",
        "totalMarginBalance": "1100.0",
        "totalUnrealizedProfit": "100.0",
    }
    broker.get_positions.return_value = []
    state = await _portfolio_state_from_broker(broker, "BTCUSDT", "futures", _DailyEquityTracker())
    assert state.equity == 1100.0
    assert state.cash == 1000.0
    broker.get_positions.assert_called_once_with()


async def test_portfolio_state_uses_asyncio_to_thread_for_broker_calls():
    broker = _mock_spot_broker()
    target = "trading_bot.runner.live_runner.asyncio.to_thread"
    with patch(target, new_callable=AsyncMock) as mock_thread:
        mock_thread.side_effect = [broker.get_balance(), broker.get_positions()]
        await _portfolio_state_from_broker(broker, "BTCUSDT", "spot", _DailyEquityTracker())
    assert mock_thread.call_count == 2
    mock_thread.assert_any_call(broker.get_balance)
    mock_thread.assert_any_call(broker.get_positions)


async def test_daily_equity_tracker_same_day_returns_first_call_equity():
    """The tracker must remember the FIRST equity seen on a given UTC day and keep
    returning it regardless of how equity moves afterward within the same day —
    this is what makes the daily-drawdown circuit breaker meaningful."""
    clock_values = iter(
        [
            datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 1, 15, 30, tzinfo=timezone.utc),
            datetime(2024, 1, 1, 23, 59, tzinfo=timezone.utc),
        ]
    )
    tracker = _DailyEquityTracker(now_fn=lambda: next(clock_values))

    first = tracker.start_equity_for(10_000.0)
    second = tracker.start_equity_for(9_000.0)
    third = tracker.start_equity_for(11_000.0)

    assert first == 10_000.0
    assert second == 10_000.0
    assert third == 10_000.0


async def test_daily_equity_tracker_resets_on_utc_day_rollover():
    clock_values = iter(
        [
            datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 2, 0, 5, tzinfo=timezone.utc),
        ]
    )
    tracker = _DailyEquityTracker(now_fn=lambda: next(clock_values))

    day1_start = tracker.start_equity_for(10_000.0)
    day2_start = tracker.start_equity_for(8_000.0)

    assert day1_start == 10_000.0
    assert day2_start == 8_000.0


async def test_portfolio_state_daily_start_equity_stable_across_calls_same_day():
    """Regression test for the dead circuit breaker: two calls in the same day with
    different current equity must report the SAME daily_start_equity (the first
    call's equity), not the current equity each time."""
    tracker = _DailyEquityTracker(now_fn=lambda: datetime(2024, 1, 1, 12, tzinfo=timezone.utc))

    broker1 = _mock_spot_broker(equity=10_000.0)
    state1 = await _portfolio_state_from_broker(broker1, "BTCUSDT", "spot", tracker)

    broker2 = _mock_spot_broker(equity=8_000.0)
    state2 = await _portfolio_state_from_broker(broker2, "BTCUSDT", "spot", tracker)

    assert state1.daily_start_equity == 10_000.0
    assert state1.equity == 10_000.0
    assert state2.daily_start_equity == 10_000.0
    assert state2.equity == 8_000.0


async def test_process_bar_calls_broker_when_signal_approved():
    from trading_bot.core.domain.order import Side
    from trading_bot.core.domain.signal import Signal
    from trading_bot.risk.manager import RiskManager

    bar = _bar(50000.0)
    broker = _mock_spot_broker()
    risk = RiskManager()

    strategy = MagicMock()
    strategy.on_bar.return_value = Signal(
        symbol="BTCUSDT", side=Side.BUY, quantity=0.001,
        entry_price=50000.0, stop_loss=49000.0, take_profit=52000.0,
        reason="test",
    )

    target = "trading_bot.runner.live_runner.asyncio.to_thread"
    with patch(target, new_callable=AsyncMock) as mock_thread:
        mock_thread.side_effect = [
            broker.get_balance(), broker.get_positions(), MagicMock(entry_order_id=1),
        ]
        await _process_bar(
            bar, strategy, risk, broker, dry_run=False, market="spot",
            daily_tracker=_DailyEquityTracker(),
        )

    assert mock_thread.call_count == 3


async def test_process_bar_skips_broker_on_no_signal():
    from trading_bot.risk.manager import RiskManager

    bar = _bar()
    broker = _mock_spot_broker()
    risk = RiskManager()
    strategy = MagicMock()
    strategy.on_bar.return_value = None

    target = "trading_bot.runner.live_runner.asyncio.to_thread"
    with patch(target, new_callable=AsyncMock) as mock_thread:
        mock_thread.side_effect = [broker.get_balance(), broker.get_positions()]
        await _process_bar(
            bar, strategy, risk, broker, dry_run=False, market="spot",
            daily_tracker=_DailyEquityTracker(),
        )

    # only the two portfolio-state lookups, no place_trade call
    assert mock_thread.call_count == 2


async def test_process_bar_dry_run_skips_broker():
    from trading_bot.core.domain.order import Side
    from trading_bot.core.domain.signal import Signal
    from trading_bot.risk.manager import RiskManager

    bar = _bar(50000.0)
    broker = _mock_spot_broker()
    risk = RiskManager()
    strategy = MagicMock()
    strategy.on_bar.return_value = Signal(
        symbol="BTCUSDT", side=Side.BUY, quantity=0.001,
        entry_price=50000.0, stop_loss=49000.0, take_profit=52000.0,
        reason="test",
    )

    target = "trading_bot.runner.live_runner.asyncio.to_thread"
    with patch(target, new_callable=AsyncMock) as mock_thread:
        mock_thread.side_effect = [broker.get_balance(), broker.get_positions()]
        await _process_bar(
            bar, strategy, risk, broker, dry_run=True, market="spot",
            daily_tracker=_DailyEquityTracker(),
        )

    # only the two portfolio-state lookups, no place_trade call
    assert mock_thread.call_count == 2


async def test_run_fault_isolation_one_symbol_failure_does_not_stop_others():
    """Exercises live_runner.run()'s actual gather(..., return_exceptions=True) wiring:
    one _run_symbol coroutine raises, the other completes, and run() itself must not
    raise while still recording the failure via log.error("task_failed", ...).
    """
    cfg = RunnerConfig(
        strategies=[
            StrategyConfig(
                strategy="ma-crossover", symbol="BTCUSDT", timeframe="H1", market="spot",
            ),
            StrategyConfig(
                strategy="ma-crossover", symbol="ETHUSDT", timeframe="H1", market="spot",
            ),
        ]
    )

    completed_symbols: list[str] = []

    async def fake_run_symbol(strategy_cfg, runner_cfg, risk, daily_tracker, ws_client, dry_run):
        await asyncio.sleep(0)
        if strategy_cfg.symbol == "BTCUSDT":
            raise RuntimeError("intentional failure")
        completed_symbols.append(strategy_cfg.symbol)

    fake_ws_client = MagicMock()
    fake_ws_client.close_connection = AsyncMock()

    with (
        patch("trading_bot.runner.live_runner.load_config", return_value=cfg),
        patch("trading_bot.runner.live_runner.configure_logging"),
        patch(
            "trading_bot.runner.live_runner.AsyncClient.create",
            new=AsyncMock(return_value=fake_ws_client),
        ),
        patch(
            "trading_bot.runner.live_runner._run_symbol",
            side_effect=fake_run_symbol,
        ),
        patch("trading_bot.runner.live_runner.log") as mock_log,
    ):
        await run("dummy-config.yaml", dry_run=True)

    assert completed_symbols == ["ETHUSDT"]
    failure_calls = [
        c for c in mock_log.error.call_args_list
        if c.args[:1] == ("task_failed",)
    ]
    assert len(failure_calls) == 1
    assert failure_calls[0].kwargs["task"] == "ma-crossover:BTCUSDT"
    assert "intentional failure" in failure_calls[0].kwargs["error"]


async def test_next_bar_returns_bar_from_queue_while_feed_task_still_running():
    queue: asyncio.Queue[Bar] = asyncio.Queue()
    bar = _bar()
    await queue.put(bar)
    feed_task = asyncio.create_task(asyncio.sleep(3600))

    try:
        result = await _next_bar(queue, feed_task, "BTCUSDT")
    finally:
        feed_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await feed_task

    assert result is bar


async def test_next_bar_raises_when_feed_task_ends_normally_before_next_bar():
    """Covers Finding 2a: a feed that ends cleanly (e.g. socket closed) must not
    leave the consumer awaiting queue.get() forever — it must raise instead."""
    queue: asyncio.Queue[Bar] = asyncio.Queue()

    async def _ends_cleanly():
        return None

    feed_task = asyncio.create_task(_ends_cleanly())
    await asyncio.sleep(0)  # let feed_task actually finish

    with pytest.raises(RuntimeError, match="ended unexpectedly"):
        await _next_bar(queue, feed_task, "BTCUSDT")


async def test_next_bar_reraises_feed_task_exception_before_next_bar():
    """Covers Finding 2b: a feed that dies with an exception (e.g. malformed
    kline crashing the socket handling) must surface that exception through the
    consumer rather than leaving it unretrieved while queue.get() hangs."""
    queue: asyncio.Queue[Bar] = asyncio.Queue()

    async def _boom():
        raise ValueError("feed exploded")

    feed_task = asyncio.create_task(_boom())
    with contextlib.suppress(ValueError):
        await feed_task  # let it finish so .exception() is populated

    with pytest.raises(ValueError, match="feed exploded"):
        await _next_bar(queue, feed_task, "BTCUSDT")
