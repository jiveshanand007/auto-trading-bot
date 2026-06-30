from __future__ import annotations

from collections import deque

from trading_bot.core.domain.order import Side
from trading_bot.core.domain.portfolio import PortfolioState
from trading_bot.core.domain.signal import Signal
from trading_bot.market_data.types import Bar


def _ema(prices: list[float], period: int) -> float:
    """EMA seeded with SMA of first `period` prices, then exponentially smoothed."""
    if len(prices) < period:
        return 0.0
    k = 2.0 / (period + 1)
    ema = sum(prices[:period]) / period
    for p in prices[period:]:
        ema = p * k + ema * (1 - k)
    return ema


class MACrossoverStrategy:
    def __init__(
        self,
        fast: int = 9,
        slow: int = 21,
        quantity: float = 0.001,
    ) -> None:
        self._fast = fast
        self._slow = slow
        self._quantity = quantity
        self._prices: deque[float] = deque(maxlen=slow * 4)

    def name(self) -> str:
        return f"ma-crossover({self._fast},{self._slow})"

    def on_bar(self, bar: Bar, portfolio: PortfolioState) -> Signal | None:  # noqa: ARG002
        self._prices.append(float(bar.close))
        prices = list(self._prices)

        if len(prices) < self._slow + 1:
            return None

        prev = prices[:-1]
        curr_fast = _ema(prices, self._fast)
        curr_slow = _ema(prices, self._slow)
        prev_fast = _ema(prev, self._fast)
        prev_slow = _ema(prev, self._slow)

        entry = float(bar.close)

        if prev_fast <= prev_slow and curr_fast > curr_slow:
            return Signal(
                symbol=bar.symbol, side=Side.BUY, quantity=self._quantity,
                entry_price=entry,
                stop_loss=round(entry * 0.98, 8),
                take_profit=round(entry * 1.04, 8),
                reason="MA crossover bullish",
            )

        if prev_fast >= prev_slow and curr_fast < curr_slow:
            return Signal(
                symbol=bar.symbol, side=Side.SELL, quantity=self._quantity,
                entry_price=entry,
                stop_loss=round(entry * 1.02, 8),
                take_profit=round(entry * 0.96, 8),
                reason="MA crossover bearish",
            )

        return None
