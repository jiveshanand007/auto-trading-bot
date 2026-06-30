from __future__ import annotations

from trading_bot.core.domain.order import Side
from trading_bot.core.domain.signal import Signal


def test_signal_construction():
    sig = Signal(
        symbol="BTCUSDT",
        side=Side.BUY,
        quantity=0.001,
        entry_price=100.0,
        stop_loss=98.0,
        take_profit=104.0,
        reason="test",
    )
    assert sig.symbol == "BTCUSDT"
    assert sig.side == Side.BUY
    assert sig.quantity == 0.001
    assert sig.stop_loss == 98.0


def test_signal_is_immutable():
    sig = Signal(
        symbol="BTCUSDT", side=Side.BUY, quantity=0.001,
        entry_price=100.0, stop_loss=98.0, take_profit=104.0, reason="test",
    )
    try:
        sig.symbol = "ETHUSDT"  # type: ignore[misc]
        raise AssertionError("should have raised FrozenInstanceError")
    except Exception:
        pass


def test_portfolio_state_construction():
    from trading_bot.core.domain.portfolio import PortfolioState

    state = PortfolioState(
        equity=10000.0,
        cash=10000.0,
        open_positions=[],
        daily_start_equity=10000.0,
        is_halted=False,
    )
    assert state.equity == 10000.0
    assert not state.is_halted
    assert state.open_positions == []
