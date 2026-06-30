# Futures Trading + SOLID Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor spot broker into a SOLID, ports-and-adapters architecture and add Binance USDM futures trading with staged SL/TP lifecycle.

**Architecture:** `core/` holds pure domain types and `IBroker` protocol; `exchanges/binance/` holds spot and futures adapters; `cli/` and `mcp_server.py` depend only on the protocol. No class mixes connection, validation, order-building, and execution.

**Tech Stack:** Python 3.10+, python-binance, pydantic-settings, typer, rich, structlog, pytest, uv

## Global Constraints

- All commands via `uv run` — never bare `python`
- Tests must pass with no network, no DB: `uv run pytest`
- Lint must pass: `uv run ruff check src/ tests/`
- `account_id` on every persisted table — do not remove
- Backtest/live parity: never fork strategy/risk logic per mode
- Coverage target: 80%+
- Commit after every task using `git commit -m "type: description"`

---

## File Map

**Create:**
```
src/trading_bot/core/__init__.py
src/trading_bot/core/domain/__init__.py
src/trading_bot/core/domain/order.py
src/trading_bot/core/domain/position.py
src/trading_bot/core/domain/trade.py
src/trading_bot/core/ports/__init__.py
src/trading_bot/core/ports/broker.py
src/trading_bot/core/ports/trade_store.py
src/trading_bot/exchanges/__init__.py
src/trading_bot/exchanges/binance/__init__.py
src/trading_bot/exchanges/binance/common/__init__.py
src/trading_bot/exchanges/binance/common/errors.py
src/trading_bot/exchanges/binance/common/auth.py
src/trading_bot/exchanges/binance/spot/__init__.py
src/trading_bot/exchanges/binance/spot/validator.py
src/trading_bot/exchanges/binance/spot/order_builder.py
src/trading_bot/exchanges/binance/spot/broker.py
src/trading_bot/exchanges/binance/futures/__init__.py
src/trading_bot/exchanges/binance/futures/validator.py
src/trading_bot/exchanges/binance/futures/order_builder.py
src/trading_bot/exchanges/binance/futures/broker.py
src/trading_bot/services/__init__.py
src/trading_bot/services/position_manager.py
src/trading_bot/cli/__init__.py
src/trading_bot/cli/_display.py
src/trading_bot/cli/_broker_factory.py
src/trading_bot/cli/trade_cli.py
src/trading_bot/cli/futures_cli.py
tests/core/__init__.py
tests/core/domain/__init__.py
tests/core/domain/test_trade.py
tests/exchanges/__init__.py
tests/exchanges/binance/__init__.py
tests/exchanges/binance/spot/__init__.py
tests/exchanges/binance/spot/test_validator.py
tests/exchanges/binance/spot/test_order_builder.py
tests/exchanges/binance/spot/test_spot_broker.py
tests/exchanges/binance/futures/__init__.py
tests/exchanges/binance/futures/test_validator.py
tests/exchanges/binance/futures/test_order_builder.py
tests/exchanges/binance/futures/test_futures_broker.py
tests/cli/__init__.py
tests/cli/test_trade_cli.py
tests/cli/test_futures_cli.py
migrations/versions/<auto>_extend_positions_add_trade_stages.py
```

**Modify:**
```
src/trading_bot/config.py               — add futures fields
src/trading_bot/client/__init__.py      — add SpotBroker alias
src/trading_bot/mcp_server.py          — add futures tools
src/trading_bot/db/models.py           — extend Position, add TradeStage model
pyproject.toml                          — update entry point to cli.trade_cli
tests/test_broker.py                    — update imports to SpotBroker
tests/test_cli.py                       — update imports to cli.trade_cli
```

---

## Task 1: Core Domain Types

**Files:**
- Create: `src/trading_bot/core/__init__.py` (empty)
- Create: `src/trading_bot/core/domain/__init__.py` (empty)
- Create: `src/trading_bot/core/domain/order.py`
- Create: `src/trading_bot/core/domain/position.py`
- Create: `src/trading_bot/core/domain/trade.py`
- Create: `src/trading_bot/core/ports/__init__.py` (empty)
- Create: `src/trading_bot/core/ports/broker.py`
- Create: `src/trading_bot/core/ports/trade_store.py`
- Test: `tests/core/domain/test_trade.py`

**Interfaces:**
- Produces: `Side`, `MarginType`, `TradeResult`, `Position`, `TradeStage`, `TradePlan`, `ActiveTrade`, `TradeStatus`, `IBroker`, `ITradeStore`

- [ ] **Step 1: Create package `__init__.py` files**

```bash
touch src/trading_bot/core/__init__.py \
      src/trading_bot/core/domain/__init__.py \
      src/trading_bot/core/ports/__init__.py \
      tests/core/__init__.py \
      tests/core/domain/__init__.py
```

- [ ] **Step 2: Write `core/domain/order.py`**

```python
# src/trading_bot/core/domain/order.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"
    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"


class MarginType(str, Enum):
    ISOLATED = "ISOLATED"
    CROSS = "CROSS"


@dataclass(frozen=True)
class TradeResult:
    symbol: str
    side: Side
    quantity: float
    entry_price: float
    entry_order_id: int
    stop_loss_order_id: int
    take_profit_order_id: int
    stop_loss: float
    take_profit: float
    raw_response: dict
```

- [ ] **Step 3: Write `core/domain/position.py`**

```python
# src/trading_bot/core/domain/position.py
from __future__ import annotations

from dataclasses import dataclass

from trading_bot.core.domain.order import MarginType, Side


@dataclass(frozen=True)
class Position:
    symbol: str
    side: Side
    quantity: float
    entry_price: float
    leverage: int
    liquidation_price: float
    unrealized_pnl: float
    margin_type: MarginType
```

- [ ] **Step 4: Write failing test for `ActiveTrade`**

```python
# tests/core/domain/test_trade.py
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
```

- [ ] **Step 5: Run test — verify it fails**

```bash
uv run pytest tests/core/domain/test_trade.py -v
```
Expected: `ModuleNotFoundError` or `ImportError` — `trade.py` doesn't exist yet.

- [ ] **Step 6: Write `core/domain/trade.py`**

```python
# src/trading_bot/core/domain/trade.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from trading_bot.core.domain.order import MarginType, Side


@dataclass(frozen=True)
class TradeStage:
    take_profit: float
    next_stop_loss: float


@dataclass(frozen=True)
class TradePlan:
    symbol: str
    side: Side
    quantity: float
    initial_stop_loss: float
    stages: list[TradeStage]
    leverage: int = 1
    margin_type: MarginType = MarginType.ISOLATED

    def __post_init__(self) -> None:
        if not self.stages:
            raise ValueError("TradePlan requires at least one stage")


class TradeStatus(str, Enum):
    OPEN = "OPEN"
    ADVANCING = "ADVANCING"
    CLOSED = "CLOSED"


@dataclass
class ActiveTrade:
    plan: TradePlan
    current_stage: int
    entry_order_id: int
    entry_price: float
    current_sl_order_id: int
    current_tp_order_id: int
    status: TradeStatus

    @property
    def current_stage_def(self) -> TradeStage:
        return self.plan.stages[self.current_stage]

    @property
    def has_next_stage(self) -> bool:
        return self.current_stage + 1 < len(self.plan.stages)
```

- [ ] **Step 7: Write `core/ports/broker.py`**

```python
# src/trading_bot/core/ports/broker.py
from __future__ import annotations

from typing import Protocol

from trading_bot.core.domain.position import Position
from trading_bot.core.domain.trade import ActiveTrade, TradePlan


class IBroker(Protocol):
    def place_trade(self, plan: TradePlan) -> ActiveTrade: ...
    def advance_stage(self, trade: ActiveTrade) -> ActiveTrade: ...
    def update_stop_loss(self, trade: ActiveTrade, new_sl: float) -> ActiveTrade: ...
    def close_position(self, symbol: str) -> dict: ...
    def get_price(self, symbol: str) -> float: ...
    def get_open_orders(self, symbol: str | None = None) -> list[dict]: ...
    def get_balance(self) -> dict[str, dict]: ...
    def get_positions(self, symbol: str | None = None) -> list[Position]: ...
    def cancel_order(self, symbol: str, order_id: int) -> dict: ...
```

- [ ] **Step 8: Write `core/ports/trade_store.py`**

```python
# src/trading_bot/core/ports/trade_store.py
from __future__ import annotations

from typing import Protocol

from trading_bot.core.domain.trade import ActiveTrade


class ITradeStore(Protocol):
    def save(self, trade: ActiveTrade) -> None: ...
    def get_active(self, symbol: str) -> ActiveTrade | None: ...
    def get_all_active(self) -> list[ActiveTrade]: ...
```

- [ ] **Step 9: Run tests — verify they pass**

```bash
uv run pytest tests/core/ -v
```
Expected: 4 passed.

- [ ] **Step 10: Lint**

```bash
uv run ruff check src/trading_bot/core/ tests/core/
```
Expected: no errors.

- [ ] **Step 11: Commit**

```bash
git add src/trading_bot/core/ tests/core/
git commit -m "feat(core): add domain types, IBroker and ITradeStore protocols"
```

---

## Task 2: Config Extension

**Files:**
- Modify: `src/trading_bot/config.py`

**Interfaces:**
- Produces: `Settings.futures_leverage`, `Settings.futures_margin_type`, `Settings.binance_futures_testnet`, `Settings.binance_futures_testnet_url`, `Settings.binance_futures_live_url`

- [ ] **Step 1: Write failing test**

```python
# tests/test_config.py  (create if not exists, otherwise append)
def test_futures_defaults():
    from trading_bot.config import Settings
    s = Settings()
    assert s.futures_leverage == 5
    assert s.futures_margin_type == "ISOLATED"
    assert s.binance_futures_testnet is True
    assert "fapi" in s.binance_futures_testnet_url
    assert "fapi" in s.binance_futures_live_url
```

- [ ] **Step 2: Run — verify it fails**

```bash
uv run pytest tests/test_config.py -v
```
Expected: `AttributeError` — fields don't exist yet.

- [ ] **Step 3: Add futures fields to `config.py`**

Open `src/trading_bot/config.py`. After the existing Binance fields, add:

```python
    # --- Binance Futures (USDM) ---
    futures_leverage: int = Field(default=5, description="Default leverage for futures trades (1–125).")
    futures_margin_type: str = Field(default="ISOLATED", description="Default margin type: ISOLATED or CROSS.")
    binance_futures_testnet: bool = Field(default=True, description="Use futures testnet endpoint.")
    binance_futures_testnet_url: str = Field(
        default="https://testnet.binancefuture.com/fapi",
        description="USDM futures testnet REST base URL.",
    )
    binance_futures_live_url: str = Field(
        default="https://fapi.binance.com/fapi",
        description="USDM futures live REST base URL.",
    )
```

