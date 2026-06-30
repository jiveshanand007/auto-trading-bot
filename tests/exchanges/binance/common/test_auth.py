"""Tests for Binance client factory functions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from trading_bot.config import Settings
from trading_bot.exchanges.binance.common.auth import make_futures_client, make_spot_client


@patch("trading_bot.exchanges.binance.common.auth.Client")
def test_make_spot_client_testnet(mock_client_class):
    """make_spot_client should use testnet URL when binance_testnet=True."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    settings = Settings(
        binance_api_key="test_key",
        binance_api_secret="test_secret",
        binance_testnet=True,
        binance_testnet_url="https://testnet.binance.vision/api",
    )

    client = make_spot_client(settings)

    mock_client_class.assert_called_once_with("test_key", "test_secret")
    assert mock_client.API_URL == "https://testnet.binance.vision/api"
    assert client is mock_client


@patch("trading_bot.exchanges.binance.common.auth.Client")
def test_make_spot_client_live(mock_client_class):
    """make_spot_client should use live URL when binance_testnet=False."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    settings = Settings(
        binance_api_key="test_key",
        binance_api_secret="test_secret",
        binance_testnet=False,
        binance_live_url="https://api.binance.com/api",
    )

    client = make_spot_client(settings)

    mock_client_class.assert_called_once_with("test_key", "test_secret")
    assert mock_client.API_URL == "https://api.binance.com/api"
    assert client is mock_client


@patch("trading_bot.exchanges.binance.common.auth.Client")
def test_make_futures_client_testnet(mock_client_class):
    """make_futures_client should use futures testnet URL when binance_futures_testnet=True."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    settings = Settings(
        binance_api_key="test_key",
        binance_api_secret="test_secret",
        binance_futures_testnet=True,
        binance_futures_testnet_url="https://testnet.binancefuture.com/fapi",
    )

    client = make_futures_client(settings)

    mock_client_class.assert_called_once_with("test_key", "test_secret")
    assert mock_client.FUTURES_URL == "https://testnet.binancefuture.com/fapi"
    assert client is mock_client


@patch("trading_bot.exchanges.binance.common.auth.Client")
def test_make_futures_client_live(mock_client_class):
    """make_futures_client should use futures live URL when binance_futures_testnet=False."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    settings = Settings(
        binance_api_key="test_key",
        binance_api_secret="test_secret",
        binance_futures_testnet=False,
        binance_futures_live_url="https://fapi.binance.com/fapi",
    )

    client = make_futures_client(settings)

    mock_client_class.assert_called_once_with("test_key", "test_secret")
    assert mock_client.FUTURES_URL == "https://fapi.binance.com/fapi"
    assert client is mock_client
