"""Configuration tests."""

from trading_bot.config import Settings


def test_futures_defaults():
    """Test that futures configuration fields have correct defaults."""
    s = Settings()
    assert s.futures_leverage == 5
    assert s.futures_margin_type == "ISOLATED"
    assert s.binance_futures_testnet is True
    assert "fapi" in s.binance_futures_testnet_url
    assert "fapi" in s.binance_futures_live_url