- [ ] **Step 4: Run — verify it passes**

```bash
uv run pytest tests/test_config.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/trading_bot/config.py tests/test_config.py
git commit -m "feat(config): add USDM futures configuration fields"
```

---

## Task 3: Binance Common Layer

**Files:**
- Create: `src/trading_bot/exchanges/__init__.py` (empty)
- Create: `src/trading_bot/exchanges/binance/__init__.py` (empty)
- Create: `src/trading_bot/exchanges/binance/common/__init__.py` (empty)
- Create: `src/trading_bot/exchanges/binance/common/errors.py`
- Create: `src/trading_bot/exchanges/binance/common/auth.py`

**Interfaces:**
- Consumes: `Settings` from `trading_bot.config`
- Produces: `BrokerError`, `map_binance_error`, `make_spot_client`, `make_futures_client`

- [ ] **Step 1: Create `__init__.py` files**

```bash
touch src/trading_bot/exchanges/__init__.py \
      src/trading_bot/exchanges/binance/__init__.py \
      src/trading_bot/exchanges/binance/common/__init__.py \
      tests/exchanges/__init__.py \
      tests/exchanges/binance/__init__.py \
      tests/exchanges/binance/common/__init__.py
```

- [ ] **Step 2: Write `common/errors.py`**

```python
# src/trading_bot/exchanges/binance/common/errors.py
from __future__ import annotations

from binance.exceptions import BinanceAPIException, BinanceOrderException


class BrokerError(Exception):
    def __init__(
        self,
        message: str,
        code: int | None = None,
        original: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.original = original


def map_binance_error(exc: BinanceAPIException | BinanceOrderException) -> BrokerError:
    code = getattr(exc, "code", None)
    return BrokerError(str(exc), code=code, original=exc)
```

- [ ] **Step 3: Write `common/auth.py`**

```python
# src/trading_bot/exchanges/binance/common/auth.py
from __future__ import annotations

from binance.client import Client

from trading_bot.config import Settings


def make_spot_client(settings: Settings) -> Client:
    client = Client(settings.binance_api_key, settings.binance_api_secret)
    client.API_URL = (
        settings.binance_testnet_url if settings.binance_testnet else settings.binance_live_url
    )
    return client


def make_futures_client(settings: Settings) -> Client:
    client = Client(settings.binance_api_key, settings.binance_api_secret)
    client.API_URL = (
        settings.binance_futures_testnet_url
        if settings.binance_futures_testnet
        else settings.binance_futures_live_url
    )
    return client
```

- [ ] **Step 4: Write failing tests**

```python
# tests/exchanges/binance/common/test_errors.py
from __future__ import annotations

from unittest.mock import MagicMock

from binance.exceptions import BinanceAPIException

from trading_bot.exchanges.binance.common.errors import BrokerError, map_binance_error


def test_broker_error_stores_code_and_original():
    original = ValueError("boom")
    err = BrokerError("test", code=-1013, original=original)
    assert str(err) == "test"
    assert err.code == -1013
    assert err.original is original


def test_map_binance_error_extracts_code():
    exc = BinanceAPIException(MagicMock(status_code=400), 400, '{"code": -1013, "msg": "bad qty"}')
    result = map_binance_error(exc)
    assert isinstance(result, BrokerError)
    assert result.original is exc
```

- [ ] **Step 5: Run — verify they pass**

```bash
touch tests/exchanges/binance/common/__init__.py
uv run pytest tests/exchanges/binance/common/ -v
```
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/trading_bot/exchanges/ tests/exchanges/
git commit -m "feat(exchanges): add common BrokerError and client factory functions"
```

---

## Task 4: Spot Validator + Order Builder

**Files:**
- Create: `src/trading_bot/exchanges/binance/spot/__init__.py` (empty)
- Create: `src/trading_bot/exchanges/binance/spot/validator.py`
- Create: `src/trading_bot/exchanges/binance/spot/order_builder.py`
- Test: `tests/exchanges/binance/spot/test_validator.py`
- Test: `tests/exchanges/binance/spot/test_order_builder.py`

**Interfaces:**
- Consumes: `TradePlan`, `Side` from `core`
- Produces: `validate(plan, current_price) -> None`, `build_otoco(plan, working_price) -> dict`

- [ ] **Step 1: Write failing tests for validator**

```python
# tests/exchanges/binance/spot/__init__.py  (empty — create with touch)
# tests/exchanges/binance/spot/test_validator.py
from __future__ import annotations

import pytest

from trading_bot.core.domain.order import Side
from trading_bot.core.domain.trade import TradePlan, TradeStage
from trading_bot.exchanges.binance.spot.validator import validate


def _buy_plan(sl=95000.0, tp=105000.0) -> TradePlan:
    return TradePlan(
        symbol="BTCUSDT", side=Side.BUY, quantity=0.001,
        initial_stop_loss=sl, stages=[TradeStage(take_profit=tp, next_stop_loss=sl)],
    )


def _sell_plan(sl=105000.0, tp=95000.0) -> TradePlan:
    return TradePlan(
        symbol="BTCUSDT", side=Side.SELL, quantity=0.001,
        initial_stop_loss=sl, stages=[TradeStage(take_profit=tp, next_stop_loss=sl)],
    )


def test_valid_buy_passes():
    validate(_buy_plan(), current_price=100000.0)  # no exception


def test_valid_sell_passes():
    validate(_sell_plan(), current_price=100000.0)  # no exception


def test_buy_sl_above_price_raises():
    with pytest.raises(ValueError, match="BUY validation failed"):
        validate(_buy_plan(sl=105000.0, tp=110000.0), current_price=100000.0)


def test_buy_tp_below_price_raises():
    with pytest.raises(ValueError, match="BUY validation failed"):
        validate(_buy_plan(sl=90000.0, tp=99000.0), current_price=100000.0)


def test_sell_sl_below_price_raises():
    with pytest.raises(ValueError, match="SELL validation failed"):
        validate(_sell_plan(sl=95000.0, tp=90000.0), current_price=100000.0)
```

- [ ] **Step 2: Run — verify they fail**

```bash
touch tests/exchanges/binance/spot/__init__.py
uv run pytest tests/exchanges/binance/spot/test_validator.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `spot/validator.py`**

```python
# src/trading_bot/exchanges/binance/spot/validator.py
from __future__ import annotations

from trading_bot.core.domain.order import Side
from trading_bot.core.domain.trade import TradePlan


def validate(plan: TradePlan, current_price: float) -> None:
    sl = plan.initial_stop_loss
    tp = plan.stages[0].take_profit

    if plan.side == Side.BUY:
        if not (sl < current_price < tp):
            raise ValueError(
                f"BUY validation failed: stop_loss={sl} must be < "
                f"current_price={current_price} < take_profit={tp}"
            )
    else:
        if not (tp < current_price < sl):
            raise ValueError(
                f"SELL validation failed: take_profit={tp} must be < "
                f"current_price={current_price} < stop_loss={sl}"
            )
```

- [ ] **Step 4: Run validator tests — verify they pass**

```bash
uv run pytest tests/exchanges/binance/spot/test_validator.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Write failing tests for order builder**

```python
# tests/exchanges/binance/spot/test_order_builder.py
from __future__ import annotations

from trading_bot.core.domain.order import Side
from trading_bot.core.domain.trade import TradePlan, TradeStage
from trading_bot.exchanges.binance.spot.order_builder import build_otoco


def _plan(side: Side) -> TradePlan:
    sl, tp = (95000.0, 105000.0) if side == Side.BUY else (105000.0, 95000.0)
    return TradePlan(
        symbol="BTCUSDT", side=side, quantity=0.001,
        initial_stop_loss=sl, stages=[TradeStage(take_profit=tp, next_stop_loss=sl)],
    )


def test_buy_otoco_working_side():
    payload = build_otoco(_plan(Side.BUY), working_price=100100.0)
    assert payload["workingSide"] == "BUY"
    assert payload["pendingSide"] == "SELL"


def test_sell_otoco_working_side():
    payload = build_otoco(_plan(Side.SELL), working_price=99900.0)
    assert payload["workingSide"] == "SELL"
    assert payload["pendingSide"] == "BUY"


def test_buy_otoco_has_required_keys():
    payload = build_otoco(_plan(Side.BUY), working_price=100100.0)
    for key in ("symbol", "workingType", "workingPrice", "workingQuantity",
                "pendingAboveType", "pendingAbovePrice",
                "pendingBelowType", "pendingBelowStopPrice"):
        assert key in payload, f"missing key: {key}"


def test_buy_otoco_prices_are_strings():
    payload = build_otoco(_plan(Side.BUY), working_price=100100.0)
    assert isinstance(payload["workingPrice"], str)
    assert isinstance(payload["pendingAbovePrice"], str)
```

- [ ] **Step 6: Write `spot/order_builder.py`**

```python
# src/trading_bot/exchanges/binance/spot/order_builder.py
from __future__ import annotations

from trading_bot.core.domain.order import Side
from trading_bot.core.domain.trade import TradePlan


def build_otoco(plan: TradePlan, working_price: float) -> dict:
    sl = plan.initial_stop_loss
    tp = plan.stages[0].take_profit
    qty = str(plan.quantity)

    if plan.side == Side.BUY:
        return {
            "symbol": plan.symbol,
            "workingType": "LIMIT",
            "workingSide": "BUY",
            "workingPrice": str(working_price),
            "workingQuantity": qty,
            "workingTimeInForce": "GTC",
            "pendingSide": "SELL",
            "pendingQuantity": qty,
            "pendingAboveType": "LIMIT_MAKER",
            "pendingAbovePrice": str(tp),
            "pendingBelowType": "STOP_LOSS_LIMIT",
            "pendingBelowStopPrice": str(sl),
            "pendingBelowPrice": str(round(sl * 0.999, 2)),
            "pendingBelowTimeInForce": "GTC",
        }
    return {
        "symbol": plan.symbol,
        "workingType": "LIMIT",
        "workingSide": "SELL",
        "workingPrice": str(working_price),
        "workingQuantity": qty,
        "workingTimeInForce": "GTC",
        "pendingSide": "BUY",
        "pendingQuantity": qty,
        "pendingAboveType": "STOP_LOSS_LIMIT",
        "pendingAboveStopPrice": str(sl),
        "pendingAbovePrice": str(round(sl * 1.001, 2)),
        "pendingAboveTimeInForce": "GTC",
        "pendingBelowType": "LIMIT_MAKER",
        "pendingBelowPrice": str(tp),
    }
