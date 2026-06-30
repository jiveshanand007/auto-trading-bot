from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from trading_bot.market_data.types import Bar, Timeframe
from trading_bot.market_data.ws_feed import WsFeed, _kline_msg_to_bar


def _kline_msg(symbol: str, open_ms: int, closed: bool) -> dict:
    return {
        "e": "kline",
        "s": symbol,
        "k": {
            "t": open_ms,
            "T": open_ms + 3_600_000,
            "s": symbol,
            "i": "1h",
            "o": "50000.00",
            "c": "51000.00",
            "h": "52000.00",
            "l": "49000.00",
            "v": "100.0",
            "x": closed,
        },
    }


def test_kline_msg_to_bar_fields():
    msg = _kline_msg("BTCUSDT", 1_700_000_000_000, closed=True)
    bar = _kline_msg_to_bar(msg, "BTCUSDT", Timeframe.H1)
    assert isinstance(bar, Bar)
    assert bar.symbol == "BTCUSDT"
    assert bar.close == Decimal("51000.00")
    assert bar.high == Decimal("52000.00")
    assert bar.low == Decimal("49000.00")
    assert bar.open == Decimal("50000.00")
    assert bar.volume == Decimal("100.0")
    assert bar.timeframe == Timeframe.H1
    assert bar.open_time.tzinfo is not None


def test_kline_msg_to_bar_open_time_utc():
    open_ms = 1_700_000_000_000
    msg = _kline_msg("BTCUSDT", open_ms, closed=True)
    bar = _kline_msg_to_bar(msg, "BTCUSDT", Timeframe.H1)
    expected = datetime.fromtimestamp(open_ms / 1000, tz=timezone.utc)
    assert bar.open_time == expected


class _FakeStream:
    def __init__(self, messages: list[dict]) -> None:
        self._messages = list(messages)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def __aiter__(self):
        return self

    async def __anext__(self) -> dict:
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)


class _FakeBSM:
    def __init__(self, messages: list[dict]) -> None:
        self._messages = messages

    def kline_socket(self, symbol: str, interval: str):
        return _FakeStream(self._messages)


async def test_ws_feed_puts_bar_on_closed_kline():
    queue: asyncio.Queue[Bar] = asyncio.Queue()
    feed = WsFeed("BTCUSDT", Timeframe.H1, queue)
    messages = [_kline_msg("BTCUSDT", 1_700_000_000_000, closed=True)]

    import trading_bot.market_data.ws_feed as ws_module
    original_bsm = ws_module.BinanceSocketManager
    ws_module.BinanceSocketManager = lambda client: _FakeBSM(messages)  # type: ignore[assignment]
    try:
        await feed.run(None)  # type: ignore[arg-type]
    finally:
        ws_module.BinanceSocketManager = original_bsm

    assert not queue.empty()
    bar = queue.get_nowait()
    assert bar.symbol == "BTCUSDT"
    assert bar.close == Decimal("51000.00")


async def test_ws_feed_ignores_open_klines():
    queue: asyncio.Queue[Bar] = asyncio.Queue()
    feed = WsFeed("BTCUSDT", Timeframe.H1, queue)
    messages = [
        _kline_msg("BTCUSDT", 1_700_000_000_000, closed=False),
        _kline_msg("BTCUSDT", 1_700_003_600_000, closed=False),
    ]

    import trading_bot.market_data.ws_feed as ws_module
    original_bsm = ws_module.BinanceSocketManager
    ws_module.BinanceSocketManager = lambda client: _FakeBSM(messages)  # type: ignore[assignment]
    try:
        await feed.run(None)  # type: ignore[arg-type]
    finally:
        ws_module.BinanceSocketManager = original_bsm

    assert queue.empty()
