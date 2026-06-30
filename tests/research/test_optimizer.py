from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from trading_bot.market_data.types import Bar, Timeframe
from trading_bot.research.optimizer import (
    OptimizationResult,
    SplitResult,
    grid_search,
    optimize,
    train_test_split,
)
from trading_bot.strategy.ma_crossover import MACrossoverStrategy
from trading_bot.strategy.rsi import RSIStrategy


def _bar(close: float, i: int) -> Bar:
    c = Decimal(str(close))
    t = datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i)
    return Bar(
        symbol="BTCUSDT", timeframe=Timeframe.H1,
        open_time=t, close_time=t + timedelta(hours=1),
        open=c, high=c + Decimal("2"), low=c - Decimal("2"),
        close=c, volume=Decimal("10"),
    )


def _trending_bars(n: int = 200) -> list[Bar]:
    """Bars with uptrend then downtrend — enough for MA/RSI signals."""
    prices = [100.0 + i * 0.5 for i in range(n // 2)]
    prices += [100.0 + (n // 2) * 0.5 - i * 0.5 for i in range(n // 2)]
    return [_bar(p, i) for i, p in enumerate(prices)]


# ---------------------------------------------------------------------------
# train_test_split
# ---------------------------------------------------------------------------

def test_split_ratio_67_33():
    bars = _trending_bars(100)
    train, test = train_test_split(bars, train_ratio=0.67)
    assert len(train) == 67
    assert len(test) == 33
    assert len(train) + len(test) == 100


def test_split_preserves_chronological_order():
    bars = _trending_bars(50)
    train, test = train_test_split(bars, 0.67)
    assert train[-1].open_time < test[0].open_time


def test_split_empty_bars():
    train, test = train_test_split([])
    assert train == []
    assert test == []


def test_split_very_small_dataset():
    bars = _trending_bars(10)
    train, test = train_test_split(bars, 0.67)
    assert len(train) + len(test) == 10
    assert len(train) >= 1


def test_split_custom_ratio():
    bars = _trending_bars(100)
    train, test = train_test_split(bars, train_ratio=0.8)
    assert len(train) == 80
    assert len(test) == 20


# ---------------------------------------------------------------------------
# grid_search
# ---------------------------------------------------------------------------

def test_grid_search_returns_optimization_result():
    bars = _trending_bars(200)
    param_grid = {"fast": [3, 5], "slow": [10, 15]}
    result = grid_search(MACrossoverStrategy, param_grid, bars)
    assert isinstance(result, OptimizationResult)


def test_grid_search_covers_all_combinations():
    bars = _trending_bars(200)
    param_grid = {"fast": [3, 5], "slow": [10, 15]}
    result = grid_search(MACrossoverStrategy, param_grid, bars)
    assert len(result.all_results) == 4  # 2 x 2


def test_grid_search_best_is_highest_sharpe():
    bars = _trending_bars(200)
    param_grid = {"fast": [3, 5], "slow": [10, 15]}
    result = grid_search(MACrossoverStrategy, param_grid, bars)
    sharpes = [r.metrics.sharpe for r in result.all_results]
    assert result.best_sharpe == max(sharpes)


def test_grid_search_best_params_keys_match_grid():
    bars = _trending_bars(200)
    param_grid = {"fast": [3, 5], "slow": [10, 15]}
    result = grid_search(MACrossoverStrategy, param_grid, bars)
    assert set(result.best_params.keys()) == {"fast", "slow"}


def test_grid_search_rsi():
    bars = _trending_bars(200)
    param_grid = {"period": [7, 14], "oversold": [25, 30], "overbought": [70, 75]}
    result = grid_search(RSIStrategy, param_grid, bars)
    assert len(result.all_results) == 8  # 2 x 2 x 2
    assert "period" in result.best_params


# ---------------------------------------------------------------------------
# optimize (full train/test pipeline)
# ---------------------------------------------------------------------------

def test_optimize_returns_split_result():
    bars = _trending_bars(200)
    param_grid = {"fast": [3, 5], "slow": [10, 15]}
    result = optimize(MACrossoverStrategy, param_grid, bars)
    assert isinstance(result, SplitResult)


def test_optimize_bar_counts_sum_to_total():
    bars = _trending_bars(200)
    param_grid = {"fast": [3, 5], "slow": [10, 15]}
    result = optimize(MACrossoverStrategy, param_grid, bars)
    assert result.n_train_bars + result.n_test_bars == result.n_total_bars == 200


def test_optimize_train_before_test_chronologically():
    bars = _trending_bars(200)
    param_grid = {"fast": [3, 5], "slow": [10, 15]}
    result = optimize(MACrossoverStrategy, param_grid, bars)
    assert result.train_end < result.test_start


def test_optimize_best_params_applied_to_both_windows():
    bars = _trending_bars(200)
    param_grid = {"fast": [3, 5], "slow": [10, 15]}
    result = optimize(MACrossoverStrategy, param_grid, bars)
    assert result.train_metrics.strategy_name == result.test_metrics.strategy_name


def test_optimize_raises_on_too_few_bars():
    bars = _trending_bars(5)
    with pytest.raises(ValueError, match="at least 10"):
        optimize(MACrossoverStrategy, {"fast": [3], "slow": [10]}, bars)


def test_overfitting_ratio_is_float():
    bars = _trending_bars(200)
    param_grid = {"fast": [3, 5], "slow": [10, 15]}
    result = optimize(MACrossoverStrategy, param_grid, bars)
    assert isinstance(result.overfitting_ratio, float)
