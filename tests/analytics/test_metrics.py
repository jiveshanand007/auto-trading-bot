from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
from rich.table import Table

from trading_bot.analytics.metrics import AnalyticsResult, compare_strategies, compute_metrics
from trading_bot.backtest.result import BacktestResult, ClosedTrade
from trading_bot.core.domain.order import Side


def _ts(hour: int) -> datetime:
    return datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(hours=hour)


def _result(
    *,
    initial: float = 10_000.0,
    equities: list[float],
    trades: list[ClosedTrade] | None = None,
    use_datetime_index: bool = True,
) -> BacktestResult:
    n = len(equities)
    idx = pd.DatetimeIndex([_ts(i) for i in range(n)]) if use_datetime_index else list(range(n))
    eq = pd.Series(equities, index=idx, name="equity")
    return BacktestResult(
        strategy_name="test-strat",
        symbol="BTCUSDT",
        initial_capital=initial,
        trades=trades or [],
        equity_curve=eq,
    )


def _win(pnl: float, entry: int = 0, exit_: int = 1) -> ClosedTrade:
    return ClosedTrade(
        symbol="BTCUSDT", side=Side.BUY,
        entry_price=100.0, exit_price=100.0 + pnl,
        quantity=1.0, pnl=pnl,
        entry_bar_index=entry, exit_bar_index=exit_,
    )


# ---------------------------------------------------------------------------
# total_return_pct
# ---------------------------------------------------------------------------

def test_total_return_pct_gain():
    r = _result(initial=10_000.0, equities=[10_000.0, 11_000.0])
    m = compute_metrics(r)
    assert m.total_return_pct == pytest.approx(10.0)


def test_total_return_pct_loss():
    r = _result(initial=10_000.0, equities=[10_000.0, 9_000.0])
    m = compute_metrics(r)
    assert m.total_return_pct == pytest.approx(-10.0)


def test_total_return_pct_flat():
    r = _result(initial=10_000.0, equities=[10_000.0, 10_000.0])
    m = compute_metrics(r)
    assert m.total_return_pct == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# win_rate + trade counts
# ---------------------------------------------------------------------------

def test_win_rate_two_wins_one_loss():
    trades = [_win(100.0), _win(50.0), _win(-30.0)]
    r = _result(equities=[10_000.0, 10_100.0, 10_150.0, 10_120.0], trades=trades)
    m = compute_metrics(r)
    assert m.win_rate_pct == pytest.approx(200.0 / 3.0)
    assert m.total_trades == 3


def test_win_rate_no_trades():
    r = _result(equities=[10_000.0, 10_000.0])
    m = compute_metrics(r)
    assert m.win_rate_pct == pytest.approx(0.0)
    assert m.total_trades == 0


# ---------------------------------------------------------------------------
# profit_factor
# ---------------------------------------------------------------------------

def test_profit_factor_normal():
    trades = [_win(200.0), _win(-100.0)]
    r = _result(equities=[10_000.0] * 3, trades=trades)
    m = compute_metrics(r)
    assert m.profit_factor == pytest.approx(2.0)


def test_profit_factor_no_losses_is_inf():
    trades = [_win(100.0), _win(50.0)]
    r = _result(equities=[10_000.0] * 3, trades=trades)
    m = compute_metrics(r)
    assert math.isinf(m.profit_factor)


# ---------------------------------------------------------------------------
# avg_win / avg_loss
# ---------------------------------------------------------------------------

def test_avg_win_avg_loss():
    trades = [_win(100.0), _win(200.0), _win(-50.0), _win(-150.0)]
    r = _result(equities=[10_000.0] * 5, trades=trades)
    m = compute_metrics(r)
    assert m.avg_win == pytest.approx(150.0)
    assert m.avg_loss == pytest.approx(-100.0)


# ---------------------------------------------------------------------------
# max drawdown
# ---------------------------------------------------------------------------

def test_max_drawdown():
    # 10000 → 11000 → 9000 → DD = (11000-9000)/11000 ≈ 18.18%
    r = _result(initial=10_000.0, equities=[10_000.0, 11_000.0, 9_000.0])
    m = compute_metrics(r)
    expected_dd = (11_000.0 - 9_000.0) / 11_000.0 * 100.0
    assert m.max_drawdown_pct == pytest.approx(expected_dd, rel=1e-3)


def test_max_drawdown_no_drawdown():
    r = _result(initial=10_000.0, equities=[10_000.0, 10_500.0, 11_000.0])
    m = compute_metrics(r)
    assert m.max_drawdown_pct == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# exposure_pct
# ---------------------------------------------------------------------------

def test_exposure_pct():
    # 10 bars, 1 trade from bar 2 to bar 4 → 3 bars exposed → 30%
    equities = [10_000.0] * 10
    trades = [ClosedTrade(
        symbol="BTCUSDT", side=Side.BUY,
        entry_price=100.0, exit_price=105.0,
        quantity=1.0, pnl=5.0,
        entry_bar_index=2, exit_bar_index=4,
    )]
    r = _result(equities=equities, trades=trades)
    m = compute_metrics(r)
    assert m.exposure_pct == pytest.approx(30.0)


def test_exposure_pct_no_trades():
    r = _result(equities=[10_000.0] * 5)
    m = compute_metrics(r)
    assert m.exposure_pct == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# sharpe / sortino direction
# ---------------------------------------------------------------------------

def test_sharpe_positive_for_rising_equity():
    equities = [10_000.0 * (1.001 ** i) for i in range(50)]
    r = _result(equities=equities)
    m = compute_metrics(r)
    assert m.sharpe > 0


def test_sharpe_zero_for_flat_equity():
    r = _result(equities=[10_000.0] * 20)
    m = compute_metrics(r)
    assert m.sharpe == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# compare_strategies
# ---------------------------------------------------------------------------

def _analytics(name: str, sharpe: float) -> AnalyticsResult:
    return AnalyticsResult(
        strategy_name=name, total_return_pct=0.0, cagr=0.0,
        sharpe=sharpe, sortino=0.0, max_drawdown_pct=0.0,
        win_rate_pct=0.0, profit_factor=1.0, avg_win=0.0, avg_loss=0.0,
        total_trades=0, exposure_pct=0.0,
        equity_curve=pd.Series([], dtype=float),
    )


def test_compare_strategies_returns_rich_table():
    table = compare_strategies([_analytics("a", 1.0)])
    assert isinstance(table, Table)


def test_compare_strategies_sorted_by_sharpe_descending():
    metrics = [_analytics("low", 0.5), _analytics("high", 2.0), _analytics("mid", 1.0)]
    table = compare_strategies(metrics)
    # Rich stores cells per column; column 0 is the strategy name
    names = [str(cell) for cell in table.columns[0]._cells]
    assert names == ["high", "mid", "low"]
