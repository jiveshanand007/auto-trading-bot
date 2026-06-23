# Graph Report - .  (2026-06-23)

## Corpus Check
- Corpus is ~10,207 words - fits in a single context window. You may not need a graph.

## Summary
- 176 nodes · 269 edges · 17 communities (15 shown, 2 thin omitted)
- Extraction: 82% EXTRACTED · 18% INFERRED · 0% AMBIGUOUS · INFERRED: 48 edges (avg confidence: 0.69)
- Token cost: 38,000 input · 3,718 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Binance Klines Downloader|Binance Klines Downloader]]
- [[_COMMUNITY_Parquet OHLCV Storage|Parquet OHLCV Storage]]
- [[_COMMUNITY_DB Engine, Config & Binance Client|DB Engine, Config & Binance Client]]
- [[_COMMUNITY_Platform Design & Architecture|Platform Design & Architecture]]
- [[_COMMUNITY_Strategy  Risk  Broker Components|Strategy / Risk / Broker Components]]
- [[_COMMUNITY_Download CLI & Logging|Download CLI & Logging]]
- [[_COMMUNITY_ORM Models (account_id seam)|ORM Models (account_id seam)]]
- [[_COMMUNITY_Canonical Bar Type Tests|Canonical Bar Type Tests]]
- [[_COMMUNITY_Market Data Types|Market Data Types]]
- [[_COMMUNITY_DB Schema Tests|DB Schema Tests]]
- [[_COMMUNITY_Dropped Messaging  Polyglot (YAGNI)|Dropped Messaging / Polyglot (YAGNI)]]
- [[_COMMUNITY_Dropped KubernetesDevOps (YAGNI)|Dropped Kubernetes/DevOps (YAGNI)]]

## God Nodes (most connected - your core abstractions)
1. `ParquetBarStore` - 24 edges
2. `Timeframe` - 17 edges
3. `Bar` - 14 edges
4. `KlineDownloader` - 12 edges
5. `Base` - 10 edges
6. `FakeBinanceClient` - 10 edges
7. `KlineFetcher` - 8 edges
8. `_bar()` - 8 edges
9. `main()` - 7 edges
10. `get_settings()` - 6 edges

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
- **Strategy -> Risk -> Broker Parity Pipeline** — specs_2026_06_21_trading_bot_8_week_design_strategy, specs_2026_06_21_trading_bot_8_week_design_risk_manager, specs_2026_06_21_trading_bot_8_week_design_broker_iface, claude_backtest_live_parity [EXTRACTED 1.00]
- **Requirement Event-Driven Data Flow** — requirement_market_data_feed, requirement_strategy_engine, requirement_risk_fund_allocator, requirement_order_execution [EXTRACTED 1.00]
- **YAGNI Scope Cuts (spec narrows requirement)** — requirement_messaging_queue, requirement_kubernetes_devops, requirement_react_dashboard, requirement_multi_exchange [INFERRED 0.85]

## Communities (17 total, 2 thin omitted)

### Community 0 - "Binance Klines Downloader"
Cohesion: 0.12
Nodes (19): KlineDownloader, KlineFetcher, Download historical OHLCV from Binance into the parquet store.  Binance returns, Minimal interface the downloader needs from a Binance client., Map a raw Binance kline row to a canonical :class:`Bar`., Fetch a date range of klines and persist them to the parquet store., Download [start, end] for symbol/timeframe. Returns bars written., raw_kline_to_bar() (+11 more)

### Community 1 - "Parquet OHLCV Storage"
Cohesion: 0.15
Nodes (16): BaseModel, DataFrame, ParquetBarStore, Read/write :class:`Bar` collections as partitioned parquet files., Append bars, de-duplicating on open_time and keeping sorted order.          All, Return bars sorted by open_time, optionally filtered to [start, end]., Bar, One OHLCV candle for a symbol at a timeframe.      Times must be timezone-aware (+8 more)

