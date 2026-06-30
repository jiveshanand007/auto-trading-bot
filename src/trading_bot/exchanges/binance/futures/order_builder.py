from __future__ import annotations

from trading_bot.core.domain.order import Side


def build_entry(symbol: str, side: Side, quantity: float) -> dict:
    return {
        "symbol": symbol,
        "side": side.value,
        "type": "MARKET",
        "quantity": str(quantity),
    }


def build_stop_market(symbol: str, side: Side, stop_price: float) -> dict:
    return {
        "symbol": symbol,
        "side": side.value,
        "type": "STOP_MARKET",
        "stopPrice": str(stop_price),
        "closePosition": "true",
        "timeInForce": "GTE_GTC",
    }


def build_take_profit_market(symbol: str, side: Side, take_profit_price: float) -> dict:
    return {
        "symbol": symbol,
        "side": side.value,
        "type": "TAKE_PROFIT_MARKET",
        "stopPrice": str(take_profit_price),
        "closePosition": "true",
        "timeInForce": "GTE_GTC",
    }


def build_set_leverage(symbol: str, leverage: int) -> dict:
    return {"symbol": symbol, "leverage": leverage}


def build_set_margin_type(symbol: str, margin_type: str) -> dict:
    return {"symbol": symbol, "marginType": margin_type.upper()}
