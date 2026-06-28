# Futures Trading + SOLID Refactor — Design Spec

**Date:** 2026-06-28  
**Author:** jivesha  
**Status:** Approved (design); ready for implementation planning

---

## 1. Goal & Scope

Refactor the existing codebase and add Binance USDM futures trading, guided by three constraints:

1. **SOLID / SRP throughout** — no class mixes connection, validation, order-building, and execution. Each unit has one job.
2. **Keep spot trading** — existing `SpotBroker` stays working; futures is additive.
3. **Open for strategy automation** — trade lifecycle (staged SL/TP updates) must be a first-class concept so a future strategy layer can drive it without touching broker code.

### Out of scope (this iteration)
- WebSocket price feed (Week 5)
- Strategy automation / `PositionManager` wiring (Week 5)
- Partial position closes
- COINM futures or HEDGE position mode

---

## 2. Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Futures market | USDM perpetuals (`fapi.binance.com`) | Most liquid, retail-standard |
| Position mode | ONE-WAY only | Simplest model; one position per symbol |
| Entry style | MARKET entry | Guaranteed fill; matches existing spot UX |
| Exit style | `STOP_MARKET` + `TAKE_PROFIT_MARKET` with `closePosition=true` | No size-mismatch bugs on partial fills |
| Leverage config | Default in config, override per-trade via CLI flag | Safe default, flexible override |
| Margin type | Default in config, override per-trade via CLI flag | Same rationale |
| Architecture pattern | Ports & Adapters | `core/` depends on nothing; exchanges are plugins |

---

## 3. Module Structure

```
src/trading_bot/
  core/
    domain/
      order.py          # OrderRequest, TradeResult, Side, OrderType, MarginType
      position.py       # Position value object (futures-aware)
      trade.py          # ActiveTrade, TradePlan, TradeStage, TradeStatus
    ports/
      broker.py         # IBroker protocol
      trade_store.py    # ITradeStore protocol (persistence abstraction)

  exchanges/
    binance/
      common/
        errors.py       # BrokerError; maps BinanceAPIException → domain errors
        auth.py         # Client construction (spot vs futures base URLs)
      spot/
        broker.py       # SpotBroker: IBroker
        order_builder.py  # Pure functions: build_otoco_payload(...)
        validator.py    # SpotValidator: validate SL/TP vs current price
      futures/
        broker.py       # FuturesBroker: IBroker
        order_builder.py  # Pure functions: build_entry, build_stop_market, build_tp_market
        validator.py    # FuturesValidator: leverage, margin, SL/TP, min notional

  services/
    position_manager.py # Stub — wired to event loop in Week 5

  cli/
    trade_cli.py        # Spot commands (unchanged UX)
    futures_cli.py      # Futures subapp: buy, sell, positions, balance, cancel, advance
    _display.py         # Shared Rich rendering (panels, tables, risk metrics)
    _broker_factory.py  # Constructs SpotBroker or FuturesBroker from Settings

  mcp_server.py         # Thin MCP wrapper — exposes both brokers
  config.py             # Extended with futures settings
  db/
    models.py           # Position model extended; new trade_stages table
```

**Dependency rule:** `core/` imports nothing from `exchanges/`, `cli/`, or `services/`. All dependencies point inward.

---

## 4. Domain Types (`core/domain/`)

### `order.py`

```python
class Side(str, Enum):
    BUY  = "BUY"
    SELL = "SELL"

class OrderType(str, Enum):
    MARKET              = "MARKET"
    LIMIT               = "LIMIT"
    STOP_MARKET         = "STOP_MARKET"
    TAKE_PROFIT_MARKET  = "TAKE_PROFIT_MARKET"

class MarginType(str, Enum):
    ISOLATED = "ISOLATED"
    CROSS    = "CROSS"

@dataclass(frozen=True)
class OrderRequest:
    symbol:       str
    side:         Side
    quantity:     float
    stop_loss:    float
    take_profit:  float
    leverage:     int        = 1               # 1 for spot (unused)
    margin_type:  MarginType = MarginType.ISOLATED

@dataclass(frozen=True)
class TradeResult:
    symbol:               str
    side:                 Side
    quantity:             float
    entry_price:          float
    entry_order_id:       int
    stop_loss_order_id:   int
    take_profit_order_id: int
    stop_loss:            float
    take_profit:          float
    raw_response:         dict   # full exchange payload, never discarded
```

### `trade.py`

```python
@dataclass(frozen=True)
class TradeStage:
    take_profit:     float
    next_stop_loss:  float   # SL to activate when strategy advances to this stage

@dataclass(frozen=True)
class TradePlan:
    symbol:              str
    side:                Side
    quantity:            float
    initial_stop_loss:   float
    stages:              list[TradeStage]   # min 1; strategy walks this list

class TradeStatus(str, Enum):
    OPEN      = "OPEN"
    ADVANCING = "ADVANCING"   # mid-stage-transition (transient)
    CLOSED    = "CLOSED"

@dataclass
class ActiveTrade:
    plan:                  TradePlan
    current_stage:         int            # 0-indexed
    entry_order_id:        int
    entry_price:           float
    current_sl_order_id:   int
    current_tp_order_id:   int
    status:                TradeStatus

    @property
    def current_stage_def(self) -> TradeStage:
        return self.plan.stages[self.current_stage]

    @property
    def has_next_stage(self) -> bool:
        return self.current_stage + 1 < len(self.plan.stages)
```

