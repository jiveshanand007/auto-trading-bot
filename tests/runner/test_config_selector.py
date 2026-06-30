from __future__ import annotations

import pytest

from trading_bot.market_data.types import Timeframe
from trading_bot.runner.config import RunnerConfig, StrategyConfig
from trading_bot.runner.config_selector import ConfigSelector
from trading_bot.strategy.ma_crossover import MACrossoverStrategy
from trading_bot.strategy.rsi import RSIStrategy


def _cfg(strategy: str, symbol: str, params: dict) -> StrategyConfig:
    return StrategyConfig(
        strategy=strategy, symbol=symbol, timeframe="H1",
        market="spot", params=params,
    )


def _runner_cfg(*strategies) -> RunnerConfig:
    return RunnerConfig(strategies=list(strategies))


def test_returns_ma_crossover_strategy():
    cfg = _runner_cfg(_cfg("ma-crossover", "BTCUSDT", {"fast": 9, "slow": 21}))
    selector = ConfigSelector(cfg)
    strategy = selector.select("BTCUSDT", Timeframe.H1)
    assert isinstance(strategy, MACrossoverStrategy)


def test_returns_rsi_strategy():
    cfg = _runner_cfg(_cfg("rsi", "ETHUSDT", {"period": 14}))
    selector = ConfigSelector(cfg)
    strategy = selector.select("ETHUSDT", Timeframe.H1)
    assert isinstance(strategy, RSIStrategy)


def test_select_returns_new_instance_each_call():
    cfg = _runner_cfg(_cfg("ma-crossover", "BTCUSDT", {"fast": 9, "slow": 21}))
    selector = ConfigSelector(cfg)
    a = selector.select("BTCUSDT", Timeframe.H1)
    b = selector.select("BTCUSDT", Timeframe.H1)
    assert a is not b


def test_params_passed_to_strategy():
    cfg = _runner_cfg(_cfg("ma-crossover", "BTCUSDT", {"fast": 5, "slow": 50}))
    selector = ConfigSelector(cfg)
    strategy = selector.select("BTCUSDT", Timeframe.H1)
    assert isinstance(strategy, MACrossoverStrategy)
    assert strategy._fast == 5
    assert strategy._slow == 50


def test_raises_for_unconfigured_symbol():
    cfg = _runner_cfg(_cfg("ma-crossover", "BTCUSDT", {}))
    selector = ConfigSelector(cfg)
    with pytest.raises(KeyError):
        selector.select("SOLUSDT", Timeframe.H1)


def test_multiple_symbols_resolved_independently():
    cfg = _runner_cfg(
        _cfg("ma-crossover", "BTCUSDT", {"fast": 9, "slow": 21}),
        _cfg("rsi", "ETHUSDT", {"period": 14}),
    )
    selector = ConfigSelector(cfg)
    btc = selector.select("BTCUSDT", Timeframe.H1)
    eth = selector.select("ETHUSDT", Timeframe.H1)
    assert isinstance(btc, MACrossoverStrategy)
    assert isinstance(eth, RSIStrategy)
