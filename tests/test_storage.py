"""Tests for the parquet OHLCV storage layer."""

from datetime import datetime, timezone
from decimal import Decimal

from trading_bot.market_data.storage import ParquetBarStore
from trading_bot.market_data.types import Bar, Timeframe


def _bars(symbol="BTCUSDT", tf=Timeframe.H1, n=5, start=None):
    start = start or datetime(2024, 1, 1, tzinfo=timezone.utc)
    out = []
    for i in range(n):
        ot = start + i * tf.duration
        out.append(
            Bar(
                symbol=symbol,
                timeframe=tf,
                open_time=ot,
                close_time=ot + tf.duration,
                open=Decimal("100") + i,
                high=Decimal("110") + i,
                low=Decimal("90") + i,
                close=Decimal("105") + i,
                volume=Decimal("1.5"),
            )
        )
    return out


def test_write_then_read_roundtrip(tmp_path):
    store = ParquetBarStore(tmp_path)
    bars = _bars(n=5)
    store.write(bars)
    read = store.read("BTCUSDT", Timeframe.H1)
    assert read == bars


def test_partitioned_by_symbol_and_timeframe(tmp_path):
    store = ParquetBarStore(tmp_path)
    store.write(_bars(symbol="BTCUSDT", tf=Timeframe.H1, n=3))
    store.write(_bars(symbol="ETHUSDT", tf=Timeframe.M15, n=2))
    assert (tmp_path / "symbol=BTCUSDT" / "timeframe=H1").exists()
    assert (tmp_path / "symbol=ETHUSDT" / "timeframe=M15").exists()
    assert len(store.read("BTCUSDT", Timeframe.H1)) == 3
    assert len(store.read("ETHUSDT", Timeframe.M15)) == 2


def test_append_dedupes_on_open_time(tmp_path):
    store = ParquetBarStore(tmp_path)
    first = _bars(n=5)
    store.write(first)
    # Overlapping write: last 2 of first batch + 3 new ones.
    overlap = _bars(n=8)[3:]
    store.write(overlap)
    read = store.read("BTCUSDT", Timeframe.H1)
    open_times = [b.open_time for b in read]
    assert len(open_times) == len(set(open_times)) == 8
    assert read == sorted(read, key=lambda b: b.open_time)


def test_read_missing_returns_empty(tmp_path):
    store = ParquetBarStore(tmp_path)
    assert store.read("NOPE", Timeframe.D1) == []


def test_read_time_range_filter(tmp_path):
    store = ParquetBarStore(tmp_path)
    bars = _bars(n=10)
    store.write(bars)
    start = bars[3].open_time
    end = bars[6].open_time
    read = store.read("BTCUSDT", Timeframe.H1, start=start, end=end)
    assert [b.open_time for b in read] == [b.open_time for b in bars[3:7]]
