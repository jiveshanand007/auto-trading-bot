from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from trading_bot.backtest.engine import run_backtest, signal_to_plan
from trading_bot.backtest.result import BacktestResult
from trading_bot.backtest.simulated_broker import SimulatedBroker
from trading_bot.core.domain.order import Side
from trading_bot.core.domain.portfolio import PortfolioState
from trading_bot.core.domain.signal import Signal
from trading_bot.market_data.types import Bar, Timeframe


def _bar(close: float, open_: float | None = None, bar_index: int = 0) -> Bar:
    o = Decimal(str(open_ if open_ is not None else close))
    c = Decimal(str(close))
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(hours=bar_index)
    return Bar(
        symbol="BTCUSDT", timeframe=Timeframe.H1,
        open_time=t0, close_time=t0 + timedelta(hours=1),
        open=o, high=c + Decimal("1"), low=c - Decimal("1"),
        close=c, volume=Decimal("100"),
    )


def _make_bars(n: int, start: float = 100.0) -> list[Bar]:
    return [_bar(close=start + i * 0.5, bar_index=i) for i in range(n)]


class _NoSignalStrategy:
    def on_bar(self, bar: Bar, portfolio: PortfolioState) -> Signal | None:
        return None

    def name(self) -> str:
        return "no-signal"


class _AlwaysApproveRisk:
    def validate(self, signal: Signal, state: PortfolioState) -> Signal | None:
        return signal


class _AlwaysRejectRisk:
    def validate(self, signal: Signal, state: PortfolioState) -> Signal | None:
        return None


class _BuyOnBar3Strategy:
    def __init__(self) -> None:
        self._count = 0

    def on_bar(self, bar: Bar, portfolio: PortfolioState) -> Signal | None:
        self._count += 1
        if self._count == 3:
            entry = float(bar.close)
            return Signal(
                symbol=bar.symbol, side=Side.BUY, quantity=0.001,
                entry_price=entry, stop_loss=entry * 0.9, take_profit=entry * 1.5,
                reason="bar3",
            )
        return None

    def name(self) -> str:
        return "buy-on-bar3"


# --- signal_to_plan ---

def test_signal_to_plan_buy():
    sig = Signal(
        symbol="BTCUSDT", side=Side.BUY, quantity=0.001,
        entry_price=100.0, stop_loss=98.0, take_profit=104.0, reason="test",
    )
    plan = signal_to_plan(sig)
    assert plan.symbol == "BTCUSDT"
    assert plan.side == Side.BUY
    assert plan.quantity == 0.001
    assert plan.initial_stop_loss == 98.0
    assert plan.stages[0].take_profit == 104.0
    assert plan.stages[0].next_stop_loss == 98.0
    assert plan.leverage == 1


def test_signal_to_plan_sell():
    sig = Signal(
        symbol="ETHUSDT", side=Side.SELL, quantity=0.01,
        entry_price=2000.0, stop_loss=2040.0, take_profit=1960.0, reason="test",
    )
    plan = signal_to_plan(sig)
    assert plan.side == Side.SELL
    assert plan.initial_stop_loss == 2040.0
    assert plan.stages[0].take_profit == 1960.0


# --- run_backtest ---

def test_run_backtest_returns_backtest_result():
    result = run_backtest(
        strategy=_NoSignalStrategy(),
        risk=_AlwaysApproveRisk(),
        broker=SimulatedBroker(initial_capital=10000.0),
        bars=_make_bars(10),
    )
    assert isinstance(result, BacktestResult)
    assert result.strategy_name == "no-signal"
    assert result.initial_capital == 10000.0
    assert len(result.equity_curve) == 10


def test_run_backtest_no_trades_when_no_signals():
    result = run_backtest(
        strategy=_NoSignalStrategy(),
        risk=_AlwaysApproveRisk(),
        broker=SimulatedBroker(initial_capital=10000.0),
        bars=_make_bars(10),
    )
    assert result.trades == []


def test_run_backtest_no_trades_when_risk_rejects_all():
    class _AlwaysBuyStrategy:
        def on_bar(self, bar: Bar, portfolio: PortfolioState) -> Signal | None:
            entry = float(bar.close)
            return Signal(
                symbol=bar.symbol, side=Side.BUY, quantity=0.001,
                entry_price=entry, stop_loss=entry * 0.9, take_profit=entry * 1.1,
                reason="always",
            )

        def name(self) -> str:
            return "always-buy"

    result = run_backtest(
        strategy=_AlwaysBuyStrategy(),
        risk=_AlwaysRejectRisk(),
        broker=SimulatedBroker(initial_capital=10000.0),
        bars=_make_bars(10),
    )
    assert result.trades == []


def test_run_backtest_determinism():
    bars = _make_bars(30)

    def _run() -> list[float]:
        return list(run_backtest(
            strategy=_BuyOnBar3Strategy(),
            risk=_AlwaysApproveRisk(),
            broker=SimulatedBroker(initial_capital=10000.0, fee_rate=0.001, slippage_rate=0.0005),
            bars=bars,
        ).equity_curve.values)

    assert _run() == pytest.approx(_run())
