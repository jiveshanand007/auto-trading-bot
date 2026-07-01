from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from binance import AsyncClient, BinanceSocketManager

from trading_bot.logging_config import get_logger
from trading_bot.market_data.types import Bar, Timeframe

log = get_logger(__name__)


def _kline_msg_to_bar(msg: dict, symbol: str, timeframe: Timeframe) -> Bar:
    k = msg["k"]
    return Bar(
        symbol=symbol,
        timeframe=timeframe,
        open_time=datetime.fromtimestamp(k["t"] / 1000, tz=timezone.utc),
        close_time=datetime.fromtimestamp(k["T"] / 1000, tz=timezone.utc),
        open=Decimal(str(k["o"])),
        high=Decimal(str(k["h"])),
        low=Decimal(str(k["l"])),
        close=Decimal(str(k["c"])),
        volume=Decimal(str(k["v"])),
    )


class WsFeed:
    """Subscribes to one Binance kline stream; puts a Bar on the queue for each closed candle."""

    def __init__(
        self,
        symbol: str,
        timeframe: Timeframe,
        queue: asyncio.Queue[Bar],
    ) -> None:
        self._symbol = symbol
        self._timeframe = timeframe
        self._queue = queue

    async def run(self, client: AsyncClient) -> None:
        bm = BinanceSocketManager(client)
        interval = self._timeframe.binance_interval
        async with bm.kline_socket(symbol=self._symbol, interval=interval) as stream:
            async for msg in stream:
                try:
                    if msg.get("k", {}).get("x"):
                        bar = _kline_msg_to_bar(msg, self._symbol, self._timeframe)
                        await self._queue.put(bar)
                except Exception as exc:
                    log.error("ws_feed_malformed_message", symbol=self._symbol, error=str(exc))
                    continue
