from __future__ import annotations

from trading_bot.market_data.types import Timeframe
from trading_bot.runner.config import RunnerConfig, StrategyConfig
from trading_bot.strategy.ma_crossover import MACrossoverStrategy
from trading_bot.strategy.rsi import RSIStrategy

_STRATEGY_CLASSES = {
    "ma-crossover": MACrossoverStrategy,
    "rsi": RSIStrategy,
}


class ConfigSelector:
    """Returns a fresh strategy instance per select() call.

    The runner calls select() once per coroutine at startup and holds
    the instance for the coroutine's lifetime — price buffers accumulate
    correctly across bars.
    """

    def __init__(self, cfg: RunnerConfig) -> None:
        self._index: dict[tuple[str, str], StrategyConfig] = {
            (s.symbol, s.timeframe): s for s in cfg.strategies
        }

    def select(self, symbol: str, timeframe: Timeframe):
        key = (symbol, timeframe.value)
        cfg = self._index.get(key)
        if cfg is None:
            raise KeyError(f"No strategy configured for {symbol}/{timeframe.value}")
        cls = _STRATEGY_CLASSES[cfg.strategy]
        return cls(**cfg.params)
