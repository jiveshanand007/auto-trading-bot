# Graph Report - .  (2026-06-30)

## Corpus Check
- 82 files · ~42,240 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 561 nodes · 1023 edges · 50 communities (44 shown, 6 thin omitted)
- Extraction: 80% EXTRACTED · 20% INFERRED · 0% AMBIGUOUS · INFERRED: 205 edges (avg confidence: 0.74)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_External Libraries & Base Types|External Libraries & Base Types]]
- [[_COMMUNITY_Futures CLI & Order Domain|Futures CLI & Order Domain]]
- [[_COMMUNITY_Config & Client Factory|Config & Client Factory]]
- [[_COMMUNITY_Binance Error Handling|Binance Error Handling]]
- [[_COMMUNITY_CLI Display & Broker Factory|CLI Display & Broker Factory]]
- [[_COMMUNITY_SDD Tasks & Core Protocols|SDD Tasks & Core Protocols]]
- [[_COMMUNITY_Project Docs & Architecture|Project Docs & Architecture]]
- [[_COMMUNITY_Trade Domain Model|Trade Domain Model]]
- [[_COMMUNITY_Infrastructure & Setup|Infrastructure & Setup]]
- [[_COMMUNITY_Futures CLI Tests|Futures CLI Tests]]
- [[_COMMUNITY_Futures Broker Tests|Futures Broker Tests]]
- [[_COMMUNITY_Legacy Broker Tests|Legacy Broker Tests]]
- [[_COMMUNITY_Database Models|Database Models]]
- [[_COMMUNITY_Spot Broker Tests|Spot Broker Tests]]
- [[_COMMUNITY_Market Data Types Tests|Market Data Types Tests]]
- [[_COMMUNITY_Futures Validator Tests|Futures Validator Tests]]
- [[_COMMUNITY_DB Model Tests|DB Model Tests]]
- [[_COMMUNITY_Project Roadmap|Project Roadmap]]
- [[_COMMUNITY_MCP Server|MCP Server]]
- [[_COMMUNITY_Infrastructure Requirements|Infrastructure Requirements]]
- [[_COMMUNITY_Kubernetes DevOps Requirement|Kubernetes DevOps Requirement]]
- [[_COMMUNITY_TradeResult Legacy Type|TradeResult Legacy Type]]
- [[_COMMUNITY_Futures Leverage Builder|Futures Leverage Builder]]
- [[_COMMUNITY_Settings Singleton|Settings Singleton]]

## God Nodes (most connected - your core abstractions)
1. `TradePlan` - 32 edges
2. `ActiveTrade` - 30 edges
3. `ParquetBarStore` - 24 edges
4. `map_binance_error()` - 24 edges
5. `FuturesBroker` - 24 edges
6. `SpotBroker` - 21 edges
7. `Settings` - 20 edges
8. `TradeStage` - 20 edges
9. `Side` - 18 edges
10. `Timeframe` - 17 edges

## Surprising Connections (you probably didn't know these)
- `Strategy Engine (Brain)` --semantically_similar_to--> `Strategy Component (on_bar->Signal)`  [INFERRED] [semantically similar]
  requirement.md → docs/superpowers/specs/2026-06-21-trading-bot-8-week-design.md
- `Risk & Fund Allocator` --semantically_similar_to--> `Risk & Portfolio Manager`  [INFERRED] [semantically similar]
  requirement.md → docs/superpowers/specs/2026-06-21-trading-bot-8-week-design.md
- `Order Execution Module` --semantically_similar_to--> `Broker Interface`  [INFERRED] [semantically similar]
  requirement.md → docs/superpowers/specs/2026-06-21-trading-bot-8-week-design.md
- `Binance API (REST + WebSocket)` --semantically_similar_to--> `BinanceBroker (testnet/prod)`  [INFERRED] [semantically similar]
  requirement.md → docs/superpowers/specs/2026-06-21-trading-bot-8-week-design.md
- `Market Data Feed` --semantically_similar_to--> `Market Data Component`  [INFERRED] [semantically similar]
  requirement.md → docs/superpowers/specs/2026-06-21-trading-bot-8-week-design.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Spot Trade Placement Flow** — sdd_task5brief_spotbroker, sdd_task4brief_spotvalidate, sdd_task4brief_buildotoco [EXTRACTED 1.00]