```

- [ ] **Step 7: Run all spot unit tests**

```bash
uv run pytest tests/exchanges/binance/spot/ -v
```
Expected: 9 passed.

- [ ] **Step 8: Commit**

```bash
git add src/trading_bot/exchanges/binance/spot/ tests/exchanges/binance/spot/
git commit -m "feat(spot): add validator and order_builder pure functions"
```

---

## Task 5: SpotBroker (refactor BinanceBroker)

**Files:**
- Create: `src/trading_bot/exchanges/binance/spot/broker.py`
- Modify: `src/trading_bot/client/__init__.py` — add `SpotBroker` alias
- Modify: `tests/test_broker.py` — verify existing tests still pass
- Test: `tests/exchanges/binance/spot/test_spot_broker.py`

**Interfaces:**
- Consumes: `TradePlan`, `IBroker`, `BrokerError`, `map_binance_error`, `make_spot_client`, `validate`, `build_otoco`
- Produces: `SpotBroker` implementing `IBroker` protocol

- [ ] **Step 1: Write failing tests for SpotBroker**

```python
# tests/exchanges/binance/spot/test_spot_broker.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from binance.exceptions import BinanceAPIException

from trading_bot.core.domain.order import Side
from trading_bot.core.domain.trade import ActiveTrade, TradePlan, TradeStage, TradeStatus
from trading_bot.exchanges.binance.common.errors import BrokerError
from trading_bot.exchanges.binance.spot.broker import SpotBroker

_PATCH = "trading_bot.exchanges.binance.spot.broker.Client"


def _make_broker(mock_client: MagicMock) -> SpotBroker:
    with patch(_PATCH, return_value=mock_client):
        return SpotBroker()


def _fake_client() -> MagicMock:
    return MagicMock()


def _buy_plan() -> TradePlan:
    return TradePlan(
        symbol="BTCUSDT", side=Side.BUY, quantity=0.001,
        initial_stop_loss=95000.0,
        stages=[TradeStage(take_profit=105000.0, next_stop_loss=100000.0)],
    )


def _otoco_response() -> dict:
    return {
        "orderListId": 999,
        "orderReports": [
            {"orderId": 1, "status": "FILLED", "fills": [{"qty": "0.001", "price": "100000.0"}]},
            {"orderId": 2, "status": "PENDING_NEW"},
            {"orderId": 3, "status": "PENDING_NEW"},
        ],
    }


def test_place_trade_returns_active_trade():
    client = _fake_client()
    client.get_symbol_ticker.return_value = {"price": "100000.0"}
    client._post.return_value = _otoco_response()

    broker = _make_broker(client)
    result = broker.place_trade(_buy_plan())

    assert isinstance(result, ActiveTrade)
    assert result.plan.symbol == "BTCUSDT"
    assert result.entry_order_id == 1
    assert result.current_tp_order_id == 2
    assert result.current_sl_order_id == 3
    assert result.status == TradeStatus.OPEN
    assert result.entry_price == pytest.approx(100000.0)


def test_place_trade_api_error_raises_broker_error():
    client = _fake_client()
    client.get_symbol_ticker.return_value = {"price": "100000.0"}
    exc = BinanceAPIException(MagicMock(status_code=400), 400, '{"code": -1013, "msg": "bad"}')
    client._post.side_effect = exc

    broker = _make_broker(client)
    with pytest.raises(BrokerError) as exc_info:
        broker.place_trade(_buy_plan())
    assert exc_info.value.original is exc


def test_get_price_returns_float():
    client = _fake_client()
    client.get_symbol_ticker.return_value = {"price": "100000.5"}
    broker = _make_broker(client)
    assert broker.get_price("BTCUSDT") == pytest.approx(100000.5)


def test_get_balance_filters_zero_balances():
    client = _fake_client()
    client.get_account.return_value = {
        "balances": [
            {"asset": "BTC", "free": "0.5", "locked": "0.0"},
            {"asset": "ETH", "free": "0.0", "locked": "0.0"},
        ]
    }
    broker = _make_broker(client)
    result = broker.get_balance()
    assert "BTC" in result
    assert "ETH" not in result


def test_get_positions_returns_empty_list():
    broker = _make_broker(_fake_client())
    assert broker.get_positions() == []


def test_cancel_order_delegates_to_client():
    client = _fake_client()
    client.cancel_order.return_value = {"orderId": 77, "status": "CANCELED"}
    broker = _make_broker(client)
    result = broker.cancel_order("BTCUSDT", 77)
    assert result["status"] == "CANCELED"
    client.cancel_order.assert_called_once_with(symbol="BTCUSDT", orderId=77)


def test_advance_stage_cancels_and_replaces_orders():
    client = _fake_client()
    client.get_symbol_ticker.return_value = {"price": "100000.0"}

    broker = _make_broker(client)
    plan = TradePlan(
        symbol="BTCUSDT", side=Side.BUY, quantity=0.001,
        initial_stop_loss=95000.0,
        stages=[
            TradeStage(take_profit=105000.0, next_stop_loss=100000.0),
            TradeStage(take_profit=110000.0, next_stop_loss=106000.0),
        ],
    )
    trade = ActiveTrade(
        plan=plan, current_stage=0, entry_order_id=1, entry_price=100000.0,
        current_sl_order_id=3, current_tp_order_id=2, status=TradeStatus.OPEN,
    )

    client.cancel_order.return_value = {"status": "CANCELED"}
    client.create_order.return_value = {"orderId": 10, "status": "NEW"}

    updated = broker.advance_stage(trade)

    assert updated.current_stage == 1
    assert updated.status == TradeStatus.OPEN
    client.cancel_order.assert_called()
```

- [ ] **Step 2: Run — verify they fail**

```bash
uv run pytest tests/exchanges/binance/spot/test_spot_broker.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `spot/broker.py`**

```python
# src/trading_bot/exchanges/binance/spot/broker.py
from __future__ import annotations

import time

import structlog
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException

from trading_bot.config import Settings, get_settings
from trading_bot.core.domain.order import Side
from trading_bot.core.domain.position import Position
from trading_bot.core.domain.trade import ActiveTrade, TradePlan, TradeStatus
from trading_bot.exchanges.binance.common.auth import make_spot_client
from trading_bot.exchanges.binance.common.errors import BrokerError, map_binance_error
from trading_bot.exchanges.binance.spot.order_builder import build_otoco
from trading_bot.exchanges.binance.spot.validator import validate

log = structlog.get_logger(__name__)

_FILL_RETRIES = 10
_FILL_SLEEP = 0.5


class SpotBroker:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client: Client = make_spot_client(self._settings)

    def get_price(self, symbol: str) -> float:
        try:
            return float(self._client.get_symbol_ticker(symbol=symbol)["price"])
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

    def place_trade(self, plan: TradePlan) -> ActiveTrade:
        current_price = self.get_price(plan.symbol)
        validate(plan, current_price)

        if plan.side == Side.BUY:
            working_price = round(current_price * 1.001, 2)
        else:
            working_price = round(current_price * 0.999, 2)

        payload = build_otoco(plan, working_price)
        try:
            resp = self._client._post("orderList/otoco", True, data=payload)
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

        reports = resp.get("orderReports", [])
        working = reports[0] if reports else {}
        entry_order_id = working.get("orderId", 0)

        fills = working.get("fills", [])
        if fills:
            total_qty = sum(float(f["qty"]) for f in fills)
            total_val = sum(float(f["price"]) * float(f["qty"]) for f in fills)
            entry_price = total_val / total_qty
        else:
            entry_price = self._poll_fill_price(plan.symbol, entry_order_id)

        if plan.side == Side.BUY:
            tp_order_id = reports[1].get("orderId", 0) if len(reports) > 1 else 0
            sl_order_id = reports[2].get("orderId", 0) if len(reports) > 2 else 0
        else:
            sl_order_id = reports[1].get("orderId", 0) if len(reports) > 1 else 0
            tp_order_id = reports[2].get("orderId", 0) if len(reports) > 2 else 0

        return ActiveTrade(
            plan=plan,
            current_stage=0,
            entry_order_id=entry_order_id,
            entry_price=entry_price,
            current_sl_order_id=sl_order_id,
            current_tp_order_id=tp_order_id,
            status=TradeStatus.OPEN,
        )

    def advance_stage(self, trade: ActiveTrade) -> ActiveTrade:
        if not trade.has_next_stage:
            raise BrokerError("No next stage available for this trade")

        trade.status = TradeStatus.ADVANCING
        current = trade.current_stage_def
        next_stage = trade.plan.stages[trade.current_stage + 1]
        side_str = "SELL" if trade.plan.side == Side.BUY else "BUY"

        try:
            self._client.cancel_order(
                symbol=trade.plan.symbol, orderId=trade.current_sl_order_id
            )
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

        new_sl = current.next_stop_loss
        new_tp = next_stage.take_profit

        try:
            sl_resp = self._client.create_order(
                symbol=trade.plan.symbol,
                side=side_str,
                type="STOP_LOSS_LIMIT",
                quantity=str(trade.plan.quantity),
                price=str(round(new_sl * (0.999 if trade.plan.side == Side.BUY else 1.001), 2)),
                stopPrice=str(new_sl),
                timeInForce="GTC",
            )
            tp_resp = self._client.create_order(
                symbol=trade.plan.symbol,
                side=side_str,
                type="LIMIT_MAKER",
                quantity=str(trade.plan.quantity),
                price=str(new_tp),
            )
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

        trade.current_sl_order_id = sl_resp["orderId"]
        trade.current_tp_order_id = tp_resp["orderId"]
        trade.current_stage += 1
        trade.status = TradeStatus.OPEN
        return trade

    def update_stop_loss(self, trade: ActiveTrade, new_sl: float) -> ActiveTrade:
        side_str = "SELL" if trade.plan.side == Side.BUY else "BUY"
        try:
            self._client.cancel_order(
                symbol=trade.plan.symbol, orderId=trade.current_sl_order_id
            )
            sl_resp = self._client.create_order(
                symbol=trade.plan.symbol,
                side=side_str,
                type="STOP_LOSS_LIMIT",
                quantity=str(trade.plan.quantity),
                price=str(round(new_sl * (0.999 if trade.plan.side == Side.BUY else 1.001), 2)),
                stopPrice=str(new_sl),
                timeInForce="GTC",
            )
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

        trade.current_sl_order_id = sl_resp["orderId"]
        return trade

    def close_position(self, symbol: str) -> dict:
        raise NotImplementedError("close_position not implemented for spot; cancel open orders manually")

    def get_open_orders(self, symbol: str | None = None) -> list[dict]:
        try:
            if symbol is not None:
                return self._client.get_open_orders(symbol=symbol)
            return self._client.get_open_orders()
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

    def get_balance(self) -> dict[str, dict]:
        try:
            balances = self._client.get_account()["balances"]
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc
        return {
            b["asset"]: {"free": b["free"], "locked": b["locked"]}
            for b in balances
            if float(b["free"]) > 0 or float(b["locked"]) > 0
        }

    def get_positions(self, symbol: str | None = None) -> list[Position]:
        return []

    def cancel_order(self, symbol: str, order_id: int) -> dict:
        try:
            return self._client.cancel_order(symbol=symbol, orderId=order_id)
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

    def _poll_fill_price(self, symbol: str, order_id: int) -> float:
        try:
            for _ in range(_FILL_RETRIES):
                status = self._client.get_order(symbol=symbol, orderId=order_id)
                if status["status"] == "FILLED":
                    return float(status.get("avgPrice") or status.get("price", 0))
                time.sleep(_FILL_SLEEP)
        except (BinanceAPIException, BinanceOrderException) as exc:
            log.warning("could not poll fill price", error=str(exc))
        return 0.0
```

