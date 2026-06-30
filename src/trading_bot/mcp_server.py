from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from trading_bot.cli._broker_factory import make_futures_broker, make_spot_broker
from trading_bot.core.domain.order import MarginType, Side
from trading_bot.core.domain.trade import TradePlan, TradeStage
from trading_bot.exchanges.binance.common.errors import BrokerError

mcp = FastMCP("trading-bot")

_spot = make_spot_broker()
_futures = make_futures_broker()


@mcp.tool()
def place_spot_trade(
    symbol: str,
    side: str,
    quantity: float,
    stop_loss: float,
    take_profit: float,
) -> dict:
    """Place a spot order with stop-loss and take-profit (OCO).

    Example: place_spot_trade('BTCUSDT', 'BUY', 0.001, 95000, 105000)
    """
    plan = TradePlan(
        symbol=symbol, side=Side(side.upper()), quantity=quantity,
        initial_stop_loss=stop_loss,
        stages=[TradeStage(take_profit=take_profit, next_stop_loss=stop_loss)],
    )
    try:
        result = _spot.place_trade(plan)
        return {
            "symbol": result.plan.symbol,
            "side": result.plan.side.value,
            "entry_price": result.entry_price,
            "entry_order_id": result.entry_order_id,
            "sl_order_id": result.current_sl_order_id,
            "tp_order_id": result.current_tp_order_id,
        }
    except (BrokerError, ValueError) as e:
        return {"error": str(e)}


@mcp.tool()
def get_spot_orders(symbol: str = "") -> list:
    """Get open spot orders. Pass symbol like 'BTCUSDT' to filter."""
    try:
        return _spot.get_open_orders(symbol or None)
    except (BrokerError, ValueError) as e:
        return [{"error": str(e)}]


@mcp.tool()
def get_spot_balance() -> dict:
    """Get spot account balances for all non-zero assets."""
    try:
        return _spot.get_balance()
    except (BrokerError, ValueError) as e:
        return {"error": str(e)}


@mcp.tool()
def cancel_spot_order(symbol: str, order_id: int) -> dict:
    """Cancel an open spot order by symbol and order ID."""
    try:
        return _spot.cancel_order(symbol, order_id)
    except (BrokerError, ValueError) as e:
        return {"error": str(e)}


@mcp.tool()
def place_futures_trade(
    symbol: str,
    side: str,
    quantity: float,
    stop_loss: float,
    take_profit: float,
    leverage: int = 5,
    margin_type: str = "ISOLATED",
) -> dict:
    """Open a USDM futures position with stop-loss and take-profit.

    Example: place_futures_trade('BTCUSDT', 'BUY', 0.001, 95000, 105000, leverage=10)
    """
    plan = TradePlan(
        symbol=symbol, side=Side(side.upper()), quantity=quantity,
        initial_stop_loss=stop_loss,
        stages=[TradeStage(take_profit=take_profit, next_stop_loss=stop_loss)],
        leverage=leverage,
        margin_type=MarginType(margin_type.upper()),
    )
    try:
        result = _futures.place_trade(plan)
        return {
            "symbol": result.plan.symbol,
            "side": result.plan.side.value,
            "entry_price": result.entry_price,
            "entry_order_id": result.entry_order_id,
            "sl_order_id": result.current_sl_order_id,
            "tp_order_id": result.current_tp_order_id,
            "leverage": result.plan.leverage,
        }
    except (BrokerError, ValueError) as e:
        return {"error": str(e)}


@mcp.tool()
def get_futures_positions(symbol: str = "") -> list:
    """Get open futures positions. Pass symbol to filter, or leave empty for all."""
    try:
        positions = _futures.get_positions(symbol or None)
        return [
            {
                "symbol": p.symbol,
                "side": p.side.value,
                "quantity": p.quantity,
                "entry_price": p.entry_price,
                "leverage": p.leverage,
                "liquidation_price": p.liquidation_price,
                "unrealized_pnl": p.unrealized_pnl,
                "margin_type": p.margin_type.value,
            }
            for p in positions
        ]
    except (BrokerError, ValueError) as e:
        return [{"error": str(e)}]


@mcp.tool()
def get_futures_balance() -> dict:
    """Get futures account balance (available margin, total margin, unrealized PnL)."""
    try:
        return _futures.get_balance()
    except (BrokerError, ValueError) as e:
        return {"error": str(e)}


@mcp.tool()
def cancel_futures_order(symbol: str, order_id: int) -> dict:
    """Cancel an open futures order by symbol and order ID."""
    try:
        return _futures.cancel_order(symbol, order_id)
    except (BrokerError, ValueError) as e:
        return {"error": str(e)}


@mcp.tool()
def close_futures_position(symbol: str) -> dict:
    """Market-close an entire futures position."""
    try:
        return _futures.close_position(symbol)
    except (BrokerError, ValueError) as e:
        return {"error": str(e)}


if __name__ == "__main__":
    mcp.run()
