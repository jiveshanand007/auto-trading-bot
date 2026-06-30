from __future__ import annotations

import pandas as pd

from trading_bot.backtest.result import BacktestResult
from trading_bot.backtest.simulated_broker import SimulatedBroker
from trading_bot.core.domain.order import MarginType
from trading_bot.core.domain.signal import Signal
from trading_bot.core.domain.trade import TradePlan, TradeStage
from trading_bot.market_data.types import Bar


def signal_to_plan(signal: Signal) -> TradePlan:
    """Wrap a Signal into a single-stage TradePlan."""
    return TradePlan(
        symbol=signal.symbol,
        side=signal.side,
        quantity=signal.quantity,
        initial_stop_loss=signal.stop_loss,
        stages=[TradeStage(take_profit=signal.take_profit, next_stop_loss=signal.stop_loss)],
        leverage=1,
        margin_type=MarginType.ISOLATED,
    )


def run_backtest(
    strategy: object,
    risk: object,
    broker: SimulatedBroker,
    bars: list[Bar],
) -> BacktestResult:
    """Chronological backtest loop — no look-ahead bias.

    Per bar order: advance_bar → portfolio_state → strategy.on_bar →
    risk.validate → place_trade (fills at next bar's open).
    """
    for bar in bars:
        broker.advance_bar(bar)
        portfolio = broker.portfolio_state()
        signal = strategy.on_bar(bar, portfolio)  # type: ignore[union-attr]
        if signal is not None:
            approved = risk.validate(signal, portfolio)  # type: ignore[union-attr]
            if approved is not None:
                broker.place_trade(signal_to_plan(approved))

    snapshots = broker.get_equity_snapshots()
    equity_curve = pd.Series(
        [eq for _, eq in snapshots],
        index=[ts for ts, _ in snapshots],
        name="equity",
    )
    return BacktestResult(
        strategy_name=strategy.name(),  # type: ignore[union-attr]
        symbol=bars[0].symbol if bars else "UNKNOWN",
        initial_capital=broker.initial_capital,
        trades=broker.get_closed_trades(),
        equity_curve=equity_curve,
    )
