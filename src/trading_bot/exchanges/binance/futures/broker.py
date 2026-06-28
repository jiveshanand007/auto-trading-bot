from __future__ import annotations

import dataclasses
import time

import structlog
from binance.exceptions import BinanceAPIException, BinanceOrderException

from trading_bot.config import Settings, get_settings
from trading_bot.core.domain.order import MarginType, Side
from trading_bot.core.domain.position import Position
from trading_bot.core.domain.trade import ActiveTrade, TradePlan, TradeStatus
from trading_bot.exchanges.binance.common.auth import make_futures_client
from trading_bot.exchanges.binance.common.errors import BrokerError, map_binance_error
from trading_bot.exchanges.binance.futures.order_builder import (
    build_entry,
    build_set_margin_type,
    build_stop_market,
    build_take_profit_market,
)
from trading_bot.exchanges.binance.futures.validator import validate

log = structlog.get_logger(__name__)

_FILL_RETRIES = 10
_FILL_SLEEP = 0.5
_MARGIN_NO_CHANGE_CODE = -4046
_ORDER_ALREADY_GONE_CODE = -2011


class FuturesBroker:
    def __init__(self, settings: Settings | None = None, *, client=None) -> None:
        self._settings = settings or get_settings()
        self._client = client if client is not None else make_futures_client(self._settings)

    def get_price(self, symbol: str) -> float:
        try:
            return float(self._client.futures_symbol_ticker(symbol=symbol)["price"])
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

    def place_trade(self, plan: TradePlan) -> ActiveTrade:
        current_price = self.get_price(plan.symbol)
        validate(plan, current_price)
        self._configure_symbol(plan)

        exit_side = Side.SELL if plan.side == Side.BUY else Side.BUY

        try:
            entry_resp = self._client.futures_create_order(
                **build_entry(plan.symbol, plan.side, plan.quantity)
            )
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

        entry_order_id = entry_resp["orderId"]
        entry_price = self._resolve_entry_price(entry_resp, plan.symbol, entry_order_id)

        try:
            sl_resp = self._client.futures_create_order(
                **build_stop_market(plan.symbol, exit_side, plan.initial_stop_loss)
            )
            tp_resp = self._client.futures_create_order(
                **build_take_profit_market(plan.symbol, exit_side, plan.stages[0].take_profit)
            )
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

        return ActiveTrade(
            plan=plan,
            current_stage=0,
            entry_order_id=entry_order_id,
            entry_price=entry_price,
            current_sl_order_id=sl_resp["orderId"],
            current_tp_order_id=tp_resp["orderId"],
            status=TradeStatus.OPEN,
        )

    def advance_stage(self, trade: ActiveTrade) -> ActiveTrade:
        if not trade.has_next_stage:
            raise BrokerError("No next stage available for this trade")

        current = trade.current_stage_def
        next_stage = trade.plan.stages[trade.current_stage + 1]
        exit_side = Side.SELL if trade.plan.side == Side.BUY else Side.BUY

        try:
            self._cancel_order_safe(trade.plan.symbol, trade.current_sl_order_id)
            self._cancel_order_safe(trade.plan.symbol, trade.current_tp_order_id)

            sl_resp = self._client.futures_create_order(
                **build_stop_market(trade.plan.symbol, exit_side, current.next_stop_loss)
            )
            tp_resp = self._client.futures_create_order(
                **build_take_profit_market(trade.plan.symbol, exit_side, next_stage.take_profit)
            )
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

        return dataclasses.replace(
            trade,
            current_stage=trade.current_stage + 1,
            current_sl_order_id=sl_resp["orderId"],
            current_tp_order_id=tp_resp["orderId"],
            status=TradeStatus.OPEN,
        )

    def update_stop_loss(self, trade: ActiveTrade, new_sl: float) -> ActiveTrade:
        exit_side = Side.SELL if trade.plan.side == Side.BUY else Side.BUY
        try:
            self._cancel_order_safe(trade.plan.symbol, trade.current_sl_order_id)
            sl_resp = self._client.futures_create_order(
                **build_stop_market(trade.plan.symbol, exit_side, new_sl)
            )
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

        return dataclasses.replace(trade, current_sl_order_id=sl_resp["orderId"])

    def close_position(self, symbol: str) -> dict:
        try:
            positions = self._client.futures_position_information(symbol=symbol)
            pos = next((p for p in positions if float(p.get("positionAmt", 0)) != 0), None)
            if pos is None:
                return {"msg": "no open position"}
            amt = float(pos["positionAmt"])
            close_side = "SELL" if amt > 0 else "BUY"
            return self._client.futures_create_order(
                symbol=symbol,
                side=close_side,
                type="MARKET",
                quantity=str(abs(amt)),
                reduceOnly="true",
            )
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

    def get_open_orders(self, symbol: str | None = None) -> list[dict]:
        try:
            if symbol is not None:
                return self._client.futures_get_open_orders(symbol=symbol)
            return self._client.futures_get_open_orders()
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

    def get_balance(self) -> dict:
        try:
            return self._client.futures_account()
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

    def get_positions(self, symbol: str | None = None) -> list[Position]:
        try:
            kwargs = {"symbol": symbol} if symbol else {}
            raw = self._client.futures_position_information(**kwargs)
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

        result = []
        for p in raw:
            if float(p.get("positionAmt", 0)) == 0:
                continue
            amt = float(p["positionAmt"])
            side = Side.BUY if amt > 0 else Side.SELL
            margin_type = (
                MarginType.ISOLATED
                if p.get("marginType", "").lower() == "isolated"
                else MarginType.CROSS
            )
            result.append(Position(
                symbol=p["symbol"],
                side=side,
                quantity=abs(amt),
                entry_price=float(p.get("entryPrice", 0)),
                leverage=int(p.get("leverage", 1)),
                liquidation_price=float(p.get("liquidationPrice", 0)),
                unrealized_pnl=float(p.get("unrealizedProfit", 0)),
                margin_type=margin_type,
            ))
        return result

    def cancel_order(self, symbol: str, order_id: int) -> dict:
        try:
            return self._client.futures_cancel_order(symbol=symbol, orderId=order_id)
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

    def _configure_symbol(self, plan: TradePlan) -> None:
        try:
            self._client.futures_change_leverage(symbol=plan.symbol, leverage=plan.leverage)
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc
        try:
            self._client.futures_change_margin_type(
                **build_set_margin_type(plan.symbol, plan.margin_type.value)
            )
        except BinanceAPIException as exc:
            if getattr(exc, "code", None) == _MARGIN_NO_CHANGE_CODE:
                return
            raise map_binance_error(exc) from exc

    def _cancel_order_safe(self, symbol: str, order_id: int) -> None:
        try:
            self._client.futures_cancel_order(symbol=symbol, orderId=order_id)
        except BinanceAPIException as exc:
            if getattr(exc, "code", None) == _ORDER_ALREADY_GONE_CODE:
                log.debug("order already gone, skipping cancel", order_id=order_id)
                return
            raise map_binance_error(exc) from exc

    def _resolve_entry_price(self, entry_resp: dict, symbol: str, order_id: int) -> float:
        avg = entry_resp.get("avgPrice")
        if avg and float(avg) > 0:
            return float(avg)
        try:
            for _ in range(_FILL_RETRIES):
                status = self._client.futures_get_order(symbol=symbol, orderId=order_id)
                if status["status"] == "FILLED":
                    return float(status.get("avgPrice") or status.get("price", 0))
                time.sleep(_FILL_SLEEP)
        except (BinanceAPIException, BinanceOrderException) as exc:
            log.warning("could not poll futures fill price", error=str(exc))
        return 0.0
