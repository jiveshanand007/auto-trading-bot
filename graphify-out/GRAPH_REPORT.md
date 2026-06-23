# Graph Report - .  (2026-06-24)

## Corpus Check
- 10 files · ~12,701 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 256 nodes · 380 edges · 22 communities (19 shown, 3 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 55 edges (avg confidence: 0.72)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Market Data & Parquet Storage|Market Data & Parquet Storage]]
- [[_COMMUNITY_Project Docs & Architecture Concepts|Project Docs & Architecture Concepts]]
- [[_COMMUNITY_ORM Models & DB Session|ORM Models & DB Session]]
- [[_COMMUNITY_DB Engine, Config & Binance HTTP Client|DB Engine, Config & Binance HTTP Client]]
- [[_COMMUNITY_Requirements & Dropped YAGNI Scope|Requirements & Dropped YAGNI Scope]]
- [[_COMMUNITY_BinanceBroker & CLI Test Suite|BinanceBroker & CLI Test Suite]]
- [[_COMMUNITY_Klines Downloader & Tests|Klines Downloader & Tests]]
- [[_COMMUNITY_Trade CLI Commands|Trade CLI Commands]]
- [[_COMMUNITY_Bar Type Tests|Bar Type Tests]]
- [[_COMMUNITY_BinanceBroker Unit Tests|BinanceBroker Unit Tests]]
- [[_COMMUNITY_High-Level Architecture Concepts|High-Level Architecture Concepts]]
- [[_COMMUNITY_MCP Server Tools|MCP Server Tools]]
- [[_COMMUNITY_DB Schema Tests|DB Schema Tests]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 19|Community 19]]

## God Nodes (most connected - your core abstractions)
1. `ParquetBarStore` - 24 edges
2. `Timeframe` - 17 edges
3. `Bar` - 14 edges
4. `KlineDownloader` - 12 edges
5. `Base` - 10 edges
6. `FakeBinanceClient` - 10 edges
7. `BinanceBroker` - 9 edges
8. `KlineFetcher` - 8 edges
9. `_bar()` - 8 edges
10. `BrokerError` - 8 edges

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
- **Live Trading Demo: CLI + MCP Server + BinanceBroker form the end-to-end trade execution path** — specs_2026_06_24_live_trading_demo_design_trade_cli, specs_2026_06_24_live_trading_demo_design_mcp_server, specs_2026_06_24_live_trading_demo_design_binance_broker [EXTRACTED 1.00]
- **OCO trade flow: BinanceBroker places market order then OCO (SL+TP), returning TradeResult** — specs_2026_06_24_live_trading_demo_design_binance_broker, specs_2026_06_24_live_trading_demo_design_oco_order, specs_2026_06_24_live_trading_demo_design_trade_result [EXTRACTED 1.00]
- **Week 1 foundations: Bar type + Parquet Store + DB Schema form the data layer** — claude_bar_type, claude_parquet_store, claude_db_schema_8_tables [INFERRED 0.95]

## Communities (22 total, 3 thin omitted)

### Community 0 - "Market Data & Parquet Storage"
Cohesion: 0.08
Nodes (28): BaseModel, DataFrame, Enum, KlineFetcher, Minimal interface the downloader needs from a Binance client., _as_utc(), ParquetBarStore, Parquet-backed OHLCV storage, partitioned by symbol and timeframe.  Layout:: (+20 more)

### Community 1 - "Project Docs & Architecture Concepts"
Cohesion: 0.08
Nodes (29): 8-Week Trading Bot Design Spec, Backtest/Live Parity North Star, MCP Server (trading_bot.mcp_server), PostgreSQL 14 (local, not Docker), Auto Trading Bot Project, pydantic-settings Config, python-binance Library, SQLAlchemy 2.0 + Alembic (+21 more)

### Community 2 - "ORM Models & DB Session"
Cohesion: 0.11
Nodes (21): BoundLogger, datetime, Base, Declarative base for all ORM models., Account, EquitySnapshot, Fill, _now() (+13 more)

