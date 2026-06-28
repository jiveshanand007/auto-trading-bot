# src/trading_bot/cli/_broker_factory.py
from __future__ import annotations

from trading_bot.config import get_settings
from trading_bot.exchanges.binance.futures.broker import FuturesBroker
from trading_bot.exchanges.binance.spot.broker import SpotBroker


def make_spot_broker() -> SpotBroker:
    return SpotBroker(get_settings())


def make_futures_broker() -> FuturesBroker:
    return FuturesBroker(get_settings())