### `position.py`

```python
@dataclass(frozen=True)
class Position:
    symbol:             str
    side:               Side
    quantity:           float
    entry_price:        float
    leverage:           int
    liquidation_price:  float
    unrealized_pnl:     float
    margin_type:        MarginType
```

---

## 5. Broker Interface (`core/ports/broker.py`)

```python
class IBroker(Protocol):
    # Trade lifecycle
    def place_trade(self, plan: TradePlan) -> ActiveTrade: ...
    def advance_stage(self, trade: ActiveTrade) -> ActiveTrade: ...
    def update_stop_loss(self, trade: ActiveTrade, new_sl: float) -> ActiveTrade: ...
    def close_position(self, symbol: str) -> dict: ...

    # Queries
    def get_price(self, symbol: str) -> float: ...
    def get_open_orders(self, symbol: str | None = None) -> list[dict]: ...
    def get_balance(self) -> dict[str, dict]: ...
    def get_positions(self, symbol: str | None = None) -> list[Position]: ...

    # Order management
    def cancel_order(self, symbol: str, order_id: int) -> dict: ...
```

`advance_stage` is atomic from the caller's perspective: set status to `ADVANCING`, cancel current SL+TP, place next stage's SL+TP, increment `current_stage`, set status back to `OPEN`, return updated `ActiveTrade`. If placement fails mid-way the broker raises `BrokerError` and the caller must reconcile via `get_open_orders`.

---

## 6. Exchange Implementations

### 6.1 Common (`exchanges/binance/common/`)

**`errors.py`**
- `BrokerError(message, code, original)` — domain error, exchange-agnostic
- `map_binance_error(exc: BinanceAPIException) -> BrokerError`

**`auth.py`**
- `make_spot_client(settings) -> Client`
- `make_futures_client(settings) -> Client` — sets `API_URL` to `fapi` endpoint

### 6.2 Spot (`exchanges/binance/spot/`)

**`validator.py`**
- BUY: `stop_loss < current_price < take_profit`
- SELL: `take_profit < current_price < stop_loss`

**`order_builder.py`** — pure functions, no I/O
- `build_otoco(plan, working_price) -> dict` — existing OTOCO payload, extracted verbatim

**`broker.py` — `SpotBroker(IBroker)`**
- Replaces current `BinanceBroker`; identical external behaviour
- `get_price` extracted from broker — CLI no longer touches `broker._client`
- `get_positions` returns empty list (no margin positions in spot)

### 6.3 Futures (`exchanges/binance/futures/`)

**`validator.py`**
- Leverage: 1–125
- BUY (LONG): `stop_loss < current_price < take_profit`
- SELL (SHORT): `take_profit < current_price < stop_loss`
- Min notional: `quantity * current_price >= 5.0` (USDM minimum)

**`order_builder.py`** — pure functions, no I/O
- `build_entry(symbol, side, quantity) -> dict`
- `build_stop_market(symbol, side, stop_price) -> dict` — `closePosition=true`
- `build_take_profit_market(symbol, side, tp_price) -> dict` — `closePosition=true`
- `build_set_leverage(symbol, leverage) -> dict`
- `build_set_margin_type(symbol, margin_type) -> dict`

**`broker.py` — `FuturesBroker(IBroker)`**

`place_trade(plan)` flow:
1. `get_price(symbol)` → current price
2. `FuturesValidator.validate(request, current_price)`
3. POST `/fapi/v1/leverage` (idempotent)
4. POST `/fapi/v1/marginType` (idempotent; ignore error -4046 "no change")
5. POST `/fapi/v1/order` MARKET entry
6. Poll `/fapi/v1/order` until FILLED
7. POST `/fapi/v1/order` STOP_MARKET (`closePosition=true`)
8. POST `/fapi/v1/order` TAKE_PROFIT_MARKET (`closePosition=true`)
9. Return `ActiveTrade`

`advance_stage(trade)`:
1. Cancel `current_sl_order_id`
2. Cancel `current_tp_order_id`
3. Place new STOP_MARKET at `next_stage.next_stop_loss`
4. Place new TAKE_PROFIT_MARKET at `next_stage.take_profit`
5. Return updated `ActiveTrade` with incremented `current_stage`

`get_balance()`:
- GET `/fapi/v2/account` → `{ availableBalance, totalMarginBalance, totalUnrealizedProfit }`

`get_positions(symbol)`:
- GET `/fapi/v2/positionRisk` → filter `positionAmt != 0` → map to `Position`

---

## 7. CLI Design

### Spot CLI (`cli/trade_cli.py`) — unchanged UX

```bash
uv run trade buy  BTCUSDT 0.001 --sl 95000 --tp 105000
uv run trade sell BTCUSDT 0.001 --sl 105000 --tp 95000
uv run trade orders [SYMBOL]
uv run trade balance
uv run trade cancel BTCUSDT 12345678
```

