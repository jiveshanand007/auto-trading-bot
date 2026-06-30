from __future__ import annotations

from trading_bot.core.domain.order import MarginType, Side
from trading_bot.core.domain.portfolio import PortfolioState
from trading_bot.core.domain.position import Position
from trading_bot.core.domain.signal import Signal
from trading_bot.risk.manager import RiskManager


def _state(
    equity: float = 10000.0,
    positions: list[Position] | None = None,
    is_halted: bool = False,
    daily_start: float | None = None,
) -> PortfolioState:
    return PortfolioState(
        equity=equity,
        cash=equity,
        open_positions=positions or [],
        daily_start_equity=daily_start if daily_start is not None else equity,
        is_halted=is_halted,
    )


def _sig(
    qty: float = 0.001,
    entry: float = 100.0,
    sl: float = 98.0,
    tp: float = 104.0,
    side: Side = Side.BUY,
) -> Signal:
    return Signal(
        symbol="BTCUSDT", side=side, quantity=qty,
        entry_price=entry, stop_loss=sl, take_profit=tp, reason="test",
    )


def _pos() -> Position:
    return Position(
        symbol="BTCUSDT", side=Side.BUY, quantity=0.001, entry_price=100.0,
        leverage=1, liquidation_price=0.0, unrealized_pnl=0.0,
        margin_type=MarginType.ISOLATED,
    )


# --- Check 1: halted ---

def test_reject_when_portfolio_halted():
    rm = RiskManager()
    assert rm.validate(_sig(), _state(is_halted=True)) is None


def test_reject_when_risk_manager_internally_halted():
    rm = RiskManager()
    rm.halt()
    assert rm.validate(_sig(), _state()) is None


def test_reset_clears_internal_halt():
    rm = RiskManager()
    rm.halt()
    rm.reset()
    assert rm.validate(_sig(), _state()) is not None


# --- Check 2: max position size ---

def test_reject_oversized_position():
    rm = RiskManager(max_position_pct=0.20)
    assert rm.validate(_sig(qty=100.0, entry=100.0), _state(equity=10000.0)) is None


def test_accept_valid_position_size():
    rm = RiskManager(max_position_pct=0.20)
    assert rm.validate(_sig(qty=1.0, entry=100.0), _state(equity=10000.0)) is not None


# --- Check 3: max open positions ---

def test_reject_when_max_open_positions_reached():
    rm = RiskManager(max_open_positions=1)
    assert rm.validate(_sig(), _state(positions=[_pos()])) is None


def test_accept_when_below_max_open_positions():
    rm = RiskManager(max_open_positions=2)
    assert rm.validate(_sig(), _state(positions=[_pos()])) is not None


# --- Check 4: per-order USDT cap ---

def test_reject_order_exceeding_usdt_cap():
    rm = RiskManager(max_order_usdt=100.0)
    assert rm.validate(_sig(qty=5.0, entry=100.0), _state()) is None


def test_accept_order_within_usdt_cap():
    rm = RiskManager(max_order_usdt=200.0)
    assert rm.validate(_sig(qty=1.0, entry=100.0), _state()) is not None


# --- Check 5: SL/TP validity ---

def test_reject_buy_with_sl_above_entry():
    rm = RiskManager()
    assert rm.validate(_sig(entry=100.0, sl=102.0, tp=104.0, side=Side.BUY), _state()) is None


def test_reject_buy_with_tp_below_entry():
    rm = RiskManager()
    assert rm.validate(_sig(entry=100.0, sl=98.0, tp=99.0, side=Side.BUY), _state()) is None


def test_reject_sell_with_sl_below_entry():
    rm = RiskManager()
    assert rm.validate(_sig(entry=100.0, sl=98.0, tp=96.0, side=Side.SELL), _state()) is None


def test_reject_sell_with_tp_above_entry():
    rm = RiskManager()
    assert rm.validate(_sig(entry=100.0, sl=102.0, tp=101.0, side=Side.SELL), _state()) is None


def test_accept_valid_buy_sl_tp():
    rm = RiskManager()
    assert rm.validate(_sig(entry=100.0, sl=98.0, tp=104.0, side=Side.BUY), _state()) is not None


def test_accept_valid_sell_sl_tp():
    rm = RiskManager()
    assert rm.validate(
        _sig(entry=100.0, sl=102.0, tp=96.0, side=Side.SELL), _state()
    ) is not None


# --- Check 6: daily drawdown circuit breaker ---

def test_circuit_breaker_triggers_on_excess_drawdown():
    rm = RiskManager(max_daily_drawdown_pct=0.05)
    state = PortfolioState(
        equity=9400.0, cash=9400.0, open_positions=[],
        daily_start_equity=10000.0, is_halted=False,
    )
    assert rm.validate(_sig(), state) is None


def test_circuit_breaker_latches_internal_halt():
    rm = RiskManager(max_daily_drawdown_pct=0.05)
    bad_state = PortfolioState(
        equity=9400.0, cash=9400.0, open_positions=[],
        daily_start_equity=10000.0, is_halted=False,
    )
    rm.validate(_sig(), bad_state)
    assert rm.validate(_sig(), _state(equity=10000.0)) is None


def test_no_circuit_breaker_within_threshold():
    rm = RiskManager(max_daily_drawdown_pct=0.05)
    state = PortfolioState(
        equity=9600.0, cash=9600.0, open_positions=[],
        daily_start_equity=10000.0, is_halted=False,
    )
    assert rm.validate(_sig(), state) is not None


def test_validate_returns_signal_unchanged_when_approved():
    rm = RiskManager()
    sig = _sig()
    assert rm.validate(sig, _state()) == sig
