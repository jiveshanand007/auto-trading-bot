# Auto Trading Bot — High-Level Design

> **Living document.** Last updated: 2026-06-30. Reflects the current codebase on branch `feat/futures-refactor`.

---

## What This Is

A **strategy research → live-validation platform** for Binance. Currently a single-operator system that can place, manage, and close spot and USDM perpetual futures trades from the terminal or via Claude (MCP). The architecture is designed so the same strategy/risk code runs identically in backtest, testnet, and live — only the broker implementation swaps.

---

## North Star: Backtest / Live Parity

```
Strategy → Risk → IBroker
                     │
           ┌─────────┴──────────┐
     SimulatedBroker       SpotBroker / FuturesBroker
     (backtest)            (testnet / live)
```

**Never fork strategy or risk logic per mode.** Only the `IBroker` implementation changes.

---

## Architecture: Ports & Adapters (Hexagonal)

```
┌─────────────────────────────────────────────────────────────┐
│  DRIVING LAYER (how humans / agents trigger the system)     │
│                                                             │
│   CLI (typer + rich)          MCP Server (FastMCP)         │
│   uv run trade [...]          Claude conversational UI      │
└──────────────────────┬──────────────────────────────────────┘
                       │ calls
┌──────────────────────▼──────────────────────────────────────┐
│  CORE (pure domain — no I/O, no exchange-specific code)     │
│                                                             │
│  domain/trade.py   TradePlan, TradeStage, ActiveTrade       │
│  domain/order.py   Side, MarginType, OrderType enums        │
│  domain/position.py  Position dataclass                     │
│  ports/broker.py   IBroker protocol (9 methods)             │
│  ports/trade_store.py  ITradeStore protocol                 │
└──────────────────────┬──────────────────────────────────────┘
                       │ implemented by
┌──────────────────────▼──────────────────────────────────────┐
│  ADAPTERS (exchange-specific, never imported by core)       │
│                                                             │
│  exchanges/binance/common/                                  │
│    auth.py          make_spot_client / make_futures_client  │
│    errors.py        BrokerError                             │
│                                                             │
│  exchanges/binance/spot/                                    │
│    broker.py        SpotBroker   implements IBroker         │
│    order_builder.py pure functions — build OCO order args   │
│    validator.py     pure functions — validate TradePlan     │
│                                                             │
│  exchanges/binance/futures/                                 │
│    broker.py        FuturesBroker  implements IBroker       │
│    order_builder.py pure functions — build futures orders   │
│    validator.py     pure functions — validate futures plan  │
└─────────────────────────────────────────────────────────────┘
```

**Key rule:** `grep -r "from trading_bot.exchanges" src/trading_bot/core/` returns nothing. Core never knows about exchanges.

---

## IBroker Protocol

Defined in `src/trading_bot/core/ports/broker.py`. Every broker (spot, futures, simulated) must implement all 9 methods:

| Method | Purpose |
|--------|---------|
| `place_trade(plan)` | Open a position with entry, SL, TP |
| `advance_stage(trade)` | Cancel current TP/SL, place next stage's orders |
| `update_stop_loss(trade, new_sl)` | Move the stop-loss order |
| `close_position(symbol)` | Market-close the entire position |
| `get_price(symbol)` | Current market price |
| `get_open_orders(symbol?)` | List open orders |
| `get_balance()` | Account balances |
| `get_positions(symbol?)` | Open positions |
| `cancel_order(symbol, order_id)` | Cancel a single order |

---

## Domain Types

### TradePlan (immutable input)
```python
TradePlan(
    symbol="BTCUSDT",
    side=Side.BUY,
    quantity=0.001,
    initial_stop_loss=94000.0,
    stages=[
        TradeStage(take_profit=108000.0, next_stop_loss=97000.0),
        TradeStage(take_profit=115000.0, next_stop_loss=105000.0),
    ],
    leverage=10,                      # futures only
    margin_type=MarginType.ISOLATED,  # futures only
)
```

### ActiveTrade (live tracking)
Returned by `place_trade`. Holds order IDs, current stage index, entry price, status. Stored in `_active_trades` dict in the CLI for `advance` / `move-sl` commands.

### Multi-Stage Lifecycle
```
Stage 0 open:
  Entry: MARKET fill at ~99,000
  SL:    STOP_MARKET at 94,000
  TP:    TAKE_PROFIT_MARKET at 108,000

`advance BTCUSDT` (when TP hit or called manually):
  Cancel old SL + TP
  Place new SL at 97,000  ← locked-in profit
  Place new TP at 115,000
```

---

## Broker Implementations

