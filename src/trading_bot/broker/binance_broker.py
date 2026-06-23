"""Binance broker implementation wrapping python-binance."""

from __future__ import annotations

import time
from dataclasses import dataclass

import structlog
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException

from trading_bot.config import Settings, get_settings

log = structlog.get_logger(__name__)

_FILL_RETRIES = 10
_FILL_SLEEP = 0.5


class BrokerError(Exception):
    def __init__(self, message: str, original: Exception | None = None):
        super().__init__(message)
        self.original = original


@dataclass
class TradeResult:
    symbol: str
    side: str
    quantity: float
    entry_price: float
    entry_order_id: int
    oco_order_list_id: int
    stop_loss: float
    take_profit: float


class BinanceBroker:
    def __init__(self, settings: Settings | None = None):
        self._settings = settings or get_settings()
        s = self._settings
        self._client = Client(
            s.binance_api_key,
            s.binance_api_secret,
            testnet=s.binance_testnet,
        )

    def place_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_loss: float,
        take_profit: float,
    ) -> TradeResult:
        try:
            raw_price = self._client.get_symbol_ticker(symbol=symbol)["price"]
            current_price = float(raw_price)
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise BrokerError(str(exc), original=exc) from exc

        side_upper = side.upper()
        if side_upper == "BUY":
            if not (stop_loss < current_price < take_profit):
                raise ValueError(
                    f"BUY validation failed: stop_loss={stop_loss} must be < "
                    f"current_price={current_price} < take_profit={take_profit}"
                )
        elif side_upper == "SELL":
            if not (take_profit < current_price < stop_loss):
                raise ValueError(
                    f"SELL validation failed: take_profit={take_profit} must be < "
                    f"current_price={current_price} < stop_loss={stop_loss}"
                )
        else:
            raise ValueError(f"side must be 'BUY' or 'SELL', got {side!r}")

        try:
            if side_upper == "BUY":
                order = self._client.order_market_buy(symbol=symbol, quantity=quantity)
            else:
                order = self._client.order_market_sell(symbol=symbol, quantity=quantity)
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise BrokerError(str(exc), original=exc) from exc

        order_id = order["orderId"]

        fills = order.get("fills", [])
        if fills:
            total_qty = sum(float(f["qty"]) for f in fills)
            total_val = sum(float(f["price"]) * float(f["qty"]) for f in fills)
            entry_price = total_val / total_qty
        else:
            entry_price = float(order.get("price", 0))

        try:
            for _ in range(_FILL_RETRIES):
                status = self._client.get_order(symbol=symbol, orderId=order_id)
                if status["status"] == "FILLED":
                    break
                time.sleep(_FILL_SLEEP)
            else:
                log.warning("order not filled after retries", order_id=order_id)
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise BrokerError(str(exc), original=exc) from exc

        oco_side = "SELL" if side_upper == "BUY" else "BUY"
        stop_limit_price = str(round(stop_loss * 0.999, 2))

        try:
            oco_resp = self._client.create_oco_order(
                symbol=symbol,
                side=oco_side,
                quantity=quantity,
                price=str(take_profit),
                stopPrice=str(stop_loss),
                stopLimitPrice=stop_limit_price,
                stopLimitTimeInForce="GTC",
            )
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise BrokerError(str(exc), original=exc) from exc

        oco_order_list_id = oco_resp["orderListId"]

        return TradeResult(
            symbol=symbol,
            side=side_upper,
            quantity=quantity,
            entry_price=entry_price,
            entry_order_id=order_id,
            oco_order_list_id=oco_order_list_id,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    def get_open_orders(self, symbol: str | None = None) -> list[dict]:
        try:
            if symbol is not None:
                return self._client.get_open_orders(symbol=symbol)
            return self._client.get_open_orders()
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise BrokerError(str(exc), original=exc) from exc

    def get_balance(self) -> dict[str, dict]:
        try:
            balances = self._client.get_account()["balances"]
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise BrokerError(str(exc), original=exc) from exc

        return {
            b["asset"]: {"free": b["free"], "locked": b["locked"]}
            for b in balances
            if float(b["free"]) > 0 or float(b["locked"]) > 0
        }

    def cancel_order(self, symbol: str, order_id: int) -> dict:
        try:
            return self._client.cancel_order(symbol=symbol, orderId=order_id)
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise BrokerError(str(exc), original=exc) from exc