- **Core Trade Lifecycle Model** — sdd_task1brief_tradeplan, sdd_task1brief_tradestage, sdd_task1brief_activetrade, sdd_task1brief_tradestatus [EXTRACTED 1.00]
- **Futures Order Construction** — sdd_task6brief_futuresvalidate, sdd_task6brief_buildentry, sdd_task6brief_buildstopmarket, sdd_task6brief_buildtakeprofitmarket [EXTRACTED 1.00]
- **Hexagonal Broker Layer: IBroker Port with SpotBroker and FuturesBroker Adapters** — docs_hld_ibroker, docs_hld_spotbroker, docs_hld_futuresbroker, docs_hld_hexagonal_arch [EXTRACTED 1.00]
- **Core Trade Domain Model: TradePlan contains TradeStages tracked by ActiveTrade** — docs_hld_tradeplan, docs_hld_tradestage, docs_hld_activetrade [EXTRACTED 1.00]
- **CLI Layer: display, broker-factory, spot-CLI, and futures-CLI participate in terminal interface** — sdd_task_8_brief_display_module, sdd_task_8_brief_broker_factory, sdd_task_8_brief_trade_cli, sdd_task_9_brief_futures_app [INFERRED 0.95]

## Communities (50 total, 6 thin omitted)

### Community 0 - "External Libraries & Base Types"
Cohesion: 0.05
Nodes (51): BaseModel, BoundLogger, DataFrame, datetime, _now(), main(), _parse_date(), CLI to download historical klines into the parquet store.  Example::      uv run (+43 more)

### Community 1 - "Futures CLI & Order Domain"
Cohesion: 0.06
Nodes (51): advance command calls broker.advance_stage and updates _active_trades., test_futures_advance_success(), MarginType, OrderType, Side, TradeResult, Position, _plan() (+43 more)

### Community 2 - "Config & Client Factory"
Cohesion: 0.05
Nodes (39): BaseSettings, Client, BinanceBroker, BrokerError, Binance broker implementation wrapping python-binance., TradeResult, make_futures_client(), make_spot_client() (+31 more)

### Community 3 - "Binance Error Handling"
Cohesion: 0.06
Nodes (26): BinanceAPIException, BinanceOrderException, BrokerError, map_binance_error(), Binance-specific error handling and mapping., Initialize BrokerError.          Args:             message: Human-readable error, Map a Binance exception to a BrokerError.      Args:         exc: Binance except, Unified broker error wrapper for Binance exceptions. (+18 more)

### Community 4 - "CLI Display & Broker Factory"
Cohesion: 0.09
Nodes (43): make_futures_broker(), make_spot_broker(), _fmt(), print_active_trade(), print_balance_table(), print_orders_table(), print_positions_table(), print_trade_preview() (+35 more)

### Community 5 - "SDD Tasks & Core Protocols"
Cohesion: 0.09
Nodes (35): SDD Progress Ledger (futures-refactor), ActiveTrade Dataclass, IBroker Protocol, ITradeStore Protocol, MarginType Enum (ISOLATED/CROSS), Position Dataclass, Side Enum (BUY/SELL), Task 1 Brief: Core Domain Types (+27 more)

### Community 6 - "Project Docs & Architecture"
Cohesion: 0.14
Nodes (34): Backtest Live Parity North Star Principle, CLAUDE.md Project Guide, ActiveTrade Domain Type, High-Level Design Document, Database Schema (9 tables with account_id SaaS seam), FuturesBroker, Ports and Adapters Architecture Pattern, IBroker Protocol (9 methods) (+26 more)

### Community 7 - "Trade Domain Model"
Cohesion: 0.08
Nodes (10): ActiveTrade, IBroker, ITradeStore, Protocol, PositionManager, Drives trade lifecycle from price events.      Wired to the WebSocket price feed, _active_trade(), Unit tests for the trade CLI (cli/trade_cli.py) — make_spot_broker is mocked. (+2 more)

### Community 8 - "Infrastructure & Setup"
Cohesion: 0.10
Nodes (23): pgdata volume, postgres service (postgres:16), Quickstart / Local Run Flow, Binance API (REST + WebSocket), Market Data Feed, Multi-Exchange Support (Coinbase, Kraken), Order Execution Module, React SPA Dashboard + Node Backend (+15 more)

### Community 9 - "Futures CLI Tests"
Cohesion: 0.15
Nodes (16): _active_trade(), advance command exits with error when no active trade exists for symbol., advance command exits with error when trade is already at the final stage., move-sl command calls broker.update_stop_loss and updates _active_trades., move-sl command exits with error when no active trade exists for symbol., buy command stores result in _active_trades under the uppercased symbol., close command removes the symbol from _active_trades after success., test_futures_advance_final_stage() (+8 more)