- [ ] **Step 4: Run SpotBroker tests**

```bash
uv run pytest tests/exchanges/binance/spot/test_spot_broker.py -v
```
Expected: 7 passed.

- [ ] **Step 5: Add `SpotBroker` alias to `client/__init__.py`**

Open `src/trading_bot/client/__init__.py` and add the import:

```python
from trading_bot.exchanges.binance.spot.broker import SpotBroker

__all__ = [..., "SpotBroker"]  # add SpotBroker to existing __all__
```

- [ ] **Step 6: Run existing broker tests — they must still pass**

```bash
uv run pytest tests/test_broker.py -v
```
Expected: all existing tests pass.

- [ ] **Step 7: Run full suite**

```bash
uv run pytest -q
```
Expected: no regressions.

- [ ] **Step 8: Commit**

```bash
git add src/trading_bot/exchanges/binance/spot/broker.py \
        src/trading_bot/client/__init__.py \
        tests/exchanges/binance/spot/test_spot_broker.py
git commit -m "feat(spot): add SpotBroker implementing IBroker; backward-compat alias in client/"
```

---

## Task 6: Futures Validator + Order Builder

**Files:**
- Create: `src/trading_bot/exchanges/binance/futures/__init__.py` (empty)
- Create: `src/trading_bot/exchanges/binance/futures/validator.py`
- Create: `src/trading_bot/exchanges/binance/futures/order_builder.py`
- Test: `tests/exchanges/binance/futures/test_validator.py`
- Test: `tests/exchanges/binance/futures/test_order_builder.py`

**Interfaces:**
- Consumes: `TradePlan`, `Side`
- Produces: `validate(plan, current_price) -> None`, `build_entry`, `build_stop_market`, `build_take_profit_market`, `build_set_leverage`, `build_set_margin_type`

- [ ] **Step 1: Create `__init__.py` files**

```bash
touch src/trading_bot/exchanges/binance/futures/__init__.py \
      tests/exchanges/binance/futures/__init__.py
```

- [ ] **Step 2: Write failing tests for futures validator**

```python
# tests/exchanges/binance/futures/test_validator.py
from __future__ import annotations

import pytest

from trading_bot.core.domain.order import Side
from trading_bot.core.domain.trade import TradePlan, TradeStage
from trading_bot.exchanges.binance.futures.validator import validate


def _plan(side=Side.BUY, sl=95000.0, tp=105000.0, qty=0.001, leverage=5) -> TradePlan:
    return TradePlan(
        symbol="BTCUSDT", side=side, quantity=qty,
        initial_stop_loss=sl,
        stages=[TradeStage(take_profit=tp, next_stop_loss=sl)],
        leverage=leverage,
    )


def test_valid_long_passes():
    validate(_plan(), current_price=100000.0)


def test_valid_short_passes():
    validate(_plan(side=Side.SELL, sl=105000.0, tp=95000.0), current_price=100000.0)


def test_leverage_zero_raises():
    with pytest.raises(ValueError, match="leverage"):
        validate(_plan(leverage=0), current_price=100000.0)


def test_leverage_above_125_raises():
    with pytest.raises(ValueError, match="leverage"):
        validate(_plan(leverage=126), current_price=100000.0)


def test_buy_sl_above_price_raises():
    with pytest.raises(ValueError, match="BUY validation failed"):
        validate(_plan(sl=105000.0, tp=110000.0), current_price=100000.0)


def test_sell_sl_below_price_raises():
    with pytest.raises(ValueError, match="SELL validation failed"):
        validate(_plan(side=Side.SELL, sl=95000.0, tp=90000.0), current_price=100000.0)


def test_min_notional_too_small_raises():
    with pytest.raises(ValueError, match="notional"):
        validate(_plan(qty=0.00001), current_price=100000.0)
```

- [ ] **Step 3: Write failing tests for futures order builder**

```python
# tests/exchanges/binance/futures/test_order_builder.py
from __future__ import annotations

from trading_bot.core.domain.order import Side
from trading_bot.exchanges.binance.futures.order_builder import (
    build_entry,
    build_set_leverage,
    build_set_margin_type,
    build_stop_market,
    build_take_profit_market,
)


def test_entry_buy_payload():
    payload = build_entry("BTCUSDT", Side.BUY, 0.001)
    assert payload["side"] == "BUY"
    assert payload["type"] == "MARKET"
    assert payload["quantity"] == "0.001"
    assert payload["symbol"] == "BTCUSDT"


def test_stop_market_has_close_position():
    payload = build_stop_market("BTCUSDT", Side.SELL, 95000.0)
    assert payload["type"] == "STOP_MARKET"
    assert payload["closePosition"] == "true"
    assert payload["stopPrice"] == "95000.0"


def test_take_profit_market_has_close_position():
    payload = build_take_profit_market("BTCUSDT", Side.SELL, 105000.0)
    assert payload["type"] == "TAKE_PROFIT_MARKET"
    assert payload["closePosition"] == "true"


def test_set_leverage_payload():
    payload = build_set_leverage("BTCUSDT", 10)
    assert payload["symbol"] == "BTCUSDT"
    assert payload["leverage"] == 10


def test_set_margin_type_payload():
    payload = build_set_margin_type("BTCUSDT", "ISOLATED")
    assert payload["symbol"] == "BTCUSDT"
    assert payload["marginType"] == "ISOLATED"
```

- [ ] **Step 4: Run — verify they fail**

```bash
uv run pytest tests/exchanges/binance/futures/ -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 5: Write `futures/validator.py`**

```python
# src/trading_bot/exchanges/binance/futures/validator.py
from __future__ import annotations

from trading_bot.core.domain.order import Side
from trading_bot.core.domain.trade import TradePlan

_MIN_NOTIONAL = 5.0
_MAX_LEVERAGE = 125


def validate(plan: TradePlan, current_price: float) -> None:
    if not (1 <= plan.leverage <= _MAX_LEVERAGE):
        raise ValueError(f"leverage must be 1–{_MAX_LEVERAGE}, got {plan.leverage}")

    notional = plan.quantity * current_price
    if notional < _MIN_NOTIONAL:
        raise ValueError(
            f"Order notional {notional:.4f} USDT is below minimum {_MIN_NOTIONAL} USDT"
        )

    sl = plan.initial_stop_loss
    tp = plan.stages[0].take_profit

    if plan.side == Side.BUY:
        if not (sl < current_price < tp):
            raise ValueError(
                f"BUY validation failed: stop_loss={sl} must be < "
                f"current_price={current_price} < take_profit={tp}"
            )
    else:
        if not (tp < current_price < sl):
            raise ValueError(
                f"SELL validation failed: take_profit={tp} must be < "
                f"current_price={current_price} < stop_loss={sl}"
            )
```

- [ ] **Step 6: Write `futures/order_builder.py`**

```python
# src/trading_bot/exchanges/binance/futures/order_builder.py
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
```

- [ ] **Step 7: Run all futures unit tests**

```bash
uv run pytest tests/exchanges/binance/futures/ -v
```
Expected: 12 passed.

- [ ] **Step 8: Commit**

```bash
git add src/trading_bot/exchanges/binance/futures/ tests/exchanges/binance/futures/
git commit -m "feat(futures): add validator and order_builder pure functions"
```

---

## Task 7: FuturesBroker

**Files:**
- Create: `src/trading_bot/exchanges/binance/futures/broker.py`
- Test: `tests/exchanges/binance/futures/test_futures_broker.py`

**Interfaces:**
- Consumes: `IBroker`, `TradePlan`, `make_futures_client`, all `futures/order_builder` functions, `BrokerError`, `map_binance_error`
- Produces: `FuturesBroker` implementing `IBroker` protocol

- [ ] **Step 1: Write failing tests**

```python
# tests/exchanges/binance/futures/test_futures_broker.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from binance.exceptions import BinanceAPIException

from trading_bot.core.domain.order import MarginType, Side
from trading_bot.core.domain.position import Position
from trading_bot.core.domain.trade import ActiveTrade, TradePlan, TradeStage, TradeStatus
from trading_bot.exchanges.binance.common.errors import BrokerError
from trading_bot.exchanges.binance.futures.broker import FuturesBroker

_PATCH = "trading_bot.exchanges.binance.futures.broker.Client"


def _make_broker(mock_client: MagicMock) -> FuturesBroker:
    with patch(_PATCH, return_value=mock_client):
        return FuturesBroker()


def _fake_client() -> MagicMock:
    return MagicMock()


def _buy_plan(stages=None) -> TradePlan:
    if stages is None:
        stages = [TradeStage(take_profit=105000.0, next_stop_loss=100000.0)]
    return TradePlan(
        symbol="BTCUSDT", side=Side.BUY, quantity=0.001,
        initial_stop_loss=95000.0, stages=stages, leverage=5,
    )


def _entry_response(order_id: int = 1) -> dict:
    return {"orderId": order_id, "status": "FILLED", "avgPrice": "100000.0"}


def _order_response(order_id: int) -> dict:
    return {"orderId": order_id, "status": "NEW"}


def test_place_trade_returns_active_trade():
    client = _fake_client()
    client.futures_symbol_ticker.return_value = {"price": "100000.0"}
    client.futures_create_order.side_effect = [
        _entry_response(1),
        _order_response(2),
        _order_response(3),
    ]

    broker = _make_broker(client)
    result = broker.place_trade(_buy_plan())

    assert isinstance(result, ActiveTrade)
    assert result.entry_order_id == 1
    assert result.current_sl_order_id == 2
    assert result.current_tp_order_id == 3
    assert result.status == TradeStatus.OPEN
    assert result.entry_price == pytest.approx(100000.0)


def test_place_trade_sets_leverage_and_margin_type():
    client = _fake_client()
    client.futures_symbol_ticker.return_value = {"price": "100000.0"}
    client.futures_create_order.side_effect = [
        _entry_response(1), _order_response(2), _order_response(3)
    ]

    broker = _make_broker(client)
    broker.place_trade(_buy_plan())

    client.futures_change_leverage.assert_called_once_with(symbol="BTCUSDT", leverage=5)
    client.futures_change_margin_type.assert_called_once()


