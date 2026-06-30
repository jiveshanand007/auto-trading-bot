from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from trading_bot.backtest.simulated_broker import SimulatedBroker
from trading_bot.core.domain.order import Side
from trading_bot.core.domain.trade import TradePlan, TradeStage
from trading_bot.market_data.types import Bar, Timeframe


def _bar(
    close: float,
    open_: float | None = None,
    high: float | None = None,
    low: float | None = None,
    bar_index: int = 0,
) -> Bar:
    o = Decimal(str(open_ if open_ is not None else close))
    c = Decimal(str(close))
    h = Decimal(str(high if high is not None else float(max(o, c)) + 1.0))
    l = Decimal(str(low if low is not None else float(min(o, c)) - 1.0))
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(hours=bar_index)
    return Bar(
        symbol="BTCUSDT", timeframe=Timeframe.H1,
        open_time=t0, close_time=t0 + timedelta(hours=1),
        open=o, high=h, low=l, close=c, volume=Decimal("100"),
    )


def _buy_plan(sl: float = 95.0, tp: float = 110.0, qty: float = 1.0) -> TradePlan:
    return TradePlan(
        symbol="BTCUSDT", side=Side.BUY, quantity=qty,
        initial_stop_loss=sl,
        stages=[TradeStage(take_profit=tp, next_stop_loss=sl)],
    )


def _sell_plan(sl: float = 105.0, tp: float = 90.0, qty: float = 1.0) -> TradePlan:
    return TradePlan(
        symbol="BTCUSDT", side=Side.SELL, quantity=qty,
        initial_stop_loss=sl,
        stages=[TradeStage(take_profit=tp, next_stop_loss=sl)],
    )


# --- fill mechanics ---

def test_place_trade_stays_pending_until_next_bar():
    broker = SimulatedBroker(initial_capital=10000.0, fee_rate=0.0, slippage_rate=0.0)
    broker.place_trade(_buy_plan())
    assert broker.get_positions() == []


def test_pending_entry_fills_at_bar_open():
    broker = SimulatedBroker(initial_capital=10000.0, fee_rate=0.0, slippage_rate=0.0)
    broker.place_trade(_buy_plan(sl=95.0, tp=110.0))
    broker.advance_bar(_bar(open_=100.0, close=101.0, high=101.5, low=99.5, bar_index=0))
    positions = broker.get_positions()
    assert len(positions) == 1
    assert positions[0].entry_price == pytest.approx(100.0)


def test_slippage_applied_to_buy_entry():
    broker = SimulatedBroker(initial_capital=10000.0, fee_rate=0.0, slippage_rate=0.001)
    broker.place_trade(_buy_plan(sl=95.0, tp=110.0))
    broker.advance_bar(_bar(open_=100.0, close=100.0, high=101.0, low=99.0, bar_index=0))
    pos = broker.get_positions()[0]
    assert pos.entry_price == pytest.approx(100.1)


def test_slippage_applied_to_sell_entry():
    broker = SimulatedBroker(initial_capital=10000.0, fee_rate=0.0, slippage_rate=0.001)
    broker.place_trade(_sell_plan(sl=105.0, tp=90.0))
    broker.advance_bar(_bar(open_=100.0, close=100.0, high=101.0, low=99.0, bar_index=0))
    pos = broker.get_positions()[0]
    assert pos.entry_price == pytest.approx(99.9)


# --- SL/TP triggers ---

def test_sl_triggers_for_buy_when_bar_low_hits():
    broker = SimulatedBroker(initial_capital=10000.0, fee_rate=0.0, slippage_rate=0.0)
    broker.place_trade(_buy_plan(sl=95.0, tp=110.0))
    broker.advance_bar(_bar(open_=100.0, close=99.0, high=100.5, low=99.0, bar_index=0))
    broker.advance_bar(_bar(open_=99.0, close=97.0, high=99.0, low=94.0, bar_index=1))
    assert broker.get_positions() == []
    closed = broker.get_closed_trades()
    assert len(closed) == 1
    assert closed[0].exit_price == pytest.approx(95.0)
    assert closed[0].pnl == pytest.approx(-5.0)


def test_tp_triggers_for_buy_when_bar_high_hits():
    broker = SimulatedBroker(initial_capital=10000.0, fee_rate=0.0, slippage_rate=0.0)
    broker.place_trade(_buy_plan(sl=95.0, tp=110.0))
    broker.advance_bar(_bar(open_=100.0, close=105.0, high=105.0, low=99.0, bar_index=0))
    broker.advance_bar(_bar(open_=105.0, close=112.0, high=112.0, low=104.0, bar_index=1))
    assert broker.get_positions() == []
    closed = broker.get_closed_trades()
    assert len(closed) == 1
    assert closed[0].exit_price == pytest.approx(110.0)
    assert closed[0].pnl == pytest.approx(10.0)