### SpotBroker
- Entry: `create_order(MARKET)`
- SL + TP in one shot: `create_oco_order` (OCO = One-Cancels-the-Other)
- Balance: `get_account()` → filters non-zero assets
- Testnet URL: `https://testnet.binance.vision/api` → set via `client.API_URL`

### FuturesBroker
- Set leverage + margin type first via `futures_change_leverage` / `futures_change_margin_type`
- Entry: `futures_create_order(MARKET)`
- SL: separate `futures_create_order(STOP_MARKET, closePosition=True)`
- TP: separate `futures_create_order(TAKE_PROFIT_MARKET, closePosition=True)`
- Balance: `futures_account()` → deeply nested dict; CLI extracts 5 summary keys
- Testnet URL: `https://testnet.binancefuture.com/fapi` → set via `client.FUTURES_URL`

### Critical python-binance Gotcha
`python-binance` uses **two separate URL attributes**:
- `client.API_URL` — used by spot methods (`create_order`, `get_account`, …)
- `client.FUTURES_URL` — used by futures methods (`futures_create_order`, `futures_account`, …)

Setting the wrong one causes `APIError(code=-2015)` on every futures call even with valid credentials. See `exchanges/binance/common/auth.py`.

---

## Configuration

All settings are `BOT_`-prefixed env vars, loaded via pydantic-settings from `.env`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `BOT_BINANCE_API_KEY` | — | Spot (and futures fallback) API key |
| `BOT_BINANCE_API_SECRET` | — | Spot API secret |
| `BOT_BINANCE_TESTNET` | `true` | Use spot testnet |
| `BOT_BINANCE_TESTNET_URL` | `https://testnet.binance.vision/api` | Spot testnet URL |
| `BOT_BINANCE_FUTURES_API_KEY` | — | Futures-specific key (falls back to spot key) |
| `BOT_BINANCE_FUTURES_API_SECRET` | — | Futures-specific secret |
| `BOT_BINANCE_FUTURES_TESTNET` | `true` | Use futures testnet |
| `BOT_BINANCE_FUTURES_TESTNET_URL` | `https://testnet.binancefuture.com/fapi` | Futures testnet URL |
| `BOT_FUTURES_LEVERAGE` | `5` | Default leverage |
| `BOT_FUTURES_MARGIN_TYPE` | `ISOLATED` | Default margin type |
| `BOT_DATABASE_URL` | `postgresql+psycopg2://bot:bot@localhost:5432/trading_bot` | Postgres |

**Testnet note:** Spot testnet (`testnet.binance.vision`) and futures testnet (`testnet.binancefuture.com`) accept the **same API key**. No separate futures key is needed; `make_futures_client` falls back to spot keys automatically.

---

## CLI Reference

Entry point: `uv run trade`

### Spot commands

```bash
uv run trade buy  BTCUSDT 0.001 --sl 94000 --tp 108000
uv run trade sell BTCUSDT 0.001 --sl 108000 --tp 94000
uv run trade orders [SYMBOL]
uv run trade balance
uv run trade cancel SYMBOL ORDER_ID
```

### Futures subcommands (`uv run trade futures`)

```bash
# Open positions
uv run trade futures buy  BTCUSDT 0.001 --sl 94000 --tp 108000 [--leverage 10] [--margin ISOLATED]
uv run trade futures sell BTCUSDT 0.001 --sl 108000 --tp 90000

# Multi-stage: add multiple TP + next-SL levels
uv run trade futures buy BTCUSDT 0.001 --sl 94000 \
    --tp 108000 --next-sl 97000 \
    --tp 115000 --next-sl 105000

# Manage open trades (requires prior buy/sell in same session)
uv run trade futures advance BTCUSDT        # promote to next stage
uv run trade futures move-sl BTCUSDT 97000  # drag stop-loss up

# Query / housekeeping
uv run trade futures positions [SYMBOL]
uv run trade futures orders    [SYMBOL]
uv run trade futures balance
uv run trade futures cancel SYMBOL ORDER_ID
uv run trade futures close  SYMBOL          # market-close entire position
```

`--yes` / `-y` skips the confirmation prompt on buy/sell.

---

## MCP Server (Claude conversational interface)

Start: `uv run python -m trading_bot.mcp_server`

Exposes 9 tools to Claude:

| Tool | What it does |
|------|-------------|
| `place_spot_trade` | Spot entry with SL + TP |
| `get_spot_orders` | Open spot orders |
| `get_spot_balance` | Spot account balances |
| `cancel_spot_order` | Cancel spot order |
| `place_futures_trade` | Futures entry with SL + TP + leverage |
| `get_futures_positions` | Open futures positions |
| `get_futures_balance` | Futures account balance |
| `cancel_futures_order` | Cancel futures order |
| `close_futures_position` | Market-close a futures position |