Fix: `trade_cli.py` currently calls `broker._client.get_symbol_ticker()` directly.
After refactor it calls `broker.get_price(symbol)` — encapsulation restored.

### Futures CLI (`cli/futures_cli.py`) — new subapp

Registered as `trade futures <command>`:

```bash
# Single-stage (simple)
uv run trade futures buy  BTCUSDT 0.001 --sl 95000  --tp 105000
uv run trade futures sell BTCUSDT 0.001 --sl 105000 --tp 95000

# Multi-stage plan
uv run trade futures buy BTCUSDT 0.001 \
  --sl 95000 \
  --tp 102000 --next-sl 99000 \
  --tp 108000 --next-sl 104000 \
  --tp 115000

# Position management
uv run trade futures positions [SYMBOL]
uv run trade futures advance BTCUSDT
uv run trade futures move-sl BTCUSDT 97000
uv run trade futures close BTCUSDT
uv run trade futures orders [SYMBOL]
uv run trade futures balance
uv run trade futures cancel BTCUSDT 12345678

# Optional overrides
uv run trade futures buy BTCUSDT 0.001 --sl 95000 --tp 105000 --leverage 10 --margin cross
```

### Shared rendering (`cli/_display.py`)

- `print_trade_preview(broker, plan, leverage, margin_type)`
- `print_trade_result(result)`
- `print_orders_table(orders)`
- `print_balance_table(balances)`
- `print_positions_table(positions)`

---

## 8. Configuration (`config.py`) — new fields

```python
futures_leverage:              int  = 5
futures_margin_type:           str  = "ISOLATED"
binance_futures_testnet:       bool = True
binance_futures_testnet_url:   str  = "https://testnet.binancefuture.com/fapi"
binance_futures_live_url:      str  = "https://fapi.binance.com/fapi"
```

---

## 9. Database Changes

### `positions` — new columns

```sql
current_stage        INTEGER      NOT NULL DEFAULT 0
current_sl_order_id  BIGINT
current_tp_order_id  BIGINT
leverage             INTEGER      NOT NULL DEFAULT 1
liquidation_price    NUMERIC(28,10)
unrealized_pnl       NUMERIC(28,10) DEFAULT 0
margin_type          VARCHAR(10)  DEFAULT 'ISOLATED'
```

### New `trade_stages` table

Audit trail for strategy research — records every stage definition and when it activated:

```sql
CREATE TABLE trade_stages (
    id              SERIAL PRIMARY KEY,
    account_id      INTEGER      NOT NULL REFERENCES accounts(id),
    position_id     INTEGER      NOT NULL REFERENCES positions(id),
    stage_index     INTEGER      NOT NULL,
    take_profit     NUMERIC(28,10) NOT NULL,
    next_stop_loss  NUMERIC(28,10) NOT NULL,
    activated_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
```

Both changes in a single Alembic migration, additive only.

---

## 10. Services Stub (`services/position_manager.py`)

No-op for this iteration. Wired to WebSocket price feed in Week 5:

```python
class PositionManager:
    def __init__(self, broker: IBroker, store: ITradeStore) -> None: ...
    def on_price_update(self, symbol: str, price: float) -> None: ...
```

`ITradeStore` (`core/ports/trade_store.py`):
```python
class ITradeStore(Protocol):
    def save(self, trade: ActiveTrade) -> None: ...
    def get_active(self, symbol: str) -> ActiveTrade | None: ...
    def get_all_active(self) -> list[ActiveTrade]: ...
```

---

## 11. MCP Server

Adds futures tools alongside existing spot tools:

```python
@mcp.tool()
def place_futures_trade(symbol, side, quantity, stop_loss, take_profit,
                        leverage=5, margin_type="ISOLATED") -> dict: ...

@mcp.tool()
def get_futures_positions(symbol: str = "") -> list: ...

@mcp.tool()
def advance_futures_stage(symbol: str) -> dict: ...
```

---

## 12. Testing Strategy

| Layer | What to test |
|-------|-------------|
| `order_builder.py` (spot + futures) | Payload shape, field values — pure functions, zero mocks |
| `validator.py` (spot + futures) | All valid/invalid price combos, leverage bounds, min notional |
| `SpotBroker` | All `IBroker` methods with mocked `python-binance` client |
| `FuturesBroker` | All `IBroker` methods; `advance_stage` cancel+replace sequence |
| `ActiveTrade` | Stage transitions, `has_next_stage`, `current_stage_def` |
| CLI | Typer test runner; happy path + validation errors (spot + futures) |

Coverage target: 80%+. No network or DB required.

---

## 13. Migration Path (no breaking changes)

1. `uv run trade buy/sell` continues to work throughout — `SpotBroker` is a drop-in replacement for `BinanceBroker`
2. `BinanceBroker` renamed to `SpotBroker`; import alias kept in `client/__init__.py` until all consumers updated
3. All existing tests green before any new code is written
4. DB migration is additive only — new columns have defaults, new table is independent
