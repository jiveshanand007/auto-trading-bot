from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from trading_bot.backtest.result import ClosedTrade
from trading_bot.core.domain.order import Side
from trading_bot.core.domain.portfolio import PortfolioState
from trading_bot.core.domain.position import Position
from trading_bot.core.domain.trade import ActiveTrade, TradePlan, TradeStatus
from trading_bot.market_data.types import Bar


@dataclass
class _PendingEntry:
    plan: TradePlan
    order_id: int


@dataclass
class _OpenPos:
    plan: TradePlan
    entry_price: float
    entry_order_id: int
    entry_bar_index: int


class SimulatedBroker:
    """In-memory IBroker for backtesting. Must not import trading_bot.exchanges."""

    def __init__(
        self,
        initial_capital: float = 10_000.0,
        fee_rate: float = 0.001,
        slippage_rate: float = 0.0005,
    ) -> None:
        self._initial_capital = initial_capital
        self._cash = 0.0
        self._fee_rate = fee_rate
        self._slippage_rate = slippage_rate
        self._pending: list[_PendingEntry] = []
        self._open: list[_OpenPos] = []
        self._closed: list[ClosedTrade] = []
        self._equity_snapshots: list[tuple[datetime, float]] = []
        self._current_bar: Bar | None = None
        self._bar_index: int = -1
        self._order_id_counter: int = 0
        self._daily_start_equity: float = initial_capital
        self._current_day: object = None

    @property
    def initial_capital(self) -> float:
        return self._initial_capital

    # --- IBroker protocol ---

    def place_trade(self, plan: TradePlan) -> ActiveTrade:
        oid = self._next_id()
        self._pending.append(_PendingEntry(plan=plan, order_id=oid))
        return ActiveTrade(
            plan=plan, current_stage=0, entry_order_id=oid, entry_price=0.0,
            current_sl_order_id=oid + 1, current_tp_order_id=oid + 2,
            status=TradeStatus.OPEN,
        )

    def advance_stage(self, trade: ActiveTrade) -> ActiveTrade:
        if not trade.has_next_stage:
            return trade
        return ActiveTrade(
            plan=trade.plan, current_stage=trade.current_stage + 1,
            entry_order_id=trade.entry_order_id, entry_price=trade.entry_price,
            current_sl_order_id=self._next_id(), current_tp_order_id=self._next_id(),
            status=TradeStatus.OPEN,
        )

    def update_stop_loss(self, trade: ActiveTrade, new_sl: float) -> ActiveTrade:
        for pos in self._open:
            if pos.entry_order_id == trade.entry_order_id:
                pos.plan = TradePlan(
                    symbol=pos.plan.symbol, side=pos.plan.side,
                    quantity=pos.plan.quantity, initial_stop_loss=new_sl,
                    stages=pos.plan.stages, leverage=pos.plan.leverage,
                    margin_type=pos.plan.margin_type,
                )
        return trade

    def close_position(self, symbol: str) -> dict:
        price = float(self._current_bar.close) if self._current_bar else 0.0
        remaining = []
        for pos in self._open:
            if pos.plan.symbol == symbol:
                self._close_pos(pos, price)
            else:
                remaining.append(pos)
        self._open = remaining
        return {"symbol": symbol, "status": "closed"}

    def get_price(self, symbol: str) -> float:  # noqa: ARG002
        if self._current_bar is None:
            raise RuntimeError("No bar has been advanced yet")
        return float(self._current_bar.close)

    def get_open_orders(self, symbol: str | None = None) -> list[dict]:  # noqa: ARG002
        return []

    def get_balance(self) -> dict[str, dict]:
        return {"USDT": {"free": self._initial_capital + self._cash, "locked": 0.0}}

    def get_positions(self, symbol: str | None = None) -> list[Position]:
        price = float(self._current_bar.close) if self._current_bar else 0.0
        result = []
        for pos in self._open:
            if symbol is not None and pos.plan.symbol != symbol:
                continue
            upnl = self._unrealized(pos, price)
            result.append(Position(
                symbol=pos.plan.symbol, side=pos.plan.side,
                quantity=pos.plan.quantity, entry_price=pos.entry_price,
                leverage=pos.plan.leverage, liquidation_price=0.0,
                unrealized_pnl=upnl, margin_type=pos.plan.margin_type,
            ))
        return result

    def cancel_order(self, symbol: str, order_id: int) -> dict:  # noqa: ARG002
        return {}

    # --- backtest-specific API ---

    def advance_bar(self, bar: Bar) -> None:
        self._bar_index += 1
        self._current_bar = bar

        today = bar.open_time.date()
        if self._current_day is not None and self._current_day != today and self._equity_snapshots:
            self._daily_start_equity = self._equity_snapshots[-1][1]
        self._current_day = today

        bar_open = float(bar.open)
        bar_high = float(bar.high)
        bar_low = float(bar.low)

        for pending in self._pending:
            plan = pending.plan
            fill = bar_open * (1 + self._slippage_rate if plan.side == Side.BUY
                               else 1 - self._slippage_rate)
            self._cash -= self._fee_rate * fill * plan.quantity
            self._open.append(_OpenPos(
                plan=plan, entry_price=fill,
                entry_order_id=pending.order_id, entry_bar_index=self._bar_index,
            ))
        self._pending.clear()

        still_open = []
        for pos in self._open:
            sl = pos.plan.initial_stop_loss
            tp = pos.plan.stages[0].take_profit
            if pos.plan.side == Side.BUY:
                if bar_low <= sl:
                    self._close_pos(pos, sl)
                elif bar_high >= tp:
                    self._close_pos(pos, tp)
                else:
                    still_open.append(pos)
            else:
                if bar_high >= sl:
                    self._close_pos(pos, sl)
                elif bar_low <= tp:
                    self._close_pos(pos, tp)
                else:
                    still_open.append(pos)
        self._open = still_open

        self._equity_snapshots.append(
            (bar.open_time, self._compute_equity(float(bar.close)))
        )

    def portfolio_state(self) -> PortfolioState:
        price = float(self._current_bar.close) if self._current_bar else 0.0
        return PortfolioState(
            equity=self._compute_equity(price),
            cash=self._initial_capital + self._cash,
            open_positions=self.get_positions(),
            daily_start_equity=self._daily_start_equity,
            is_halted=False,
        )

    def get_closed_trades(self) -> list[ClosedTrade]:
        return list(self._closed)

    def get_equity_snapshots(self) -> list[tuple[datetime, float]]:
        return list(self._equity_snapshots)

    # --- internal helpers ---

    def _next_id(self) -> int:
        self._order_id_counter += 1
        return self._order_id_counter

    def _unrealized(self, pos: _OpenPos, price: float) -> float:
        if pos.plan.side == Side.BUY:
            return (price - pos.entry_price) * pos.plan.quantity
        return (pos.entry_price - price) * pos.plan.quantity

    def _compute_equity(self, price: float) -> float:
        return self._initial_capital + self._cash + sum(
            self._unrealized(p, price) for p in self._open
        )

    def _close_pos(self, pos: _OpenPos, raw_exit: float) -> None:
        if pos.plan.side == Side.BUY:
            exit_price = raw_exit * (1 - self._slippage_rate)
            realized = (exit_price - pos.entry_price) * pos.plan.quantity
        else:
            exit_price = raw_exit * (1 + self._slippage_rate)
            realized = (pos.entry_price - exit_price) * pos.plan.quantity
        exit_fee = self._fee_rate * exit_price * pos.plan.quantity
        net_pnl = realized - exit_fee
        self._cash += net_pnl
        self._closed.append(ClosedTrade(
            symbol=pos.plan.symbol, side=pos.plan.side,
            entry_price=pos.entry_price, exit_price=exit_price,
            quantity=pos.plan.quantity, pnl=net_pnl,
            entry_bar_index=pos.entry_bar_index, exit_bar_index=self._bar_index,
        ))