### Community 10 - "Futures Broker Tests"
Cohesion: 0.43
Nodes (13): _buy_plan(), _entry_response(), _fake_client(), _make_broker(), _order_response(), test_advance_stage_cancels_and_replaces(), test_advance_stage_no_next_raises(), test_get_balance_returns_futures_account() (+5 more)

### Community 11 - "Legacy Broker Tests"
Cohesion: 0.34
Nodes (13): _fake_client(), _make_broker(), _otoco_response(), Unit tests for BinanceBroker — all Binance client calls are mocked., Verify weighted-average fill price is computed correctly., test_cancel_order(), test_get_balance_filters_zero(), test_get_open_orders_no_symbol() (+5 more)

### Community 12 - "Database Models"
Cohesion: 0.27
Nodes (11): Base, Account, EquitySnapshot, Fill, Order, Position, ORM models for the trading bot.  SaaS seam: **every** table carries ``account_id, One execution of a strategy in a given mode (backtest/testnet/live). (+3 more)

### Community 13 - "Spot Broker Tests"
Cohesion: 0.42
Nodes (11): _buy_plan(), _fake_client(), _make_broker(), _otoco_response(), test_advance_stage_cancels_and_replaces_orders(), test_cancel_order_delegates_to_client(), test_get_balance_filters_zero_balances(), test_get_positions_returns_empty_list() (+3 more)

### Community 14 - "Market Data Types Tests"
Cohesion: 0.29
Nodes (8): _bar(), Tests for the canonical Bar type — the parity foundation.  The same Bar flows th, test_bar_constructs_and_exposes_fields(), test_bar_is_immutable(), test_close_time_must_be_after_open_time(), test_high_must_be_max_and_low_must_be_min(), test_negative_volume_rejected(), test_open_time_must_be_timezone_aware()

### Community 15 - "Futures Validator Tests"
Cohesion: 0.42
Nodes (8): _plan(), test_buy_sl_above_price_raises(), test_leverage_above_125_raises(), test_leverage_zero_raises(), test_min_notional_too_small_raises(), test_sell_sl_below_price_raises(), test_valid_long_passes(), test_valid_short_passes()

### Community 16 - "DB Model Tests"
Cohesion: 0.48
Nodes (6): _created_inspector(), Schema tests: all tables create, and every table carries the account_id seam., test_all_expected_tables_created(), test_every_table_has_account_id_seam(), test_order_client_order_id_is_unique(), test_position_uniqueness_per_run_symbol()

### Community 17 - "Project Roadmap"
Cohesion: 0.50
Nodes (4): Week 1 Foundations & Data (done), Modular Event-Driven Architecture Proposal, 8-Week Design & Plan, Testing Strategy (unit/mock/parity/testnet)

## Knowledge Gaps
- **25 isolated node(s):** `Quickstart / Local Run Flow`, `Week 1 Foundations & Data (done)`, `pgdata volume`, `Orchestrator/Runtime`, `Risk Controls (kill-switch, drawdown breaker)` (+20 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TradePlan` connect `Futures CLI & Order Domain` to `Binance Error Handling`, `CLI Display & Broker Factory`, `Trade Domain Model`, `Futures CLI Tests`, `Futures Broker Tests`, `Spot Broker Tests`, `Futures Validator Tests`?**
  _High betweenness centrality (0.124) - this node is a cross-community bridge._
- **Why does `Settings` connect `Config & Client Factory` to `Binance Error Handling`?**
  _High betweenness centrality (0.096) - this node is a cross-community bridge._
- **Why does `FuturesBroker` connect `Binance Error Handling` to `Futures CLI & Order Domain`, `Config & Client Factory`, `CLI Display & Broker Factory`, `Trade Domain Model`, `Futures Broker Tests`?**
  _High betweenness centrality (0.090) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `TradePlan` (e.g. with `_active_trade()` and `test_futures_advance_success()`) actually correct?**
  _`TradePlan` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `ActiveTrade` (e.g. with `MarginType` and `Side`) actually correct?**
  _`ActiveTrade` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `ParquetBarStore` (e.g. with `main()` and `KlineDownloader`) actually correct?**
  _`ParquetBarStore` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `map_binance_error()` (e.g. with `test_map_binance_error_extracts_code()` and `.advance_stage()`) actually correct?**
  _`map_binance_error()` has 19 INFERRED edges - model-reasoned connections that need verification._