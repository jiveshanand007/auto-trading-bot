"""Thin wrapper over python-binance for historical klines.

Klines are public data, so no API key is required here. This class implements
the :class:`KlineFetcher` protocol used by :class:`KlineDownloader`. Order
placement and WebSocket/user-data streams (Week 5) will extend this client.
"""

from __future__ import annotations

from binance.client import Client

from trading_bot.config import Settings, get_settings


class BinanceKlineClient:
    """Fetches historical klines via the Binance REST API."""

    def __init__(self, settings: Settings | None = None):
        settings = settings or get_settings()
        # Historical klines live only on PRODUCTION (the spot testnet carries no
        # real history), and klines are public, so we always use the production
        # data endpoint here regardless of the testnet *trading* flag. Keys are
        # optional for public market data; pass them if present.
        self._client = Client(
            api_key=settings.binance_api_key or None,
            api_secret=settings.binance_api_secret or None,
            testnet=False,
        )

    def fetch_klines(
        self, symbol: str, interval: str, start_ms: int, end_ms: int, limit: int
    ) -> list[list]:
        return self._client.get_klines(
            symbol=symbol,
            interval=interval,
            startTime=start_ms,
            endTime=end_ms,
            limit=limit,
        )
