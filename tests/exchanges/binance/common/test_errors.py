"""Tests for Binance error handling."""

from __future__ import annotations

from unittest.mock import MagicMock

from binance.exceptions import BinanceAPIException

from trading_bot.exchanges.binance.common.errors import BrokerError, map_binance_error


def test_broker_error_stores_code_and_original():
    """BrokerError should store code and original exception."""
    original = ValueError("boom")
    err = BrokerError("test", code=-1013, original=original)
    assert str(err) == "test"
    assert err.code == -1013
    assert err.original is original


def test_map_binance_error_extracts_code():
    """map_binance_error should convert BinanceAPIException to BrokerError."""
    exc = BinanceAPIException(MagicMock(status_code=400), 400, '{"code": -1013, "msg": "bad qty"}')
    result = map_binance_error(exc)
    assert isinstance(result, BrokerError)
    assert result.original is exc
