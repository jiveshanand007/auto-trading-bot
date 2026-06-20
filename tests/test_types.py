"""Tests for the canonical Bar type — the parity foundation.

The same Bar flows through backtest, testnet, and live. It must be strict,
immutable, and unambiguous about time and timeframe.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trading_bot.market_data.types import Bar, Timeframe


def _bar(**overrides) -> Bar:
    base = dict(
        symbol="BTCUSDT",
        timeframe=Timeframe.H1,
        open_time=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
        close_time=datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        open=Decimal("42000.0"),
        high=Decimal("42500.0"),
        low=Decimal("41800.0"),
        close=Decimal("42300.0"),
        volume=Decimal("123.45"),
    )
    base.update(overrides)
    return Bar(**base)


def test_bar_constructs_and_exposes_fields():
    bar = _bar()
    assert bar.symbol == "BTCUSDT"
    assert bar.timeframe is Timeframe.H1
    assert bar.close == Decimal("42300.0")


def test_bar_is_immutable():
    bar = _bar()
    with pytest.raises(ValidationError):
        bar.close = Decimal("1")  # type: ignore[misc]


def test_open_time_must_be_timezone_aware():
    with pytest.raises(ValueError):
        _bar(open_time=datetime(2024, 1, 1, 0, 0))  # naive


def test_high_must_be_max_and_low_must_be_min():
    with pytest.raises(ValueError):
        _bar(high=Decimal("41000.0"))  # high below open/close
    with pytest.raises(ValueError):
        _bar(low=Decimal("43000.0"))  # low above open/close


def test_negative_volume_rejected():
    with pytest.raises(ValueError):
        _bar(volume=Decimal("-1"))


def test_close_time_must_be_after_open_time():
    with pytest.raises(ValueError):
        _bar(close_time=datetime(2023, 12, 31, 23, 0, tzinfo=timezone.utc))


def test_timeframe_to_pandas_freq_and_binance_interval():
    assert Timeframe.H1.binance_interval == "1h"
    assert Timeframe.M1.binance_interval == "1m"
    assert Timeframe.D1.binance_interval == "1d"


def test_timeframe_duration():
    assert Timeframe.H1.duration.total_seconds() == 3600
    assert Timeframe.M15.duration.total_seconds() == 900