### Community 3 - "DB Engine, Config & Binance HTTP Client"
Cohesion: 0.11
Nodes (18): BaseSettings, make_engine(), make_session_factory(), SQLAlchemy engine, session factory, and declarative base.  Swapping SQLite (dev/, BinanceKlineClient, Thin wrapper over python-binance for historical klines.  Klines are public data,, Fetches historical klines via the Binance REST API., main() (+10 more)

### Community 4 - "Requirements & Dropped YAGNI Scope"
Cohesion: 0.10
Nodes (23): pgdata volume, postgres service (postgres:16), Quickstart / Local Run Flow, Binance API (REST + WebSocket), Market Data Feed, Multi-Exchange Support (Coinbase, Kraken), Order Execution Module, React SPA Dashboard + Node Backend (+15 more)

### Community 5 - "BinanceBroker & CLI Test Suite"
Cohesion: 0.13
Nodes (11): BinanceBroker, BrokerError, Binance broker implementation wrapping python-binance., TradeResult, Exception, Settings, Unit tests for the trade CLI (trade_cli.py) — BinanceBroker is mocked., test_buy_broker_error_exits_nonzero() (+3 more)

### Community 6 - "Klines Downloader & Tests"
Cohesion: 0.16
Nodes (14): KlineDownloader, Map a raw Binance kline row to a canonical :class:`Bar`., Fetch a date range of klines and persist them to the parquet store., Download [start, end] for symbol/timeframe. Returns bars written., raw_kline_to_bar(), FakeBinanceClient, Tests for the Binance klines downloader (pagination + mapping), mocked., A raw Binance kline row for a 1h candle starting at open_ms. (+6 more)

### Community 7 - "Trade CLI Commands"
Cohesion: 0.33
Nodes (11): balance(), _broker(), buy(), cancel(), _die(), orders(), Show non-zero asset balances., Cancel an open order by symbol and order ID. (+3 more)

### Community 8 - "Bar Type Tests"
Cohesion: 0.29
Nodes (8): _bar(), Tests for the canonical Bar type — the parity foundation.  The same Bar flows th, test_bar_constructs_and_exposes_fields(), test_bar_is_immutable(), test_close_time_must_be_after_open_time(), test_high_must_be_max_and_low_must_be_min(), test_negative_volume_rejected(), test_open_time_must_be_timezone_aware()

### Community 9 - "BinanceBroker Unit Tests"
Cohesion: 0.47
Nodes (9): _fake_client(), _make_broker(), Unit tests for BinanceBroker — all Binance client calls are mocked., test_cancel_order(), test_get_balance_filters_zero(), test_get_open_orders_no_symbol(), test_place_trade_api_error_raises_broker_error(), test_place_trade_buy_success() (+1 more)

### Community 10 - "High-Level Architecture Concepts"
Cohesion: 0.22
Nodes (9): account_id SaaS Seam, Canonical Bar Type, DB Schema (8 tables with account_id), Parquet OHLCV Storage, Week 1 Foundations & Data (DONE), Week 1 Foundations & Data (done), Modular Event-Driven Architecture Proposal, 8-Week Design & Plan (+1 more)

### Community 11 - "MCP Server Tools"
Cohesion: 0.22
Nodes (8): cancel_order(), get_balance(), get_open_orders(), place_trade(), Place a market order with automatic stop-loss and take-profit (OCO).      Exampl, Get open orders. Pass symbol like 'BTCUSDT' to filter, or leave empty for all., Get account balances for all non-zero assets., Cancel an open order by symbol and order ID.

### Community 12 - "DB Schema Tests"
Cohesion: 0.48
Nodes (6): _created_inspector(), Schema tests: all tables create, and every table carries the account_id seam., test_all_expected_tables_created(), test_every_table_has_account_id_seam(), test_order_client_order_id_is_unique(), test_position_uniqueness_per_run_symbol()

## Knowledge Gaps
- **22 isolated node(s):** `Quickstart / Local Run Flow`, `pgdata volume`, `Orchestrator/Runtime`, `Risk Controls (kill-switch, drawdown breaker)`, `Testing Strategy (unit/mock/parity/testnet)` (+17 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BinanceBroker` connect `BinanceBroker & CLI Test Suite` to `BinanceBroker Unit Tests`, `Trade CLI Commands`?**
  _High betweenness centrality (0.112) - this node is a cross-community bridge._
- **Why does `main()` connect `DB Engine, Config & Binance HTTP Client` to `Market Data & Parquet Storage`, `ORM Models & DB Session`, `Klines Downloader & Tests`?**
  _High betweenness centrality (0.092) - this node is a cross-community bridge._
- **Why does `ParquetBarStore` connect `Market Data & Parquet Storage` to `DB Engine, Config & Binance HTTP Client`, `Klines Downloader & Tests`?**
  _High betweenness centrality (0.067) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `ParquetBarStore` (e.g. with `main()` and `KlineDownloader`) actually correct?**
  _`ParquetBarStore` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `Timeframe` (e.g. with `main()` and `KlineDownloader`) actually correct?**
  _`Timeframe` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `Bar` (e.g. with `KlineDownloader` and `KlineFetcher`) actually correct?**
  _`Bar` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `KlineDownloader` (e.g. with `main()` and `ParquetBarStore`) actually correct?**
  _`KlineDownloader` has 8 INFERRED edges - model-reasoned connections that need verification._