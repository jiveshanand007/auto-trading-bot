"""CLI to download historical klines into the parquet store.

Example::

    uv run python -m trading_bot.market_data.download_cli \
        --symbols BTCUSDT ETHUSDT --timeframe H1 \
        --start 2024-01-01 --end 2024-02-01
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from trading_bot.config import get_settings
from trading_bot.logging_config import configure_logging, get_logger
from trading_bot.market_data.binance_client import BinanceKlineClient
from trading_bot.market_data.downloader import KlineDownloader
from trading_bot.market_data.storage import ParquetBarStore
from trading_bot.market_data.types import Timeframe

log = get_logger(__name__)


def _parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download Binance historical klines.")
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument(
        "--timeframe", default="H1", choices=[tf.value for tf in Timeframe]
    )
    parser.add_argument("--start", required=True, type=_parse_date)
    parser.add_argument("--end", required=True, type=_parse_date)
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    store = ParquetBarStore(settings.data_dir)
    downloader = KlineDownloader(BinanceKlineClient(settings), store)
    timeframe = Timeframe(args.timeframe)

    for symbol in args.symbols:
        count = downloader.download(symbol, timeframe, args.start, args.end)
        log.info("downloaded", symbol=symbol, timeframe=timeframe.value, bars=count)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