def test_sl_triggers_for_sell_when_bar_high_hits():
    broker = SimulatedBroker(initial_capital=10000.0, fee_rate=0.0, slippage_rate=0.0)
    broker.place_trade(_sell_plan(sl=105.0, tp=90.0))
    broker.advance_bar(_bar(open_=100.0, close=99.0, high=100.5, low=99.0, bar_index=0))
    broker.advance_bar(_bar(open_=101.0, close=103.0, high=106.0, low=100.0, bar_index=1))
    assert broker.get_positions() == []
    closed = broker.get_closed_trades()
    assert closed[0].exit_price == pytest.approx(105.0)
    assert closed[0].pnl == pytest.approx(-5.0)


def test_tp_triggers_for_sell_when_bar_low_hits():
    broker = SimulatedBroker(initial_capital=10000.0, fee_rate=0.0, slippage_rate=0.0)
    broker.place_trade(_sell_plan(sl=105.0, tp=90.0))
    broker.advance_bar(_bar(open_=100.0, close=99.0, high=100.5, low=99.0, bar_index=0))
    broker.advance_bar(_bar(open_=98.0, close=91.0, high=98.0, low=88.0, bar_index=1))
    assert broker.get_positions() == []
    closed = broker.get_closed_trades()
    assert closed[0].exit_price == pytest.approx(90.0)
    assert closed[0].pnl == pytest.approx(10.0)


# --- fees ---

def test_entry_fee_reduces_equity():
    broker = SimulatedBroker(initial_capital=10000.0, fee_rate=0.001, slippage_rate=0.0)
    broker.place_trade(_buy_plan(sl=95.0, tp=110.0))
    broker.advance_bar(_bar(open_=100.0, close=100.0, high=101.0, low=99.0, bar_index=0))
    state = broker.portfolio_state()
    assert state.equity == pytest.approx(9999.9)


def test_fee_and_slippage_deducted_on_tp_exit():
    broker = SimulatedBroker(initial_capital=10000.0, fee_rate=0.001, slippage_rate=0.0)
    broker.place_trade(_buy_plan(sl=95.0, tp=110.0))
    broker.advance_bar(_bar(open_=100.0, close=100.0, high=101.0, low=99.0, bar_index=0))
    broker.advance_bar(_bar(open_=108.0, close=112.0, high=112.0, low=107.0, bar_index=1))
    state = broker.portfolio_state()
    assert state.equity == pytest.approx(10009.79)


# --- equity and portfolio state ---

def test_equity_tracks_unrealized_pnl():
    broker = SimulatedBroker(initial_capital=10000.0, fee_rate=0.0, slippage_rate=0.0)
    broker.place_trade(_buy_plan(sl=95.0, tp=200.0))
    broker.advance_bar(_bar(open_=100.0, close=105.0, high=106.0, low=99.0, bar_index=0))
    state = broker.portfolio_state()
    assert state.equity == pytest.approx(10005.0)


def test_portfolio_state_open_positions():
    broker = SimulatedBroker(initial_capital=10000.0, fee_rate=0.0, slippage_rate=0.0)
    broker.place_trade(_buy_plan())
    broker.advance_bar(_bar(open_=100.0, close=100.0, high=101.0, low=99.0, bar_index=0))
    state = broker.portfolio_state()
    assert len(state.open_positions) == 1
    assert state.open_positions[0].symbol == "BTCUSDT"


def test_get_balance_returns_usdt_dict():
    broker = SimulatedBroker(initial_capital=10000.0, fee_rate=0.0, slippage_rate=0.0)
    balance = broker.get_balance()
    assert "USDT" in balance
    assert balance["USDT"]["free"] == pytest.approx(10000.0)


def test_equity_snapshots_recorded_per_bar():
    broker = SimulatedBroker(initial_capital=10000.0, fee_rate=0.0, slippage_rate=0.0)
    broker.advance_bar(_bar(close=100.0, bar_index=0))
    broker.advance_bar(_bar(close=101.0, bar_index=1))
    assert len(broker.get_equity_snapshots()) == 2


def test_close_position_at_current_bar_close():
    broker = SimulatedBroker(initial_capital=10000.0, fee_rate=0.0, slippage_rate=0.0)
    broker.place_trade(_buy_plan(sl=95.0, tp=200.0))
    broker.advance_bar(_bar(open_=100.0, close=105.0, high=106.0, low=99.0, bar_index=0))
    broker.close_position("BTCUSDT")
    state = broker.portfolio_state()
    assert state.equity == pytest.approx(10005.0)
    assert broker.get_positions() == []