### Community 2 - "DB Engine, Config & Binance Client"
Cohesion: 0.11
Nodes (18): BaseSettings, make_engine(), make_session_factory(), SQLAlchemy engine, session factory, and declarative base.  Swapping SQLite (dev/, BinanceKlineClient, Thin wrapper over python-binance for historical klines.  Klines are public data,, Fetches historical klines via the Binance REST API., main() (+10 more)

### Community 3 - "Platform Design & Architecture"
Cohesion: 0.10
Nodes (21): account_id SaaS Seam, Backtest/Live Parity (North Star), Canonical Bar Type, config.py Settings (pydantic-settings), DB Schema (8 tables, SQLAlchemy/Alembic), Binance Klines Downloader CLI, Local PostgreSQL 14 (dev DB), Parquet OHLCV Store (+13 more)

### Community 4 - "Strategy / Risk / Broker Components"
Cohesion: 0.15
Nodes (17): Binance API (REST + WebSocket), Market Data Feed, Multi-Exchange Support (Coinbase, Kraken), Order Execution Module, Risk & Fund Allocator, Strategy Engine (Brain), Binance User Data Stream (listenKey), Backtest Engine + Analytics (+9 more)

### Community 5 - "Download CLI & Logging"
Cohesion: 0.16
Nodes (10): BoundLogger, datetime, _now(), _parse_date(), CLI to download historical klines into the parquet store.  Example::      uv run, _as_utc(), Parquet-backed OHLCV storage, partitioned by symbol and timeframe.  Layout::, Normalize a pandas/py datetime to a tz-aware UTC datetime. (+2 more)

### Community 6 - "ORM Models (account_id seam)"
Cohesion: 0.23
Nodes (12): Base, Declarative base for all ORM models., Account, EquitySnapshot, Fill, Order, Position, ORM models for the trading bot.  SaaS seam: **every** table carries ``account_id (+4 more)

### Community 7 - "Canonical Bar Type Tests"
Cohesion: 0.29
Nodes (8): _bar(), Tests for the canonical Bar type — the parity foundation.  The same Bar flows th, test_bar_constructs_and_exposes_fields(), test_bar_is_immutable(), test_close_time_must_be_after_open_time(), test_high_must_be_max_and_low_must_be_min(), test_negative_volume_rejected(), test_open_time_must_be_timezone_aware()

### Community 8 - "Market Data Types"
Cohesion: 0.25
Nodes (6): Enum, Canonical market-data types shared across backtest, testnet, and live.  The :cla, Supported candle intervals, mapped to Binance interval strings., Timeframe, str, timedelta

### Community 9 - "DB Schema Tests"
Cohesion: 0.48
Nodes (6): _created_inspector(), Schema tests: all tables create, and every table carries the account_id seam., test_all_expected_tables_created(), test_every_table_has_account_id_seam(), test_order_client_order_id_is_unique(), test_position_uniqueness_per_run_symbol()

## Knowledge Gaps
- **12 isolated node(s):** `uv Dependency/Venv Management`, `config.py Settings (pydantic-settings)`, `pgdata volume`, `Orchestrator/Runtime`, `Risk Controls (kill-switch, drawdown breaker)` (+7 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ParquetBarStore` connect `Parquet OHLCV Storage` to `Binance Klines Downloader`, `Market Data Types`, `DB Engine, Config & Binance Client`, `Download CLI & Logging`?**
  _High betweenness centrality (0.097) - this node is a cross-community bridge._
- **Why does `main()` connect `DB Engine, Config & Binance Client` to `Binance Klines Downloader`, `Parquet OHLCV Storage`, `Download CLI & Logging`, `Market Data Types`?**
  _High betweenness centrality (0.093) - this node is a cross-community bridge._
- **Why does `Timeframe` connect `Market Data Types` to `Binance Klines Downloader`, `Parquet OHLCV Storage`, `DB Engine, Config & Binance Client`, `Download CLI & Logging`?**
  _High betweenness centrality (0.069) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `ParquetBarStore` (e.g. with `main()` and `KlineDownloader`) actually correct?**
  _`ParquetBarStore` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `Timeframe` (e.g. with `main()` and `KlineDownloader`) actually correct?**
  _`Timeframe` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `Bar` (e.g. with `KlineDownloader` and `KlineFetcher`) actually correct?**
  _`Bar` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `KlineDownloader` (e.g. with `main()` and `ParquetBarStore`) actually correct?**
  _`KlineDownloader` has 8 INFERRED edges - model-reasoned connections that need verification._