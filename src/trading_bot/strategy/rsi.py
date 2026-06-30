from __future__ import annotations

from collections import deque

from trading_bot.core.domain.order import Side
from trading_bot.core.domain.portfolio import PortfolioState
from trading_bot.core.domain.signal import Signal
from trading_bot.market_data.types import Bar


def _rsi(prices: list[float], period: int) -> float:
    """Wilder's RSI. Requires len(prices) >= period + 1."""
    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [max(c, 0.0) for c in changes]
    losses = [abs(min(c, 0.0)) for c in changes]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for g, loss in zip(gains[period:], losses[period:], strict=True):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 100.0
    return 100.0 - 100.0 / (1 + avg_gain / avg_loss)


class RSIStrategy:
    def __init__(
        self,
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        quantity: float = 0.001,
    ) -> None:
        self._period = period
        self._oversold = oversold
        self._overbought = overbought
        self._quantity = quantity
        self._prices: deque[float] = deque(maxlen=period * 4)
        self._prev_rsi: float | None = None

    def name(self) -> str:
        return f"rsi({self._period})"

    def on_bar(self, bar: Bar, portfolio: PortfolioState) -> Signal | None:  # noqa: ARG002
        self._prices.append(float(bar.close))
        prices = list(self._prices)

        if len(prices) < self._period + 1:
            return None

        curr_rsi = _rsi(prices, self._period)
        entry = float(bar.close)
        signal = None

        if self._prev_rsi is not None:
            if self._prev_rsi <= self._oversold and curr_rsi > self._oversold:
                signal = Signal(
                    symbol=bar.symbol, side=Side.BUY, quantity=self._quantity,
                    entry_price=entry,
                    stop_loss=round(entry * 0.98, 8),
                    take_profit=round(entry * 1.04, 8),
                    reason=f"RSI crossed above {self._oversold}",
                )
            elif self._prev_rsi >= self._overbought and curr_rsi < self._overbought:
                signal = Signal(
                    symbol=bar.symbol, side=Side.SELL, quantity=self._quantity,
                    entry_price=entry,
                    stop_loss=round(entry * 1.02, 8),
                    take_profit=round(entry * 0.96, 8),
                    reason=f"RSI crossed below {self._overbought}",
                )

        self._prev_rsi = curr_rsi
        return signal