def test_place_trade_api_error_raises_broker_error():
    client = _fake_client()
    client.futures_symbol_ticker.return_value = {"price": "100000.0"}
    exc = BinanceAPIException(MagicMock(status_code=400), 400, '{"code": -1013, "msg": "bad"}')
    client.futures_create_order.side_effect = exc

    broker = _make_broker(client)
    with pytest.raises(BrokerError):
        broker.place_trade(_buy_plan())


def test_advance_stage_cancels_and_replaces():
    client = _fake_client()
    client.futures_cancel_order.return_value = {"status": "CANCELED"}
    client.futures_create_order.side_effect = [_order_response(10), _order_response(11)]

    broker = _make_broker(client)
    plan = _buy_plan(stages=[
        TradeStage(take_profit=105000.0, next_stop_loss=100000.0),
        TradeStage(take_profit=110000.0, next_stop_loss=106000.0),
    ])
    trade = ActiveTrade(
        plan=plan, current_stage=0, entry_order_id=1, entry_price=100000.0,
        current_sl_order_id=2, current_tp_order_id=3, status=TradeStatus.OPEN,
    )

    updated = broker.advance_stage(trade)

    assert updated.current_stage == 1
    assert updated.current_sl_order_id == 10
    assert updated.current_tp_order_id == 11
    assert updated.status == TradeStatus.OPEN
    assert client.futures_cancel_order.call_count == 2


def test_advance_stage_no_next_raises():
    client = _fake_client()
    broker = _make_broker(client)
    plan = _buy_plan()
    trade = ActiveTrade(
        plan=plan, current_stage=0, entry_order_id=1, entry_price=100000.0,
        current_sl_order_id=2, current_tp_order_id=3, status=TradeStatus.OPEN,
    )
    with pytest.raises(BrokerError, match="No next stage"):
        broker.advance_stage(trade)


def test_get_balance_returns_futures_account():
    client = _fake_client()
    client.futures_account.return_value = {
        "availableBalance": "1000.0",
        "totalMarginBalance": "1100.0",
        "totalUnrealizedProfit": "100.0",
    }
    broker = _make_broker(client)
    result = broker.get_balance()
    assert result["availableBalance"] == "1000.0"


def test_get_positions_maps_to_position_objects():
    client = _fake_client()
    client.futures_position_information.return_value = [
        {
            "symbol": "BTCUSDT",
            "positionAmt": "0.001",
            "entryPrice": "100000.0",
            "leverage": "5",
            "liquidationPrice": "80000.0",
            "unrealizedProfit": "50.0",
            "marginType": "isolated",
        },
        {"symbol": "ETHUSDT", "positionAmt": "0.0"},
    ]
    broker = _make_broker(client)
    positions = broker.get_positions()
    assert len(positions) == 1
    assert positions[0].symbol == "BTCUSDT"
    assert isinstance(positions[0], Position)


def test_get_positions_filtered_by_symbol():
    client = _fake_client()
    client.futures_position_information.return_value = []
    broker = _make_broker(client)
    broker.get_positions(symbol="BTCUSDT")
    client.futures_position_information.assert_called_once_with(symbol="BTCUSDT")
```

- [ ] **Step 2: Run — verify they fail**

```bash
uv run pytest tests/exchanges/binance/futures/test_futures_broker.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `futures/broker.py`**

```python
# src/trading_bot/exchanges/binance/futures/broker.py
from __future__ import annotations

import time

import structlog
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException

from trading_bot.config import Settings, get_settings
from trading_bot.core.domain.order import MarginType, Side
from trading_bot.core.domain.position import Position
from trading_bot.core.domain.trade import ActiveTrade, TradePlan, TradeStatus
from trading_bot.exchanges.binance.common.auth import make_futures_client
from trading_bot.exchanges.binance.common.errors import BrokerError, map_binance_error
from trading_bot.exchanges.binance.futures.order_builder import (
    build_entry,
    build_set_leverage,
    build_set_margin_type,
    build_stop_market,
    build_take_profit_market,
)
from trading_bot.exchanges.binance.futures.validator import validate

log = structlog.get_logger(__name__)

_FILL_RETRIES = 10
_FILL_SLEEP = 0.5
_MARGIN_NO_CHANGE_CODE = -4046


class FuturesBroker:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client: Client = make_futures_client(self._settings)

    def get_price(self, symbol: str) -> float:
        try:
            return float(self._client.futures_symbol_ticker(symbol=symbol)["price"])
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

    def place_trade(self, plan: TradePlan) -> ActiveTrade:
        current_price = self.get_price(plan.symbol)
        validate(plan, current_price)
        self._configure_symbol(plan)

        exit_side = Side.SELL if plan.side == Side.BUY else Side.BUY

        try:
            entry_resp = self._client.futures_create_order(
                **build_entry(plan.symbol, plan.side, plan.quantity)
            )
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

        entry_order_id = entry_resp["orderId"]
        entry_price = self._resolve_entry_price(entry_resp, plan.symbol, entry_order_id)

        try:
            sl_resp = self._client.futures_create_order(
                **build_stop_market(plan.symbol, exit_side, plan.initial_stop_loss)
            )
            tp_resp = self._client.futures_create_order(
                **build_take_profit_market(plan.symbol, exit_side, plan.stages[0].take_profit)
            )
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

        return ActiveTrade(
            plan=plan,
            current_stage=0,
            entry_order_id=entry_order_id,
            entry_price=entry_price,
            current_sl_order_id=sl_resp["orderId"],
            current_tp_order_id=tp_resp["orderId"],
            status=TradeStatus.OPEN,
        )

    def advance_stage(self, trade: ActiveTrade) -> ActiveTrade:
        if not trade.has_next_stage:
            raise BrokerError("No next stage available for this trade")

        trade.status = TradeStatus.ADVANCING
        current = trade.current_stage_def
        next_stage = trade.plan.stages[trade.current_stage + 1]
        exit_side = Side.SELL if trade.plan.side == Side.BUY else Side.BUY

        try:
            self._cancel_order_safe(trade.plan.symbol, trade.current_sl_order_id)
            self._cancel_order_safe(trade.plan.symbol, trade.current_tp_order_id)

            sl_resp = self._client.futures_create_order(
                **build_stop_market(trade.plan.symbol, exit_side, current.next_stop_loss)
            )
            tp_resp = self._client.futures_create_order(
                **build_take_profit_market(trade.plan.symbol, exit_side, next_stage.take_profit)
            )
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

        trade.current_sl_order_id = sl_resp["orderId"]
        trade.current_tp_order_id = tp_resp["orderId"]
        trade.current_stage += 1
        trade.status = TradeStatus.OPEN
        return trade

    def update_stop_loss(self, trade: ActiveTrade, new_sl: float) -> ActiveTrade:
        exit_side = Side.SELL if trade.plan.side == Side.BUY else Side.BUY
        try:
            self._cancel_order_safe(trade.plan.symbol, trade.current_sl_order_id)
            sl_resp = self._client.futures_create_order(
                **build_stop_market(trade.plan.symbol, exit_side, new_sl)
            )
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

        trade.current_sl_order_id = sl_resp["orderId"]
        return trade

    def close_position(self, symbol: str) -> dict:
        try:
            positions = self._client.futures_position_information(symbol=symbol)
            pos = next((p for p in positions if float(p.get("positionAmt", 0)) != 0), None)
            if pos is None:
                return {"msg": "no open position"}
            amt = float(pos["positionAmt"])
            close_side = "SELL" if amt > 0 else "BUY"
            return self._client.futures_create_order(
                symbol=symbol,
                side=close_side,
                type="MARKET",
                quantity=str(abs(amt)),
                reduceOnly="true",
            )
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

    def get_open_orders(self, symbol: str | None = None) -> list[dict]:
        try:
            if symbol is not None:
                return self._client.futures_get_open_orders(symbol=symbol)
            return self._client.futures_get_open_orders()
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

    def get_balance(self) -> dict[str, dict]:
        try:
            return self._client.futures_account()
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

    def get_positions(self, symbol: str | None = None) -> list[Position]:
        try:
            kwargs = {"symbol": symbol} if symbol else {}
            raw = self._client.futures_position_information(**kwargs)
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

        result = []
        for p in raw:
            if float(p.get("positionAmt", 0)) == 0:
                continue
            amt = float(p["positionAmt"])
            side = Side.BUY if amt > 0 else Side.SELL
            margin_type = (
                MarginType.ISOLATED if p.get("marginType", "").lower() == "isolated"
                else MarginType.CROSS
            )
            result.append(Position(
                symbol=p["symbol"],
                side=side,
                quantity=abs(amt),
                entry_price=float(p.get("entryPrice", 0)),
                leverage=int(p.get("leverage", 1)),
                liquidation_price=float(p.get("liquidationPrice", 0)),
                unrealized_pnl=float(p.get("unrealizedProfit", 0)),
                margin_type=margin_type,
            ))
        return result

    def cancel_order(self, symbol: str, order_id: int) -> dict:
        try:
            return self._client.futures_cancel_order(symbol=symbol, orderId=order_id)
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc

    def _configure_symbol(self, plan: TradePlan) -> None:
        try:
            self._client.futures_change_leverage(symbol=plan.symbol, leverage=plan.leverage)
        except (BinanceAPIException, BinanceOrderException) as exc:
            raise map_binance_error(exc) from exc
        try:
            self._client.futures_change_margin_type(
                **build_set_margin_type(plan.symbol, plan.margin_type.value)
            )
        except BinanceAPIException as exc:
            if getattr(exc, "code", None) == _MARGIN_NO_CHANGE_CODE:
                return
            raise map_binance_error(exc) from exc

    def _cancel_order_safe(self, symbol: str, order_id: int) -> None:
        try:
            self._client.futures_cancel_order(symbol=symbol, orderId=order_id)
        except BinanceAPIException as exc:
            if getattr(exc, "code", None) == -2011:
                log.debug("order already gone, skipping cancel", order_id=order_id)
                return
            raise map_binance_error(exc) from exc

    def _resolve_entry_price(self, entry_resp: dict, symbol: str, order_id: int) -> float:
        avg = entry_resp.get("avgPrice")
        if avg and float(avg) > 0:
            return float(avg)
        try:
            for _ in range(_FILL_RETRIES):
                status = self._client.futures_get_order(symbol=symbol, orderId=order_id)
                if status["status"] == "FILLED":
                    return float(status.get("avgPrice") or status.get("price", 0))
                time.sleep(_FILL_SLEEP)
        except (BinanceAPIException, BinanceOrderException) as exc:
            log.warning("could not poll futures fill price", error=str(exc))
        return 0.0
```

- [ ] **Step 4: Run futures broker tests**

