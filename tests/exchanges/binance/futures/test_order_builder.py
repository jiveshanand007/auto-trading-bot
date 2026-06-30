from __future__ import annotations

from trading_bot.core.domain.order import Side
from trading_bot.exchanges.binance.futures.order_builder import (
    build_entry,
    build_set_leverage,
    build_set_margin_type,
    build_stop_market,
    build_take_profit_market,
)


def test_entry_buy_payload():
    payload = build_entry("BTCUSDT", Side.BUY, 0.001)
    assert payload["side"] == "BUY"
    assert payload["type"] == "MARKET"
    assert payload["quantity"] == "0.001"
    assert payload["symbol"] == "BTCUSDT"


def test_stop_market_has_close_position():
    payload = build_stop_market("BTCUSDT", Side.SELL, 95000.0)
    assert payload["type"] == "STOP_MARKET"
    assert payload["closePosition"] == "true"
    assert payload["stopPrice"] == "95000.0"


def test_take_profit_market_has_close_position():
    payload = build_take_profit_market("BTCUSDT", Side.SELL, 105000.0)
    assert payload["type"] == "TAKE_PROFIT_MARKET"
    assert payload["closePosition"] == "true"


def test_set_leverage_payload():
    payload = build_set_leverage("BTCUSDT", 10)
    assert payload["symbol"] == "BTCUSDT"
    assert payload["leverage"] == 10


def test_set_margin_type_payload():
    payload = build_set_margin_type("BTCUSDT", "ISOLATED")
    assert payload["symbol"] == "BTCUSDT"
    assert payload["marginType"] == "ISOLATED"
