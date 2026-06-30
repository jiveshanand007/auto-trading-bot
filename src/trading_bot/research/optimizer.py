from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from trading_bot.analytics.metrics import AnalyticsResult, compute_metrics
from trading_bot.backtest.engine import run_backtest
from trading_bot.backtest.simulated_broker import SimulatedBroker
from trading_bot.market_data.types import Bar
from trading_bot.risk.manager import RiskManager


@dataclass
class ParamResult:
    params: dict[str, Any]
    metrics: AnalyticsResult


@dataclass
class OptimizationResult:
    """Grid-search results over a single set of bars (train or test)."""
    best_params: dict[str, Any]
    best_sharpe: float
    all_results: list[ParamResult] = field(default_factory=list)


@dataclass
class SplitResult:
    """Full train/test optimization report for one strategy."""
    strategy_name: str
    symbol: str
    n_total_bars: int
    n_train_bars: int
    n_test_bars: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    best_params: dict[str, Any]
    train_metrics: AnalyticsResult
    test_metrics: AnalyticsResult

    @property
    def overfitting_ratio(self) -> float:
        """test_sharpe / train_sharpe. Closer to 1.0 = less overfit."""
        if self.train_metrics.sharpe == 0:
            return 0.0
        return self.test_metrics.sharpe / self.train_metrics.sharpe


def train_test_split(
    bars: list[Bar],
    train_ratio: float = 0.67,
) -> tuple[list[Bar], list[Bar]]:
    """Split bars chronologically. Whatever data exists gets split proportionally."""
    if not bars:
        return [], []
    cutoff = max(1, int(len(bars) * train_ratio))
    return bars[:cutoff], bars[cutoff:]


def _all_combinations(param_grid: dict[str, list]) -> list[dict[str, Any]]:
    keys = list(param_grid.keys())
    return [
        dict(zip(keys, values, strict=True))
        for values in itertools.product(*param_grid.values())
    ]


def grid_search(
    strategy_cls: type,
    param_grid: dict[str, list],
    bars: list[Bar],
    initial_capital: float = 10_000.0,
    fee_rate: float = 0.001,
    rank_by: str = "sharpe",
) -> OptimizationResult:
    """Run every param combination on bars, return ranked results."""
    results: list[ParamResult] = []

    for params in _all_combinations(param_grid):
        strategy = strategy_cls(**params)
        broker = SimulatedBroker(initial_capital=initial_capital, fee_rate=fee_rate)
        bt_result = run_backtest(strategy, RiskManager(), broker, bars)
        metrics = compute_metrics(bt_result)
        results.append(ParamResult(params=params, metrics=metrics))

    results.sort(key=lambda r: getattr(r.metrics, rank_by), reverse=True)
    best = results[0]
    return OptimizationResult(
        best_params=best.params,
        best_sharpe=best.metrics.sharpe,
        all_results=results,
    )


def optimize(
    strategy_cls: type,
    param_grid: dict[str, list],
    bars: list[Bar],
    train_ratio: float = 0.67,
    initial_capital: float = 10_000.0,
    fee_rate: float = 0.001,
) -> SplitResult:
    """Grid-search on train split, evaluate best params on test split."""
    if len(bars) < 10:
        raise ValueError(f"Need at least 10 bars, got {len(bars)}")

    train_bars, test_bars = train_test_split(bars, train_ratio)

    opt = grid_search(
        strategy_cls, param_grid, train_bars,
        initial_capital=initial_capital, fee_rate=fee_rate,
    )
    best_params = opt.best_params

    # Evaluate best params on unseen test set
    test_strategy = strategy_cls(**best_params)
    test_broker = SimulatedBroker(initial_capital=initial_capital, fee_rate=fee_rate)
    test_bt = run_backtest(test_strategy, RiskManager(), test_broker, test_bars)
    test_metrics = compute_metrics(test_bt)

    # Re-run train with best params for clean train metrics
    train_strategy = strategy_cls(**best_params)
    train_broker = SimulatedBroker(initial_capital=initial_capital, fee_rate=fee_rate)
    train_bt = run_backtest(train_strategy, RiskManager(), train_broker, train_bars)
    train_metrics = compute_metrics(train_bt)

    name_probe = strategy_cls(**best_params)

    return SplitResult(
        strategy_name=name_probe.name(),
        symbol=bars[0].symbol,
        n_total_bars=len(bars),
        n_train_bars=len(train_bars),
        n_test_bars=len(test_bars),
        train_start=train_bars[0].open_time,
        train_end=train_bars[-1].open_time,
        test_start=test_bars[0].open_time,
        test_end=test_bars[-1].open_time,
        best_params=best_params,
        train_metrics=train_metrics,
        test_metrics=test_metrics,
    )
