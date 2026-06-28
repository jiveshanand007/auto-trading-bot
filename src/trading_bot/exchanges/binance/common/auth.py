"""Binance client factory functions for Spot and Futures trading."""

from __future__ import annotations

from binance.client import Client

from trading_bot.config import Settings


def make_spot_client(settings: Settings) -> Client:
    """Create a Binance Spot trading client.

    Args:
        settings: Application settings containing API credentials and endpoints.

    Returns:
        Configured binance.client.Client for Spot trading.
    """
    client = Client(settings.binance_api_key, settings.binance_api_secret)
    client.API_URL = (
        settings.binance_testnet_url if settings.binance_testnet else settings.binance_live_url
    )
    return client


def make_futures_client(settings: Settings) -> Client:
    """Create a Binance Futures (USDM) trading client.

    Args:
        settings: Application settings containing API credentials and endpoints.

    Returns:
        Configured binance.client.Client for Futures trading.
    """
    client = Client(settings.binance_api_key, settings.binance_api_secret)
    client.API_URL = (
        settings.binance_futures_testnet_url
        if settings.binance_futures_testnet
        else settings.binance_futures_live_url
    )
    return client
