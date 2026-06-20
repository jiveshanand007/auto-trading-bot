"""Canonical market-data types shared across backtest, testnet, and live.

The :class:`Bar` is the parity foundation: the *same* type flows through every
mode, so a strategy that sees a Bar in backtest sees the identical shape live.
We keep it strict (validated, immutable, timezone-aware, Decimal prices) so
divergence bugs surface at construction time rather than in trading logic.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from enum import Enum

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator


class Timeframe(str, Enum):
    """Supported candle intervals, mapped to Binance interval strings."""

    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"

    @property
    def binance_interval(self) -> str:
        return {
            Timeframe.M1: "1m",
            Timeframe.M5: "5m",
            Timeframe.M15: "15m",
            Timeframe.M30: "30m",
            Timeframe.H1: "1h",
            Timeframe.H4: "4h",
            Timeframe.D1: "1d",
        }[self]

    @property
    def duration(self) -> timedelta:
        return {
            Timeframe.M1: timedelta(minutes=1),
            Timeframe.M5: timedelta(minutes=5),
            Timeframe.M15: timedelta(minutes=15),
            Timeframe.M30: timedelta(minutes=30),
            Timeframe.H1: timedelta(hours=1),
            Timeframe.H4: timedelta(hours=4),
            Timeframe.D1: timedelta(days=1),
        }[self]


class Bar(BaseModel):
    """One OHLCV candle for a symbol at a timeframe.

    Times must be timezone-aware (UTC by convention). Prices use Decimal to
    avoid float drift in P&L and risk math.
    """

    model_config = ConfigDict(frozen=True)

    symbol: str
    timeframe: Timeframe
    open_time: AwareDatetime
    close_time: AwareDatetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    @model_validator(mode="after")
    def _validate_consistency(self) -> Bar:
        if self.close_time <= self.open_time:
            raise ValueError("close_time must be after open_time")
        prices = (self.open, self.close, self.high, self.low)
        if self.high < max(prices):
            raise ValueError("high must be >= open, close, and low")
        if self.low > min(prices):
            raise ValueError("low must be <= open, close, and high")
        if self.volume < 0:
            raise ValueError("volume must be non-negative")
        return self
