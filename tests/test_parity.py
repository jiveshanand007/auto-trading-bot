from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from trading_bot.backtest.engine import run_backtest
from trading_bot.backtest.simulated_broker import SimulatedBroker
from trading_bot.market_data.types import Bar, Timeframe
from trading_bot.risk.manager import RiskManager
from trading_bot.strategy.ma_crossover import MACrossoverStrategy


def _bar(close: float, bar_index: int) -> Bar:
    c = Decimal(str(close))
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(hours=bar_index)
    return Bar(
        symbol="BTCUSDT", timeframe=Timeframe.H1,
        open_time=t0, close_time=t0 + timedelta(hours=1),
        open=c, high=c + Decimal("2"), low=c - Decimal("2"),
        close=c, volume=Decimal("10"),
    )


def _make_bars() -> list[Bar]:
    prices = (
        [100.0, 99.0, 98.0, 97.0, 96.0, 95.0, 94.0, 93.0, 92.0, 91.0,
         90.0, 89.0, 88.0, 87.0, 86.0, 85.0, 84.0, 83.0, 82.0, 81.0,
         80.0, 79.0, 78.0]
        + [120.0] * 10
    )
    return [_bar(p, i) for i, p in enumerate(prices)]


def test_backtest_deterministic():
    bars = _make_bars()

    result1 = run_backtest(
        MACrossoverStrategy(fast=3, slow=5),
        RiskManager(),
        SimulatedBroker(initial_capital=10_000.0),
        bars,
    )
    result2 = run_backtest(
        MACrossoverStrategy(fast=3, slow=5),
        RiskManager(),
        SimulatedBroker(initial_capital=10_000.0),
        bars,
    )

    assert len(result1.trades) == len(result2.trades), "trade counts differ"
    for t1, t2 in zip(result1.trades, result2.trades, strict=True):
        assert t1.entry_price == t2.entry_price
        assert t1.exit_price == t2.exit_price
        assert t1.pnl == t2.pnl

    assert list(result1.equity_curve.values) == list(result2.equity_curve.values), (
        "equity curves differ between identical runs"
    )


def test_simulated_broker_no_exchange_import():
    path = Path("src/trading_bot/backtest/simulated_broker.py")
    import_lines = [
        line for line in path.read_text().splitlines()
        if line.strip().startswith(("import ", "from "))
    ]
    assert not any("trading_bot.exchanges" in line for line in import_lines), (
        "SimulatedBroker must never import from trading_bot.exchanges "
        "(breaks backtest/live parity)"
    )
