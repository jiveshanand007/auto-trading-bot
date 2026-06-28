from __future__ import annotations

import pytest

from trading_bot.core.domain.order import Side
from trading_bot.core.domain.trade import ActiveTrade, TradePlan, TradeStage, TradeStatus


def _plan(stages: list[tuple[float, float]]) -> TradePlan:
    return TradePlan(
        symbol="BTCUSDT",
        side=Side.BUY,
        quantity=0.001,
        initial_stop_loss=95000.0,
        stages=[TradeStage(take_profit=tp, next_stop_loss=sl) for tp, sl in stages],
    )


def _trade(plan: TradePlan, stage: int = 0) -> ActiveTrade:
    return ActiveTrade(
        plan=plan,
        current_stage=stage,
        entry_order_id=1,
        entry_price=100000.0,
        current_sl_order_id=10,
        current_tp_order_id=11,
        status=TradeStatus.OPEN,
    )


def test_current_stage_def_returns_correct_stage():
    plan = _plan([(105000.0, 100000.0), (110000.0, 106000.0)])
    trade = _trade(plan, stage=0)
    assert trade.current_stage_def.take_profit == 105000.0
    assert trade.current_stage_def.next_stop_loss == 100000.0


def test_has_next_stage_true_when_stages_remain():
    plan = _plan([(105000.0, 100000.0), (110000.0, 106000.0)])
    trade = _trade(plan, stage=0)
    assert trade.has_next_stage is True


def test_has_next_stage_false_on_last_stage():
    plan = _plan([(105000.0, 100000.0)])
    trade = _trade(plan, stage=0)
    assert trade.has_next_stage is False


def test_trade_plan_requires_at_least_one_stage():
    with pytest.raises(ValueError, match="at least one stage"):
        TradePlan(
            symbol="BTCUSDT",
            side=Side.BUY,
            quantity=0.001,
            initial_stop_loss=95000.0,
            stages=[],
        )
