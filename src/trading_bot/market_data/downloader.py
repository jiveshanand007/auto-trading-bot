"""Download historical OHLCV from Binance into the parquet store.

Binance returns at most 1000 klines per REST call, so a date range is fetched
in pages. The downloader is decoupled from the concrete Binance SDK via the
:class:`KlineFetcher` protocol, which keeps it unit-testable with a fake client
and lets the same logic drive testnet/live clients later.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Protocol

from trading_bot.logging_config import get_logger
from trading_bot.market_data.storage import ParquetBarStore
from trading_bot.market_data.types import Bar, Timeframe

log = get_logger(__name__)

# Binance hard cap on klines returned per request.
MAX_LIMIT = 1000


class KlineFetcher(Protocol):
    """Minimal interface the downloader needs from a Binance client."""

    def fetch_klines(
        self, symbol: str, interval: str, start_ms: int, end_ms: int, limit: int
    ) -> list[list]:
        ...


def _to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def raw_kline_to_bar(raw: list, symbol: str, timeframe: Timeframe) -> Bar:
    """Map a raw Binance kline row to a canonical :class:`Bar`."""
    return Bar(
        symbol=symbol,
        timeframe=timeframe,
        open_time=datetime.fromtimestamp(raw[0] / 1000, tz=timezone.utc),
        close_time=datetime.fromtimestamp(raw[6] / 1000, tz=timezone.utc),
        open=Decimal(str(raw[1])),
        high=Decimal(str(raw[2])),
        low=Decimal(str(raw[3])),
        close=Decimal(str(raw[4])),
        volume=Decimal(str(raw[5])),
    )


class KlineDownloader:
    """Fetch a date range of klines and persist them to the parquet store."""

    def __init__(self, client: KlineFetcher, store: ParquetBarStore):
        self.client = client
        self.store = store

    def download(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> int:
        """Download [start, end] for symbol/timeframe. Returns bars written."""
        interval = timeframe.binance_interval
        step_ms = int(timeframe.duration.total_seconds() * 1000)
        cursor = _to_ms(start)
        end_ms = _to_ms(end)
        total = 0

        while cursor <= end_ms:
            raw = self.client.fetch_klines(symbol, interval, cursor, end_ms, MAX_LIMIT)
            if not raw:
                break
            bars = [raw_kline_to_bar(r, symbol, timeframe) for r in raw]
            self.store.write(bars)
            total += len(bars)
            # Advance past the last open_time fetched to avoid re-requesting it.
            last_open_ms = raw[-1][0]
            cursor = last_open_ms + step_ms
            log.info(
                "klines_page",
                symbol=symbol,
                timeframe=timeframe.value,
                page=len(bars),
                total=total,
            )
            if len(raw) < MAX_LIMIT:
                break

        return total
