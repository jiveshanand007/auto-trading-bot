from __future__ import annotations

import structlog

from trading_bot.core.ports.broker import IBroker
from trading_bot.core.ports.trade_store import ITradeStore

log = structlog.get_logger(__name__)


class PositionManager:
    """Drives trade lifecycle from price events.

    Wired to the WebSocket price feed in Week 5. Until then, stage
    advancement is triggered manually via the CLI `futures advance` command.
    """

    def __init__(self, broker: IBroker, store: ITradeStore) -> None:
        self._broker = broker
        self._store = store

    def on_price_update(self, symbol: str, price: float) -> None:
        log.debug("price update received (not yet wired)", symbol=symbol, price=price)