```bash
uv run pytest tests/exchanges/binance/futures/test_futures_broker.py -v
```
Expected: 8 passed.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest -q
```
Expected: no regressions.

- [ ] **Step 6: Commit**

```bash
git add src/trading_bot/exchanges/binance/futures/broker.py \
        tests/exchanges/binance/futures/test_futures_broker.py
git commit -m "feat(futures): add FuturesBroker implementing IBroker"
```

---

## Task 8: CLI Refactor — Shared Display, Factory, Fix Spot CLI

**Files:**
- Create: `src/trading_bot/cli/__init__.py` (empty)
- Create: `src/trading_bot/cli/_display.py`
- Create: `src/trading_bot/cli/_broker_factory.py`
- Create: `src/trading_bot/cli/trade_cli.py` (moved + fixed from `src/trading_bot/trade_cli.py`)
- Modify: `src/trading_bot/trade_cli.py` — replace with backward-compat shim
- Modify: `pyproject.toml` — update entry point
- Modify: `tests/test_cli.py` — update import paths

**Interfaces:**
- Consumes: `IBroker`, `SpotBroker`, `FuturesBroker`, `Settings`
- Produces: `print_trade_preview`, `print_active_trade`, `print_orders_table`, `print_balance_table`, `print_positions_table`, `make_spot_broker`, `make_futures_broker`

- [ ] **Step 1: Create `cli/__init__.py` and test package**

```bash
touch src/trading_bot/cli/__init__.py tests/cli/__init__.py
```

- [ ] **Step 2: Write `cli/_display.py`**

```python
# src/trading_bot/cli/_display.py
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from trading_bot.core.domain.order import Side
from trading_bot.core.domain.position import Position
from trading_bot.core.domain.trade import ActiveTrade, TradePlan

console = Console()
err_console = Console(stderr=True)


def _fmt(val: float, decimals: int = 2, prefix: str = "") -> str:
    return f"{prefix}{val:,.{decimals}f}"


def print_trade_preview(
    current_price: float | None,
    balances: dict,
    plan: TradePlan,
) -> None:
    color = "green" if plan.side == Side.BUY else "red"
    side_str = plan.side.value
    info = Table.grid(padding=(0, 2))
    info.add_column(style="bold dim")
    info.add_column()
    if current_price is not None:
        info.add_row("Market price", f"[bold]{_fmt(current_price, 2, '$')}[/bold]")
        info.add_row("", "")
    base = plan.symbol.replace("USDT", "").replace("BUSD", "")
    quote = "USDT" if "USDT" in plan.symbol else "BUSD"
    for asset in (quote, base):
        b = balances.get(asset, {})
        free = b.get("free", "0") if isinstance(b, dict) else str(b)
        locked = b.get("locked", "0") if isinstance(b, dict) else "0"
        info.add_row(
            f"Balance {asset}",
            f"{free} free  /  {locked} locked" if float(locked) > 0 else f"[bold]{free}[/bold] free",
        )
    info.add_row("", "")
    info.add_row("Side", f"[bold {color}]{side_str}[/bold {color}]")
    info.add_row("Symbol", plan.symbol)
    info.add_row("Quantity", str(plan.quantity))
    if current_price is not None:
        notional = current_price * plan.quantity
        info.add_row("Notional value", f"~{_fmt(notional, 2, '$')}")
        info.add_row("", "")
        sl = plan.initial_stop_loss
        tp = plan.stages[0].take_profit
        sl_dist = abs(current_price - sl)
        tp_dist = abs(tp - current_price)
        sl_pct = sl_dist / current_price * 100
        tp_pct = tp_dist / current_price * 100
        sl_dollars = sl_dist * plan.quantity
        tp_dollars = tp_dist * plan.quantity
        rr = tp_dist / sl_dist if sl_dist else 0
        info.add_row(
            "Stop loss",
            f"[red]{_fmt(sl, 2, '$')}[/red]  ([red]-{sl_pct:.2f}%[/red]  risk [red]-{_fmt(sl_dollars, 2, '$')}[/red])",
        )
        info.add_row(
            "Take profit",
            f"[green]{_fmt(tp, 2, '$')}[/green]  ([green]+{tp_pct:.2f}%[/green]  reward [green]+{_fmt(tp_dollars, 2, '$')}[/green])",
        )
        rr_color = "green" if rr >= 1.5 else "yellow" if rr >= 1.0 else "red"
        info.add_row("Risk : Reward", f"[{rr_color}]1 : {rr:.2f}[/{rr_color}]")
    if plan.leverage > 1:
        info.add_row("Leverage", f"{plan.leverage}x")
        info.add_row("Margin type", plan.margin_type.value)
    console.print(
        Panel(
            info,
            title=f"[bold {color}] {side_str} {plan.symbol} — PRE-TRADE SUMMARY [/bold {color}]",
            border_style=color,
            padding=(1, 2),
        )
    )


def print_active_trade(trade: ActiveTrade) -> None:
    color = "green" if trade.plan.side == Side.BUY else "red"
    t = Table(show_header=True, header_style="bold cyan", title="Trade Confirmed")
    t.add_column("Field")
    t.add_column("Value")
    t.add_row("Symbol", trade.plan.symbol)
    t.add_row("Side", trade.plan.side.value)
    t.add_row("Quantity", str(trade.plan.quantity))
    t.add_row("Entry Price", _fmt(trade.entry_price, 2, "$"))
    t.add_row("Stop Loss", _fmt(trade.plan.initial_stop_loss, 2, "$"))
    t.add_row("Take Profit", _fmt(trade.current_stage_def.take_profit, 2, "$"))
    t.add_row("Stage", f"{trade.current_stage + 1} / {len(trade.plan.stages)}")
    t.add_row("Entry Order ID", str(trade.entry_order_id))
    t.add_row("SL Order ID", str(trade.current_sl_order_id))
    t.add_row("TP Order ID", str(trade.current_tp_order_id))
    console.print(t)
    console.print("[bold green]✓ Trade placed successfully[/bold green]")


def print_orders_table(orders: list[dict]) -> None:
    if not orders:
        console.print("[dim]No open orders.[/dim]")
        return
    t = Table(show_header=True, header_style="bold cyan", title="Open Orders")
    for col in ("Symbol", "Order ID", "Side", "Type", "Price", "Qty", "Status"):
        t.add_column(col)
    for o in orders:
        side = o.get("side", "")
        color = "green" if side == "BUY" else "red"
        t.add_row(
            o.get("symbol", ""), str(o.get("orderId", "")),
            f"[{color}]{side}[/{color}]", o.get("type", ""),
            o.get("price", ""), o.get("origQty", ""), o.get("status", ""),
        )
    console.print(t)


def print_balance_table(balances: dict) -> None:
    if not balances:
        console.print("[dim]No non-zero balances.[/dim]")
        return
    t = Table(show_header=True, header_style="bold cyan", title="Account Balance")
    t.add_column("Asset")
    t.add_column("Free", justify="right")
    t.add_column("Locked", justify="right")
    for asset, amounts in sorted(balances.items()):
        if isinstance(amounts, dict):
            t.add_row(asset, str(amounts.get("free", "")), str(amounts.get("locked", "")))
        else:
            t.add_row(asset, str(amounts), "—")
    console.print(t)


def print_positions_table(positions: list[Position]) -> None:
    if not positions:
        console.print("[dim]No open positions.[/dim]")
        return
    t = Table(show_header=True, header_style="bold cyan", title="Open Positions")
    for col in ("Symbol", "Side", "Qty", "Entry", "Liq Price", "PnL", "Leverage", "Margin"):
        t.add_column(col)
    for p in positions:
        color = "green" if p.side == Side.BUY else "red"
        pnl_color = "green" if p.unrealized_pnl >= 0 else "red"
        t.add_row(
            p.symbol,
            f"[{color}]{p.side.value}[/{color}]",
            str(p.quantity),
            _fmt(p.entry_price, 2, "$"),
            _fmt(p.liquidation_price, 2, "$"),
            f"[{pnl_color}]{_fmt(p.unrealized_pnl, 2, '$')}[/{pnl_color}]",
            f"{p.leverage}x",
            p.margin_type.value,
        )
    console.print(t)
```

- [ ] **Step 3: Write `cli/_broker_factory.py`**

```python
# src/trading_bot/cli/_broker_factory.py
from __future__ import annotations

from trading_bot.config import get_settings
from trading_bot.exchanges.binance.futures.broker import FuturesBroker
from trading_bot.exchanges.binance.spot.broker import SpotBroker


def make_spot_broker() -> SpotBroker:
    return SpotBroker(get_settings())


def make_futures_broker() -> FuturesBroker:
    return FuturesBroker(get_settings())
```

- [ ] **Step 4: Write `cli/trade_cli.py`**

Key fix: replace `broker._client.get_symbol_ticker(...)` with `broker.get_price(...)`.

```python
# src/trading_bot/cli/trade_cli.py
from __future__ import annotations

import contextlib
import sys

import typer

from trading_bot.cli._broker_factory import make_spot_broker
from trading_bot.cli._display import (
    console,
    err_console,
    print_active_trade,
    print_balance_table,
    print_orders_table,
    print_trade_preview,
)
from trading_bot.core.domain.order import Side
from trading_bot.core.domain.trade import TradePlan, TradeStage

app = typer.Typer(help="Spot trading — place and manage trades on Binance.")


def _die(msg: str) -> None:
    err_console.print(f"[bold red]Error:[/bold red] {msg}")
    sys.exit(1)


def _confirm(yes: bool) -> None:
    if yes:
        return
    answer = typer.prompt("Proceed with trade? [y/N]", default="N")
    if answer.strip().lower() not in ("y", "yes"):
        console.print("[dim]Trade cancelled.[/dim]")
        raise typer.Exit()


def _build_plan(symbol, side, quantity, sl, tp) -> TradePlan:
    return TradePlan(
        symbol=symbol, side=side, quantity=quantity,
        initial_stop_loss=sl,
        stages=[TradeStage(take_profit=tp, next_stop_loss=sl)],
    )


