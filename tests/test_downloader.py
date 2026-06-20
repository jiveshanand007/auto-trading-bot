"""Tests for the Binance klines downloader (pagination + mapping), mocked."""

from datetime import datetime, timezone
from decimal import Decimal

from trading_bot.market_data.downloader import KlineDownloader, raw_kline_to_bar
from trading_bot.market_data.storage import ParquetBarStore
from trading_bot.market_data.types import Timeframe

HOUR_MS = 3_600_000


def _raw(open_ms: int) -> list:
    """A raw Binance kline row for a 1h candle starting at open_ms."""
    return [
        open_ms,
        "100.0",  # open
        "110.0",  # high
        "90.0",  # low
        "105.0",  # close
        "1.5",  # volume
        open_ms + HOUR_MS - 1,  # close_time
        "157500.0",  # quote asset volume
        42,  # number of trades
        "0.7",  # taker buy base
        "73500.0",  # taker buy quote
        "0",  # ignore
    ]


class FakeBinanceClient:
    """Returns up to `limit` klines per call, starting at start_ms, capped at end_ms."""

    def __init__(self, first_open_ms: int, total: int, page_limit: int = 1000):
        self.available = [first_open_ms + i * HOUR_MS for i in range(total)]
        self.page_limit = page_limit
        self.calls: list[tuple[int, int]] = []

    def fetch_klines(self, symbol, interval, start_ms, end_ms, limit):
        self.calls.append((start_ms, end_ms))
        page = [o for o in self.available if start_ms <= o <= end_ms]
        page = page[: min(limit, self.page_limit)]
        return [_raw(o) for o in page]


def test_raw_kline_to_bar_maps_fields():
    open_ms = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    bar = raw_kline_to_bar(_raw(open_ms), "BTCUSDT", Timeframe.H1)
    assert bar.symbol == "BTCUSDT"
    assert bar.open == Decimal("100.0")
    assert bar.high == Decimal("110.0")
    assert bar.volume == Decimal("1.5")
    assert bar.open_time == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert bar.close_time > bar.open_time


def test_download_single_page(tmp_path):
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    first_ms = int(start.timestamp() * 1000)
    client = FakeBinanceClient(first_ms, total=10)
    store = ParquetBarStore(tmp_path)
    n = KlineDownloader(client, store).download(
        "BTCUSDT", Timeframe.H1, start, datetime(2024, 1, 1, 10, tzinfo=timezone.utc)
    )
    assert n == 10
    assert len(store.read("BTCUSDT", Timeframe.H1)) == 10


def test_download_paginates_across_limit(tmp_path):
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    first_ms = int(start.timestamp() * 1000)
    client = FakeBinanceClient(first_ms, total=2500, page_limit=1000)
    store = ParquetBarStore(tmp_path)
    end = start.replace() + Timeframe.H1.duration * 2500
    n = KlineDownloader(client, store).download("BTCUSDT", Timeframe.H1, start, end)
    assert n == 2500
    assert len(store.read("BTCUSDT", Timeframe.H1)) == 2500
    # 2500 bars / 1000 per page => at least 3 paginated calls.
    assert len(client.calls) >= 3
    # Each subsequent call must advance the window (no infinite loop).
    starts = [c[0] for c in client.calls]
    assert starts == sorted(starts)
    assert len(set(starts)) == len(starts)


def test_download_empty_range_writes_nothing(tmp_path):
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    first_ms = int(start.timestamp() * 1000)
    client = FakeBinanceClient(first_ms, total=0)
    store = ParquetBarStore(tmp_path)
    n = KlineDownloader(client, store).download(
        "BTCUSDT", Timeframe.H1, start, datetime(2024, 1, 2, tzinfo=timezone.utc)
    )
    assert n == 0
    assert store.read("BTCUSDT", Timeframe.H1) == []
