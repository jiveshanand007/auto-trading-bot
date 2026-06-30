from __future__ import annotations

from trading_bot.core.domain.order import Side
from trading_bot.core.domain.portfolio import PortfolioState
from trading_bot.core.domain.signal import Signal
from trading_bot.logging_config import get_logger

log = get_logger(__name__)


class RiskManager:
    def __init__(
        self,
        max_position_pct: float = 0.20,
        max_open_positions: int = 3,
        max_order_usdt: float = 1000.0,
        max_daily_drawdown_pct: float = 0.05,
    ) -> None:
        self._max_position_pct = max_position_pct
        self._max_open_positions = max_open_positions
        self._max_order_usdt = max_order_usdt
        self._max_daily_drawdown_pct = max_daily_drawdown_pct
        self._halted = False

    def halt(self) -> None:
        self._halted = True

    def reset(self) -> None:
        self._halted = False

    def validate(self, signal: Signal, state: PortfolioState) -> Signal | None:
        # Check 1: halted
        if state.is_halted or self._halted:
            log.info("risk_rejected", reason="halted", symbol=signal.symbol)
            return None

        notional = signal.quantity * signal.entry_price

        # Check 2: max position size
        if state.equity > 0 and notional > self._max_position_pct * state.equity:
            log.info("risk_rejected", reason="position_too_large", notional=notional)
            return None

        # Check 3: max open positions
        if len(state.open_positions) >= self._max_open_positions:
            log.info("risk_rejected", reason="max_positions_reached")
            return None

        # Check 4: per-order USDT cap
        if notional > self._max_order_usdt:
            log.info("risk_rejected", reason="order_exceeds_cap", notional=notional)
            return None

        # Check 5: SL/TP validity
        if signal.side == Side.BUY:
            valid = signal.stop_loss < signal.entry_price < signal.take_profit
        else:
            valid = signal.take_profit < signal.entry_price < signal.stop_loss
        if not valid:
            log.info("risk_rejected", reason="invalid_sl_tp", side=signal.side)
            return None

        # Check 6: daily drawdown circuit breaker
        if state.daily_start_equity > 0:
            drawdown = (state.daily_start_equity - state.equity) / state.daily_start_equity
            if drawdown > self._max_daily_drawdown_pct:
                self._halted = True
                log.warning("risk_circuit_breaker", drawdown_pct=drawdown * 100)
                return None

        return signal