@app.command()
def buy(
    symbol: str = typer.Argument(..., help="Trading pair, e.g. BTCUSDT"),
    quantity: float = typer.Argument(..., help="Quantity to buy"),
    sl: float = typer.Option(..., "--sl", help="Stop-loss price"),
    tp: float = typer.Option(..., "--tp", help="Take-profit price"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Place a spot BUY with stop-loss / take-profit."""
    broker = make_spot_broker()
    plan = _build_plan(symbol, Side.BUY, quantity, sl, tp)
    price, balances = None, {}
    with contextlib.suppress(Exception):
        price = broker.get_price(symbol)
    with contextlib.suppress(Exception):
        balances = broker.get_balance()
    print_trade_preview(price, balances, plan)
    _confirm(yes)
    try:
        result = broker.place_trade(plan)
    except Exception as exc:
        _die(str(exc))
    print_active_trade(result)


@app.command()
def sell(
    symbol: str = typer.Argument(..., help="Trading pair, e.g. BTCUSDT"),
    quantity: float = typer.Argument(..., help="Quantity to sell"),
    sl: float = typer.Option(..., "--sl", help="Stop-loss price"),
    tp: float = typer.Option(..., "--tp", help="Take-profit price"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Place a spot SELL with stop-loss / take-profit."""
    broker = make_spot_broker()
    plan = _build_plan(symbol, Side.SELL, quantity, sl, tp)
    price, balances = None, {}
    with contextlib.suppress(Exception):
        price = broker.get_price(symbol)
    with contextlib.suppress(Exception):
        balances = broker.get_balance()
    print_trade_preview(price, balances, plan)
    _confirm(yes)
    try:
        result = broker.place_trade(plan)
    except Exception as exc:
        _die(str(exc))
    print_active_trade(result)


@app.command()
def orders(
    symbol: str | None = typer.Argument(None, help="Filter by trading pair"),
) -> None:
    """List open spot orders."""
    try:
        open_orders = make_spot_broker().get_open_orders(symbol=symbol)
    except Exception as exc:
        _die(str(exc))
    print_orders_table(open_orders)


@app.command()
def balance() -> None:
    """Show spot account balances."""
    try:
        balances = make_spot_broker().get_balance()
    except Exception as exc:
        _die(str(exc))
    print_balance_table(balances)


@app.command()
def cancel(
    symbol: str = typer.Argument(..., help="Trading pair, e.g. BTCUSDT"),
    order_id: int = typer.Argument(..., help="Order ID to cancel"),
) -> None:
    """Cancel an open spot order."""
    try:
        make_spot_broker().cancel_order(symbol, order_id)
    except Exception as exc:
        _die(str(exc))
    console.print(Panel(f"Order [bold]{order_id}[/bold] on [bold]{symbol}[/bold] cancelled.", style="green"))


if __name__ == "__main__":
    app()
```

Note: `Panel` import missing — add `from rich.panel import Panel` to imports in the cancel command or top of file.

- [ ] **Step 5: Replace `src/trading_bot/trade_cli.py` with backward-compat shim**

```python
# src/trading_bot/trade_cli.py
# Backward-compat shim — entry point moved to trading_bot.cli.trade_cli
from trading_bot.cli.trade_cli import app  # noqa: F401
```

- [ ] **Step 6: Update `pyproject.toml` entry point**

Open `pyproject.toml`. Change:
```toml
[project.scripts]
trade = "trading_bot.trade_cli:app"
```
to:
```toml
[project.scripts]
trade = "trading_bot.cli.trade_cli:app"
```

- [ ] **Step 7: Update `tests/test_cli.py` imports**

Open `tests/test_cli.py`. Update imports and patch target:

```python
# Change:
from trading_bot.client.binance_client import BrokerError, TradeResult
from trading_bot.trade_cli import app

# To:
from trading_bot.exchanges.binance.common.errors import BrokerError
from trading_bot.cli.trade_cli import app
from trading_bot.core.domain.order import Side
from trading_bot.core.domain.trade import ActiveTrade, TradePlan, TradeStage, TradeStatus
```

Replace `_trade_result` helper with an `ActiveTrade` factory:

```python
def _active_trade(side: str = "BUY") -> ActiveTrade:
    s = Side(side)
    sl, tp = (95000.0, 105000.0) if s == Side.BUY else (105000.0, 95000.0)
    plan = TradePlan(
        symbol="BTCUSDT", side=s, quantity=0.001,
        initial_stop_loss=sl,
        stages=[TradeStage(take_profit=tp, next_stop_loss=sl)],
    )
    return ActiveTrade(
        plan=plan, current_stage=0, entry_order_id=1, entry_price=100000.0,
        current_sl_order_id=10, current_tp_order_id=11, status=TradeStatus.OPEN,
    )
```

Update mock patch target from `BinanceBroker` to `make_spot_broker`:
```python
_PATCH_BROKER = "trading_bot.cli.trade_cli.make_spot_broker"
# In tests: patch(_PATCH_BROKER, return_value=mock_broker)
```

Update `mock_broker.place_trade.return_value` to use `_active_trade(...)`.

- [ ] **Step 8: Reinstall and run full suite**

```bash
uv sync && uv run pytest -q
```
Expected: all tests pass.

- [ ] **Step 9: Smoke test CLI**

```bash
uv run trade --help
```
Expected: shows buy, sell, orders, balance, cancel commands.

- [ ] **Step 10: Commit**

```bash
git add src/trading_bot/cli/ src/trading_bot/trade_cli.py \
        pyproject.toml tests/test_cli.py
git commit -m "refactor(cli): extract display/factory, fix broker._client leak, move to cli/"
```

---

## Task 9: Futures CLI

**Files:**
- Create: `src/trading_bot/cli/futures_cli.py`
- Modify: `src/trading_bot/cli/trade_cli.py` — register futures subapp
- Test: `tests/cli/test_futures_cli.py`

**Interfaces:**
- Consumes: `FuturesBroker`, `make_futures_broker`, `TradePlan`, `TradeStage`, all `_display` functions
- Produces: `futures_app` typer subapp with commands: buy, sell, positions, orders, balance, cancel, close

- [ ] **Step 1: Write failing tests**

```python
# tests/cli/test_futures_cli.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from trading_bot.cli.trade_cli import app
from trading_bot.core.domain.order import MarginType, Side
from trading_bot.core.domain.position import Position
from trading_bot.core.domain.trade import ActiveTrade, TradePlan, TradeStage, TradeStatus

runner = CliRunner()
_PATCH = "trading_bot.cli.futures_cli.make_futures_broker"


def _active_trade() -> ActiveTrade:
    plan = TradePlan(
        symbol="BTCUSDT", side=Side.BUY, quantity=0.001,
        initial_stop_loss=95000.0,
        stages=[TradeStage(take_profit=105000.0, next_stop_loss=100000.0)],
        leverage=5,
    )
    return ActiveTrade(
        plan=plan, current_stage=0, entry_order_id=1, entry_price=100000.0,
        current_sl_order_id=2, current_tp_order_id=3, status=TradeStatus.OPEN,
    )


def test_futures_buy_success():
    mock_broker = MagicMock()
    mock_broker.get_price.return_value = 100000.0
    mock_broker.get_balance.return_value = {}
    mock_broker.place_trade.return_value = _active_trade()

    with patch(_PATCH, return_value=mock_broker):
        result = runner.invoke(
            app,
            ["futures", "buy", "BTCUSDT", "0.001", "--sl", "95000", "--tp", "105000", "--yes"],
        )
    assert result.exit_code == 0
    mock_broker.place_trade.assert_called_once()


def test_futures_sell_success():
    mock_broker = MagicMock()
    mock_broker.get_price.return_value = 100000.0
    mock_broker.get_balance.return_value = {}
    mock_broker.place_trade.return_value = _active_trade()

    with patch(_PATCH, return_value=mock_broker):
        result = runner.invoke(
            app,
            ["futures", "sell", "BTCUSDT", "0.001", "--sl", "105000", "--tp", "95000", "--yes"],
        )
    assert result.exit_code == 0


def test_futures_positions_command():
    mock_broker = MagicMock()
    mock_broker.get_positions.return_value = [
        Position("BTCUSDT", Side.BUY, 0.001, 100000.0, 5, 80000.0, 50.0, MarginType.ISOLATED)
    ]

    with patch(_PATCH, return_value=mock_broker):
        result = runner.invoke(app, ["futures", "positions"])
    assert result.exit_code == 0


def test_futures_balance_command():
    mock_broker = MagicMock()
    mock_broker.get_balance.return_value = {"availableBalance": "1000.0"}

    with patch(_PATCH, return_value=mock_broker):
        result = runner.invoke(app, ["futures", "balance"])
    assert result.exit_code == 0


def test_futures_multistage_buy():
    mock_broker = MagicMock()
    mock_broker.get_price.return_value = 100000.0
    mock_broker.get_balance.return_value = {}
    mock_broker.place_trade.return_value = _active_trade()

    with patch(_PATCH, return_value=mock_broker):
        result = runner.invoke(
            app,
            [
                "futures", "buy", "BTCUSDT", "0.001",
                "--sl", "95000",
                "--tp", "102000", "--next-sl", "99000",
                "--tp", "108000", "--next-sl", "104000",
                "--tp", "115000",
                "--yes",
            ],
        )
    assert result.exit_code == 0
    call_plan = mock_broker.place_trade.call_args[0][0]
    assert len(call_plan.stages) == 3
```

- [ ] **Step 2: Run — verify they fail**

```bash
uv run pytest tests/cli/test_futures_cli.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `cli/futures_cli.py`**

```python
# src/trading_bot/cli/futures_cli.py
from __future__ import annotations

import contextlib
import sys

import typer

from trading_bot.cli._broker_factory import make_futures_broker
from trading_bot.cli._display import (
    console,
    err_console,
    print_active_trade,
    print_balance_table,
    print_orders_table,
    print_positions_table,
    print_trade_preview,
)
from trading_bot.config import get_settings
from trading_bot.core.domain.order import MarginType, Side
from trading_bot.core.domain.trade import TradePlan, TradeStage

futures_app = typer.Typer(help="USDM futures trading — Binance perpetuals.")


def _die(msg: str) -> None:
    err_console.print(f"[bold red]Error:[/bold red] {msg}")
    sys.exit(1)


def _confirm(yes: bool) -> None:
    if yes:
        return
    answer = typer.prompt("Proceed with trade? [y/N]", default="N")
    if answer.strip().lower() not in ("y", "yes"):
        console.print("[dim]Trade cancelled.[/dim]")
        raise typer.Exit()


def _parse_stages(
    tp_values: list[float],
    next_sl_values: list[float],
    initial_sl: float,
) -> list[TradeStage]:
    stages = []
    for i, tp in enumerate(tp_values):
        next_sl = next_sl_values[i] if i < len(next_sl_values) else (next_sl_values[-1] if next_sl_values else initial_sl)
        stages.append(TradeStage(take_profit=tp, next_stop_loss=next_sl))
    return stages


def _build_futures_plan(
    symbol: str,
    side: Side,
    quantity: float,
    sl: float,
    tp_values: list[float],
    next_sl_values: list[float],
    leverage: int,
    margin: str,
) -> TradePlan:
    return TradePlan(
        symbol=symbol, side=side, quantity=quantity,
        initial_stop_loss=sl,
        stages=_parse_stages(tp_values, next_sl_values, sl),
        leverage=leverage,
        margin_type=MarginType(margin.upper()),
    )


@futures_app.command()
def buy(
    symbol: str = typer.Argument(..., help="Trading pair, e.g. BTCUSDT"),
    quantity: float = typer.Argument(..., help="Contract quantity"),
    sl: float = typer.Option(..., "--sl", help="Initial stop-loss price"),
    tp: list[float] = typer.Option(..., "--tp", help="Take-profit level(s); repeat for multi-stage"),
    next_sl: list[float] = typer.Option([], "--next-sl", help="SL after each TP hit; one fewer than --tp"),
    leverage: int = typer.Option(0, "--leverage", "-l", help="Leverage (0 = use config default)"),
    margin: str = typer.Option("", "--margin", help="Margin type: isolated or cross (empty = config default)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Open a LONG (BUY) futures position with stop-loss / take-profit."""
    settings = get_settings()
    lev = leverage if leverage > 0 else settings.futures_leverage
    mgn = margin if margin else settings.futures_margin_type
    broker = make_futures_broker()
    plan = _build_futures_plan(symbol, Side.BUY, quantity, sl, tp, next_sl, lev, mgn)
    price, balances = None, {}
    with contextlib.suppress(Exception):
        price = broker.get_price(symbol)
    with contextlib.suppress(Exception):
        balances = broker.get_balance()
    print_trade_preview(price, balances, plan)
    _confirm(yes)
    try:
        result = broker.place_trade(plan)
    except Exception as exc:
        _die(str(exc))
    print_active_trade(result)


@futures_app.command()
def sell(
    symbol: str = typer.Argument(..., help="Trading pair, e.g. BTCUSDT"),
    quantity: float = typer.Argument(..., help="Contract quantity"),
    sl: float = typer.Option(..., "--sl", help="Initial stop-loss price"),
    tp: list[float] = typer.Option(..., "--tp", help="Take-profit level(s)"),
    next_sl: list[float] = typer.Option([], "--next-sl", help="SL after each TP hit"),
    leverage: int = typer.Option(0, "--leverage", "-l", help="Leverage (0 = use config default)"),
    margin: str = typer.Option("", "--margin", help="Margin type: isolated or cross"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Open a SHORT (SELL) futures position with stop-loss / take-profit."""
    settings = get_settings()
    lev = leverage if leverage > 0 else settings.futures_leverage
    mgn = margin if margin else settings.futures_margin_type
    broker = make_futures_broker()
    plan = _build_futures_plan(symbol, Side.SELL, quantity, sl, tp, next_sl, lev, mgn)
    price, balances = None, {}
    with contextlib.suppress(Exception):
        price = broker.get_price(symbol)
    with contextlib.suppress(Exception):
        balances = broker.get_balance()
    print_trade_preview(price, balances, plan)
    _confirm(yes)
    try:
        result = broker.place_trade(plan)
    except Exception as exc:
        _die(str(exc))
    print_active_trade(result)


@futures_app.command()
def positions(
    symbol: str | None = typer.Argument(None, help="Filter by trading pair"),
) -> None:
    """List open futures positions."""
    try:
        pos = make_futures_broker().get_positions(symbol=symbol)
    except Exception as exc:
        _die(str(exc))
    print_positions_table(pos)


@futures_app.command()
def orders(
    symbol: str | None = typer.Argument(None, help="Filter by trading pair"),
) -> None:
    """List open futures orders."""
    try:
        open_orders = make_futures_broker().get_open_orders(symbol=symbol)
    except Exception as exc:
        _die(str(exc))
    print_orders_table(open_orders)


@futures_app.command()
def balance() -> None:
    """Show futures account balance."""
    try:
        bal = make_futures_broker().get_balance()
    except Exception as exc:
        _die(str(exc))
    print_balance_table(bal)


@futures_app.command()
def cancel(
    symbol: str = typer.Argument(..., help="Trading pair"),
    order_id: int = typer.Argument(..., help="Order ID to cancel"),
) -> None:
    """Cancel an open futures order."""
    try:
        make_futures_broker().cancel_order(symbol, order_id)
    except Exception as exc:
        _die(str(exc))
    from rich.panel import Panel
    console.print(Panel(f"Order [bold]{order_id}[/bold] on [bold]{symbol}[/bold] cancelled.", style="green"))


@futures_app.command()
def close(
    symbol: str = typer.Argument(..., help="Trading pair to close"),
) -> None:
    """Market-close an entire futures position."""
    try:
        result = make_futures_broker().close_position(symbol)
    except Exception as exc:
        _die(str(exc))
    console.print(f"[bold green]✓ Position closed:[/bold green] {result}")
```

- [ ] **Step 4: Register futures subapp in `cli/trade_cli.py`**

Add after the existing imports:

```python
from trading_bot.cli.futures_cli import futures_app

app.add_typer(futures_app, name="futures")
```

- [ ] **Step 5: Run futures CLI tests**

```bash
uv run pytest tests/cli/test_futures_cli.py -v
```
Expected: 5 passed.

- [ ] **Step 6: Run full suite**

```bash
uv run pytest -q
```
Expected: all pass.

- [ ] **Step 7: Smoke test**

```bash
uv run trade futures --help
```
Expected: shows buy, sell, positions, orders, balance, cancel, close commands.

- [ ] **Step 8: Commit**

```bash
git add src/trading_bot/cli/futures_cli.py src/trading_bot/cli/trade_cli.py \
        tests/cli/test_futures_cli.py
git commit -m "feat(cli): add futures subapp with buy/sell/positions/orders/balance/cancel/close"
```

---

## Task 10: DB Migration

**Files:**
- Modify: `src/trading_bot/db/models.py` — extend `Position`, add `TradeStageRecord` ORM model
- Create: `migrations/versions/<auto>_extend_positions_add_trade_stages.py`

**Interfaces:**
- Produces: Updated `Position` ORM (7 new columns), new `TradeStageRecord` ORM table with `account_id`, `position_id`, `stage_index`, `take_profit`, `next_stop_loss`, `activated_at`, `created_at`

- [ ] **Step 1: Update `db/models.py`**

Open `src/trading_bot/db/models.py`. Add `from __future__ import annotations` at top if missing. Extend the `Position` class and add `TradeStageRecord` after it:

```python
# In Position class, add these mapped_column fields:
    current_stage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_sl_order_id: Mapped[int | None] = mapped_column(Integer)
    current_tp_order_id: Mapped[int | None] = mapped_column(Integer)
    leverage: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    liquidation_price: Mapped[float | None] = mapped_column(Money)
    unrealized_pnl: Mapped[float] = mapped_column(Money, default=0)
    margin_type: Mapped[str] = mapped_column(String(10), default="ISOLATED")

    stages: Mapped[list[TradeStageRecord]] = relationship(back_populates="position")


# Add after Position class:
class TradeStageRecord(Base):
    __tablename__ = "trade_stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id"), index=True)
    stage_index: Mapped[int] = mapped_column(Integer, nullable=False)
    take_profit: Mapped[float] = mapped_column(Money, nullable=False)
    next_stop_loss: Mapped[float] = mapped_column(Money, nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    position: Mapped[Position] = relationship(back_populates="stages")
```

- [ ] **Step 2: Generate migration**

```bash
uv run alembic revision --autogenerate -m "extend_positions_add_trade_stages"
```
Expected: new file in `migrations/versions/`.

- [ ] **Step 3: Review generated migration**

Open the new migration file. Verify:
- `op.add_column('positions', ...)` for each new column
- `op.create_table('trade_stages', ...)` with all columns
- Both `upgrade()` and `downgrade()` present

- [ ] **Step 4: Apply migration**

```bash
uv run alembic upgrade head
```
Expected: `Running upgrade ... -> <rev>`.

- [ ] **Step 5: Verify schema**

```bash
PGPASSWORD=bot psql -h 127.0.0.1 -U bot -d trading_bot -c "\dt"
```
Expected: `trade_stages` in the table list.

- [ ] **Step 6: Run full test suite**

```bash
uv run pytest -q
```
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/trading_bot/db/models.py migrations/
git commit -m "feat(db): extend positions table and add trade_stages for lifecycle audit"
```

---

## Task 11: MCP Server Extension

**Files:**
- Modify: `src/trading_bot/mcp_server.py`

**Interfaces:**
- Consumes: `FuturesBroker`, `make_futures_broker`, `TradePlan`, `TradeStage`, `MarginType`
- Produces: MCP tools `place_futures_trade`, `get_futures_positions`, `get_futures_balance`, `cancel_futures_order`, `close_futures_position`

- [ ] **Step 1: Update `mcp_server.py`**

Open `src/trading_bot/mcp_server.py`. Replace its contents with the updated version that adds futures tools alongside the existing spot tools:

```python
# src/trading_bot/mcp_server.py
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
```

- [ ] **Step 2: Run full test suite**

```bash
uv run pytest -q
```
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add src/trading_bot/mcp_server.py
git commit -m "feat(mcp): add futures tools alongside existing spot tools"
```

---

## Task 12: Services Stub

**Files:**
- Create: `src/trading_bot/services/__init__.py` (empty)
- Create: `src/trading_bot/services/position_manager.py`

**Interfaces:**
- Consumes: `IBroker`, `ITradeStore`
- Produces: `PositionManager` stub with `on_price_update(symbol, price)` no-op

- [ ] **Step 1: Create files**

```bash
touch src/trading_bot/services/__init__.py
```

- [ ] **Step 2: Write `services/position_manager.py`**

```python
# src/trading_bot/services/position_manager.py
from __future__ import annotations

import structlog

from trading_bot.core.ports.broker import IBroker
from trading_bot.core.ports.trade_store import ITradeStore

log = structlog.get_logger(__name__)


class PositionManager:
    """Drives trade lifecycle from price events.

    Wired to the WebSocket price feed in Week 5. Until then, stage
    advancement is triggered manually via the CLI `futures advance` command.
    """

    def __init__(self, broker: IBroker, store: ITradeStore) -> None:
        self._broker = broker
        self._store = store

    def on_price_update(self, symbol: str, price: float) -> None:
        log.debug("price update received (not yet wired)", symbol=symbol, price=price)
```

- [ ] **Step 3: Run final full test suite + lint**

```bash
uv run pytest -q && uv run ruff check src/ tests/
```
Expected: all tests pass, no lint errors.

- [ ] **Step 4: Verify CLI entry points**

```bash
uv run trade --help && uv run trade futures --help
```

- [ ] **Step 5: Verify no core → exchanges leakage**

```bash
grep -r "from trading_bot.exchanges" src/trading_bot/core/ && echo "FAIL: core imports exchange" || echo "OK: core is clean"
```
Expected: `OK: core is clean`

- [ ] **Step 6: Commit**

```bash
git add src/trading_bot/services/
git commit -m "feat(services): add PositionManager stub wired for Week 5 event loop"
```
