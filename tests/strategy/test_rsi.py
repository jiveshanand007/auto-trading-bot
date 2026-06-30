from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from trading_bot.core.domain.order import Side
from trading_bot.core.domain.portfolio import PortfolioState
from trading_bot.market_data.types import Bar, Timeframe
from trading_bot.strategy.rsi import RSIStrategy


def _bar(close: float, bar_index: int = 0) -> Bar:
    c = Decimal(str(close))
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(hours=bar_index)
    return Bar(
        symbol="BTCUSDT", timeframe=Timeframe.H1,
        open_time=t0, close_time=t0 + timedelta(hours=1),
        open=c, high=c + Decimal("1"), low=c - Decimal("1"),
        close=c, volume=Decimal("100"),
    )


def _state() -> PortfolioState:
    return PortfolioState(
        equity=10000.0, cash=10000.0, open_positions=[],
        daily_start_equity=10000.0, is_halted=False,
    )


def test_no_signal_during_warmup():
    strat = RSIStrategy(period=14)
    state = _state()
    signals = [strat.on_bar(_bar(close=100.0 - i, bar_index=i), state) for i in range(14)]
    assert all(s is None for s in signals)


def test_no_signal_at_first_computable_bar():
    strat = RSIStrategy(period=14)
    state = _state()
    signals = [strat.on_bar(_bar(close=100.0 - i, bar_index=i), state) for i in range(15)]
    assert all(s is None for s in signals)


def test_buy_signal_when_rsi_crosses_above_oversold():
    strat = RSIStrategy(period=14, oversold=30.0)
    state = _state()
    for i in range(15):
        strat.on_bar(_bar(close=100.0 - i, bar_index=i), state)
    sig = strat.on_bar(_bar(close=92.0, bar_index=15), state)
    assert sig is not None
    assert sig.side == Side.BUY
    assert sig.stop_loss < sig.entry_price < sig.take_profit


def test_sell_signal_when_rsi_crosses_below_overbought():
    strat = RSIStrategy(period=14, overbought=70.0)
    state = _state()
    for i in range(15):
        strat.on_bar(_bar(close=100.0 + i, bar_index=i), state)
    sig = strat.on_bar(_bar(close=107.0, bar_index=15), state)
    assert sig is not None
    assert sig.side == Side.SELL
    assert sig.take_profit < sig.entry_price < sig.stop_loss


def test_sl_tp_proportions_for_buy():
    strat = RSIStrategy(period=14, oversold=30.0)
    state = _state()
    for i in range(15):
        strat.on_bar(_bar(close=100.0 - i, bar_index=i), state)
    sig = strat.on_bar(_bar(close=92.0, bar_index=15), state)
    assert sig is not None
    assert sig.stop_loss == pytest.approx(sig.entry_price * 0.98)
    assert sig.take_profit == pytest.approx(sig.entry_price * 1.04)


def test_strategy_name_contains_period():
    strat = RSIStrategy(period=14)
    assert "rsi" in strat.name()
    assert "14" in strat.name()