Example: *"Buy 0.001 BTC futures with 10x leverage, SL at 94000, TP at 108000"* → Claude calls `place_futures_trade`.

---

## Database Schema

PostgreSQL 14, local system install on WSL2 (not Docker — see CLAUDE.md). 9 tables, all with `account_id` as the SaaS seam for future multi-tenancy.

```
accounts          — one row per operator account
strategies        — named strategies with JSON params
runs              — one execution context (backtest / testnet / live)
orders            — every order placed, linked to a run
fills             — execution fills for each order
positions         — running P&L per symbol per run
  ├─ current_stage, current_sl_order_id, current_tp_order_id
  ├─ leverage, margin_type, liquidation_price, unrealized_pnl
  └─ stages[]  →  trade_stages
trade_stages      — each TP/next-SL level in a multi-stage plan
equity_snapshots  — periodic equity curve snapshots
alembic_version   — migration tracking
```

Apply schema: `uv run alembic upgrade head`

---

## Source Layout

```
src/trading_bot/
  config.py                      # All settings (BOT_ env vars)
  logging_config.py              # structlog JSON/pretty setup
  mcp_server.py                  # FastMCP server (9 tools)

  core/                          # Pure domain — no I/O
    domain/
      trade.py                   # TradePlan, TradeStage, ActiveTrade
      order.py                   # Side, MarginType, OrderType
      position.py                # Position dataclass
    ports/
      broker.py                  # IBroker protocol (9 methods)
      trade_store.py             # ITradeStore protocol

  exchanges/binance/             # Exchange adapters (never imported by core)
    common/
      auth.py                    # make_spot_client / make_futures_client
      errors.py                  # BrokerError
    spot/
      broker.py                  # SpotBroker — OCO orders
      order_builder.py           # pure functions: build OCO args
      validator.py               # pure functions: validate spot plan
    futures/
      broker.py                  # FuturesBroker — separate SL + TP orders
      order_builder.py           # pure functions: build futures order args
      validator.py               # pure functions: validate futures plan

  cli/                           # Terminal interface (typer + rich)
    trade_cli.py                 # Root app + spot commands
    futures_cli.py               # `futures` subapp (9 commands)
    _broker_factory.py           # make_spot_broker / make_futures_broker
    _display.py                  # Rich tables: balance, positions, orders, trade

  services/
    position_manager.py          # Stub: wires price feeds → active trade mgmt (Week 5)

  market_data/                   # Historical OHLCV (Week 1 deliverable)
    types.py                     # Bar, Timeframe — canonical market data type
    storage.py                   # Parquet read/write
    downloader.py                # Binance klines fetcher (no API key needed)
    download_cli.py              # download_cli entry point

  db/
    base.py                      # SQLAlchemy declarative base
    models.py                    # All ORM models (9 tables)

migrations/                      # Alembic env + version files
tests/                           # pytest — 94 tests, no network/DB needed
docs/
  HLD.md                         # This file
  flows/trade-execution-flow.md  # Step-by-step order placement flow
  reference/binance-api.md       # Binance API reference notes
```

---

## Key Commands

```bash
uv sync --extra dev              # install / sync deps
uv run pytest -q                 # run all tests (94 passing)
uv run ruff check src/ tests/    # lint
uv run ruff format src/ tests/   # format
uv run alembic upgrade head      # apply DB migrations
```

---

## Progress

| Week | Theme | Status |
|------|-------|--------|
| 1 | Foundations: scaffold, config, DB schema (8 tables), market data download | Done |
| 2 | Live trading: spot CLI, futures CLI, MCP, testnet validation | Done |
| 3 | Analytics & research dashboard | Roadmap |
| 4 | Risk & portfolio management | Roadmap |
| 5 | Live data + streaming (WebSocket price feeds) | Roadmap |
| 6 | Live runtime + reliability | Roadmap |
| 7 | Go-live (tiny capital) | Roadmap |
| 8 | Streamlit dashboard | Roadmap |

---

## Validated Live on Testnet (2026-06-30)

- `futures balance` — shows available balance, margin, unrealized PnL
- `futures positions BTCUSDT` — open contracts with leverage and liquidation price
- `futures close BTCUSDT` — market-closes position, removes from `_active_trades`
- `futures buy` / `futures sell` — places MARKET entry + STOP_MARKET + TAKE_PROFIT_MARKET
- Spot `balance`, `orders`, `buy` — all verified on `testnet.binance.vision`
