# src/trading_bot/exchanges/binance/spot/broker.py
from __future__ import annotations

import time

import structlog
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException

from trading_bot.config import Settings, get_settings
from trading_bot.core.domain.order import Side
from trading_bot.core.domain.position import Position
from trading_bot.core.domain.trade import ActiveTrade, TradePlan, TradeStatus
from trading_bot.exchanges.binance.common.errors import BrokerError, map_binance_error
from trading_bot.exchanges.binance.spot.order_builder import build_otoco
from trading_bot.exchanges.binance.spot.validator import validate

log = structlog.get_logger(__name__)

_FILL_RETRIES = 10
_FILL_SLEEP = 0.5


class SpotBroker:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        s = self._settings
        self._client: Client = Client(s.binance_api_key, s.binance_api_secret)
        self._client.API_URL = (
            s.binance_testnet_url if s.binance_testnet else s.binance_live_url
        )

    def get_price(self, symbol: str) -> float:
        try:
            return float(self._client.get_symbol_ticker(symbol=symbol)["price"])
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

    def place_trade(self, plan: TradePlan) -> ActiveTrade:
        current_price = self.get_price(plan.symbol)
        validate(plan, current_price)

        if plan.side == Side.BUY:
            working_price = round(current_price * 1.001, 2)
        else:
            working_price = round(current_price * 0.999, 2)

        payload = build_otoco(plan, working_price)
        try:
            resp = self._client._post("orderList/otoco", True, data=payload)
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

        reports = resp.get("orderReports", [])
        working = reports[0] if reports else {}
        entry_order_id = working.get("orderId", 0)

        fills = working.get("fills", [])
        if fills:
            total_qty = sum(float(f["qty"]) for f in fills)
            total_val = sum(float(f["price"]) * float(f["qty"]) for f in fills)
            entry_price = total_val / total_qty
        else:
            entry_price = self._poll_fill_price(plan.symbol, entry_order_id)

        if plan.side == Side.BUY:
            tp_order_id = reports[1].get("orderId", 0) if len(reports) > 1 else 0
            sl_order_id = reports[2].get("orderId", 0) if len(reports) > 2 else 0
        else:
            sl_order_id = reports[1].get("orderId", 0) if len(reports) > 1 else 0
            tp_order_id = reports[2].get("orderId", 0) if len(reports) > 2 else 0

        return ActiveTrade(
            plan=plan,
            current_stage=0,
            entry_order_id=entry_order_id,
            entry_price=entry_price,
            current_sl_order_id=sl_order_id,
            current_tp_order_id=tp_order_id,
            status=TradeStatus.OPEN,
        )

    def advance_stage(self, trade: ActiveTrade) -> ActiveTrade:
        if not trade.has_next_stage:
            raise BrokerError("No next stage available for this trade")

        trade.status = TradeStatus.ADVANCING
        current = trade.current_stage_def
        next_stage = trade.plan.stages[trade.current_stage + 1]
        side_str = "SELL" if trade.plan.side == Side.BUY else "BUY"

        try:
            self._client.cancel_order(
                symbol=trade.plan.symbol, orderId=trade.current_sl_order_id
            )
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

        new_sl = current.next_stop_loss
        new_tp = next_stage.take_profit

        try:
            sl_resp = self._client.create_order(
                symbol=trade.plan.symbol,
                side=side_str,
                type="STOP_LOSS_LIMIT",
                quantity=str(trade.plan.quantity),
                price=str(round(new_sl * (0.999 if trade.plan.side == Side.BUY else 1.001), 2)),
                stopPrice=str(new_sl),
                timeInForce="GTC",
            )
            tp_resp = self._client.create_order(
                symbol=trade.plan.symbol,
                side=side_str,
                type="LIMIT_MAKER",
                quantity=str(trade.plan.quantity),
                price=str(new_tp),
            )
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

        trade.current_sl_order_id = sl_resp["orderId"]
        trade.current_tp_order_id = tp_resp["orderId"]
        trade.current_stage += 1
        trade.status = TradeStatus.OPEN
        return trade

    def update_stop_loss(self, trade: ActiveTrade, new_sl: float) -> ActiveTrade:
        side_str = "SELL" if trade.plan.side == Side.BUY else "BUY"
        try:
            self._client.cancel_order(
                symbol=trade.plan.symbol, orderId=trade.current_sl_order_id
            )
            sl_resp = self._client.create_order(
                symbol=trade.plan.symbol,
                side=side_str,
                type="STOP_LOSS_LIMIT",
                quantity=str(trade.plan.quantity),
                price=str(round(new_sl * (0.999 if trade.plan.side == Side.BUY else 1.001), 2)),
                stopPrice=str(new_sl),
                timeInForce="GTC",
            )
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

        trade.current_sl_order_id = sl_resp["orderId"]
        return trade

    def close_position(self, symbol: str) -> dict:
        raise NotImplementedError(
            "close_position not implemented for spot; cancel open orders manually"
        )

    def get_open_orders(self, symbol: str | None = None) -> list[dict]:
        try:
            if symbol is not None:
                return self._client.get_open_orders(symbol=symbol)
            return self._client.get_open_orders()
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

    def get_balance(self) -> dict[str, dict]:
        try:
            balances = self._client.get_account()["balances"]
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc
        return {
            b["asset"]: {"free": b["free"], "locked": b["locked"]}
            for b in balances
            if float(b["free"]) > 0 or float(b["locked"]) > 0
        }

    def get_positions(self, symbol: str | None = None) -> list[Position]:
        return []

    def cancel_order(self, symbol: str, order_id: int) -> dict:
        try:
            return self._client.cancel_order(symbol=symbol, orderId=order_id)
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

    def _poll_fill_price(self, symbol: str, order_id: int) -> float:
        try:
            for _ in range(_FILL_RETRIES):
                status = self._client.get_order(symbol=symbol, orderId=order_id)
                if status["status"] == "FILLED":
                    return float(status.get("avgPrice") or status.get("price", 0))
                time.sleep(_FILL_SLEEP)
        except (BinanceAPIException, BinanceOrderException) as exc:
            log.warning("could not poll fill price", error=str(exc))
        return 0.0
