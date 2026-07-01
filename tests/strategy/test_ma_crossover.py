from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from trading_bot.core.domain.order import Side
from trading_bot.core.domain.portfolio import PortfolioState
from trading_bot.market_data.types import Bar, Timeframe
from trading_bot.strategy.ma_crossover import MACrossoverStrategy


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
    strat = MACrossoverStrategy(fast=3, slow=5)
    state = _state()
    signals = [strat.on_bar(_bar(close=100.0 + i, bar_index=i), state) for i in range(5)]
    assert all(s is None for s in signals)


def test_no_signal_without_crossover():
    strat = MACrossoverStrategy(fast=3, slow=5)
    state = _state()
    last_sig = None
    for i in range(12):
        last_sig = strat.on_bar(_bar(close=100.0 + i, bar_index=i), state)
    assert last_sig is None


def test_buy_signal_on_bullish_crossover():
    strat = MACrossoverStrategy(fast=3, slow=5)
    state = _state()
    prices = [110.0, 105.0, 100.0, 95.0, 90.0, 85.0, 130.0]
    last_sig = None
    for i, p in enumerate(prices):
        sig = strat.on_bar(_bar(close=p, bar_index=i), state)
        if sig is not None:
            last_sig = sig
    assert last_sig is not None
    assert last_sig.side == Side.BUY
    assert last_sig.stop_loss < last_sig.entry_price < last_sig.take_profit


def test_sell_signal_on_bearish_crossover():
    strat = MACrossoverStrategy(fast=3, slow=5)
    state = _state()
    prices = [85.0, 90.0, 95.0, 100.0, 105.0, 110.0, 70.0]
    last_sig = None
    for i, p in enumerate(prices):
        sig = strat.on_bar(_bar(close=p, bar_index=i), state)
        if sig is not None:
            last_sig = sig
    assert last_sig is not None
    assert last_sig.side == Side.SELL
    assert last_sig.take_profit < last_sig.entry_price < last_sig.stop_loss


def test_sl_tp_proportions_for_buy():
    strat = MACrossoverStrategy(fast=3, slow=5)
    state = _state()
    prices = [110.0, 105.0, 100.0, 95.0, 90.0, 85.0, 130.0]
    sig = None
    for i, p in enumerate(prices):
        result = strat.on_bar(_bar(close=p, bar_index=i), state)
        if result is not None:
            sig = result
    assert sig is not None
    assert sig.stop_loss == pytest.approx(sig.entry_price * 0.98)
    assert sig.take_profit == pytest.approx(sig.entry_price * 1.04)


def test_sl_tp_proportions_for_sell():
    strat = MACrossoverStrategy(fast=3, slow=5)
    state = _state()
    prices = [85.0, 90.0, 95.0, 100.0, 105.0, 110.0, 70.0]
    sig = None
    for i, p in enumerate(prices):
        result = strat.on_bar(_bar(close=p, bar_index=i), state)
        if result is not None:
            sig = result
    assert sig is not None
    assert sig.stop_loss == pytest.approx(sig.entry_price * 1.02)
    assert sig.take_profit == pytest.approx(sig.entry_price * 0.96)


def test_strategy_name_contains_periods():
    strat = MACrossoverStrategy(fast=9, slow=21)
    name = strat.name()
    assert "ma-crossover" in name
    assert "9" in name
    assert "21" in name
