from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from trading_bot.client import BinanceBroker, BrokerError

mcp = FastMCP("trading-bot")

_broker = BinanceBroker()


@mcp.tool()
def place_trade(
    symbol: str,
    side: str,
    quantity: float,
    stop_loss: float,
    take_profit: float,
) -> dict:
    """Place a market order with automatic stop-loss and take-profit (OCO).

    Example: place_trade('BTCUSDT', 'BUY', 0.001, 95000, 105000)
    """
    try:
        result = _broker.place_trade(symbol, side, quantity, stop_loss, take_profit)
        return asdict(result)
    except (BrokerError, ValueError) as e:
        return {"error": str(e)}


@mcp.tool()
def get_open_orders(symbol: str = "") -> list:
    """Get open orders. Pass symbol like 'BTCUSDT' to filter, or leave empty for all."""
    try:
        return _broker.get_open_orders(symbol or None)
    except (BrokerError, ValueError) as e:
        return [{"error": str(e)}]


@mcp.tool()
def get_balance() -> dict:
    """Get account balances for all non-zero assets."""
    try:
        return _broker.get_balance()
    except (BrokerError, ValueError) as e:
        return {"error": str(e)}


@mcp.tool()
def cancel_order(symbol: str, order_id: int) -> dict:
    """Cancel an open order by symbol and order ID."""
    try:
        return _broker.cancel_order(symbol, order_id)
    except (BrokerError, ValueError) as e:
        return {"error": str(e)}


if __name__ == "__main__":
    mcp.run()
