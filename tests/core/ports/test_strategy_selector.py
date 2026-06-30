from __future__ import annotations

from trading_bot.core.ports.strategy_selector import IStrategySelector
from trading_bot.market_data.types import Timeframe
from trading_bot.strategy.ma_crossover import MACrossoverStrategy


class _FakeSelector:
    def select(self, symbol: str, timeframe: Timeframe):
        return MACrossoverStrategy()


def test_config_selector_satisfies_protocol():
    selector: IStrategySelector = _FakeSelector()
    result = selector.select("BTCUSDT", Timeframe.H1)
    assert result is not None


def test_protocol_has_select_method():
    assert hasattr(IStrategySelector, "select")
