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
        self._client = Client(s.binance_api_key, s.binance_api_secret)
        # python-binance 1.0.x testnet=True doesn't reroute the sync Client;
        # use the URL from config so it's overridable without a code change.
        self._client.API_URL = (
            s.binance_testnet_url if s.binance_testnet else s.binance_live_url
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
            current_price = float(
                self._client.get_symbol_ticker(symbol=symbol)["price"]
            )
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

        # Single atomic OTOCO: entry market order + OCO (SL+TP) placed together.
        # If the OCO setup fails, the working order is also rejected — no orphaned positions.
        if side_upper == "BUY":
            data = {
                "symbol": symbol,
                "workingType": "MARKET",
                "workingSide": "BUY",
                "workingQuantity": str(quantity),
                "pendingSide": "SELL",
                "pendingQuantity": str(quantity),
                "pendingAboveType": "LIMIT_MAKER",
                "pendingAbovePrice": str(take_profit),
                "pendingBelowType": "STOP_LOSS_LIMIT",
                "pendingBelowStopPrice": str(stop_loss),
                "pendingBelowPrice": str(round(stop_loss * 0.999, 2)),
                "pendingBelowTimeInForce": "GTC",
            }
        else:
            data = {
                "symbol": symbol,
                "workingType": "MARKET",
                "workingSide": "SELL",
                "workingQuantity": str(quantity),
                "pendingSide": "BUY",
                "pendingQuantity": str(quantity),
                "pendingAboveType": "STOP_LOSS_LIMIT",
                "pendingAboveStopPrice": str(stop_loss),
                "pendingAbovePrice": str(round(stop_loss * 1.001, 2)),
                "pendingAboveTimeInForce": "GTC",
                "pendingBelowType": "LIMIT_MAKER",
                "pendingBelowPrice": str(take_profit),
            }

        try:
            resp = self._client._post("orderList/otoco", True, data=data)
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise BrokerError(str(exc), original=exc) from exc

        order_reports = resp.get("orderReports", [])
        working = order_reports[0] if order_reports else {}
        entry_order_id = working.get("orderId", 0)

        fills = working.get("fills", [])
        if fills:
            total_qty = sum(float(f["qty"]) for f in fills)
            total_val = sum(float(f["price"]) * float(f["qty"]) for f in fills)
            entry_price = total_val / total_qty
        else:
            # MARKET fills usually land in the response; poll as fallback
            entry_price = 0.0
            try:
                for _ in range(_FILL_RETRIES):
                    status = self._client.get_order(symbol=symbol, orderId=entry_order_id)
                    if status["status"] == "FILLED":
                        entry_price = float(status.get("avgPrice") or status.get("price", 0))
                        break
                    time.sleep(_FILL_SLEEP)
            except (BinanceAPIException, BinanceOrderException) as exc:
                log.warning("could not poll fill price", error=str(exc))

        return TradeResult(
            symbol=symbol,
            side=side_upper,
            quantity=quantity,
            entry_price=entry_price,
            entry_order_id=entry_order_id,
            oco_order_list_id=resp["orderListId"],
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
