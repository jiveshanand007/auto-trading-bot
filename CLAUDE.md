# CLAUDE.md

Guidance for AI agents (and humans) working in this repo. This project is built
**AI-first with minimal human intervention**, so this file is the durable memory:
read it at the start of every session before acting.

## What this is

A **strategy research → live-validation platform** for Binance. Single operator
for now, but every persisted table carries an `account_id` so it can become
multi-tenant SaaS later **without** building multi-tenancy now.

Full design + 8-week plan: **`docs/superpowers/specs/2026-06-21-trading-bot-8-week-design.md`**.
Read it before starting any week's work — it is the source of truth for scope and
"definition of done".

The North Star: **backtest/live parity**. The exact same
`Strategy → Risk → Broker` code runs in backtest, testnet, and live. Only the
*data source* and *broker implementation* swap. Never fork strategy/risk logic
per mode.

## Stack

- **Python 3.10+**, dependency + venv management via **uv** (not pip/poetry directly)
- **python-binance** — market data now; orders/streams in Week 5
- **pandas + pyarrow** — parquet OHLCV storage
- **SQLAlchemy 2.0 + Alembic** over **PostgreSQL**
- **pydantic-settings** for config, **structlog** for logging
- **pytest** + **ruff** for tests + lint

## Environment & key commands

Always run app/Python commands through `uv` so the project venv is used:

```bash
uv sync --extra dev                 # install deps into .venv
uv run pytest                       # run tests (no network/DB needed)
uv run pytest -q                    # quiet
uv run ruff check src/ tests/       # lint
uv run ruff format src/ tests/      # format
uv run alembic upgrade head         # apply DB schema
uv run alembic revision --autogenerate -m "msg"   # new migration
```

Download historical klines (no API key needed — public data):

```bash
uv run python -m trading_bot.market_data.download_cli \
    --symbols BTCUSDT ETHUSDT --timeframe H1 \
    --start 2024-01-01 --end 2024-02-01
```

## Live trading (testnet)

Place trades from the terminal:

```bash
uv run trade buy  BTCUSDT 0.001 --sl 95000 --tp 105000
uv run trade sell BTCUSDT 0.001 --sl 105000 --tp 95000
uv run trade orders            # list open orders
uv run trade orders BTCUSDT    # filter by symbol
uv run trade balance           # show account balances
uv run trade cancel BTCUSDT 12345678
```

Or via Claude (MCP server must be registered — see below):
> "Buy 0.001 BTC with stop loss at 95000 and take profit at 105000"

MCP server: `uv run python -m trading_bot.mcp_server`

Testnet setup (one-time):
1. Go to testnet.binance.vision → log in with GitHub → generate API key
2. Add to `.env`: BOT_BINANCE_API_KEY, BOT_BINANCE_API_SECRET, BOT_BINANCE_TESTNET=true

## Database — IMPORTANT: local Postgres, NOT Docker

This dev machine (WSL2 Ubuntu 22.04) runs a **locally-installed system
PostgreSQL 14** on `localhost:5432`. **Do NOT run `docker compose up`** — the
Docker `postgres:16` in `docker-compose.yml` binds the same port 5432 and will
collide. The Docker file is kept only as an alternative for clean machines.

Connection (set in `.env`, default in `src/trading_bot/config.py`):

```
BOT_DATABASE_URL=postgresql+psycopg2://bot:bot@localhost:5432/trading_bot
```

- **App/bot access:** `PGPASSWORD=bot psql -h 127.0.0.1 -U bot -d trading_bot`
- **Admin access:** `sudo -u postgres psql` (peer auth on the local socket)

One-time DB bootstrap (already done on this machine; documented for rebuilds):

```bash
sudo -u postgres psql \
    -c "CREATE ROLE bot LOGIN PASSWORD 'bot' CREATEDB;" \
    -c "CREATE DATABASE trading_bot OWNER bot;"
uv run alembic upgrade head
```

Gotcha: if `sudo -u postgres psql` prompts for a password, the `local` lines in
`/etc/postgresql/14/main/pg_hba.conf` are set to `md5`; switch them to `peer`
(the Ubuntu default) and `sudo systemctl reload postgresql`. This was already
applied here (backup at `pg_hba.conf.bak`).

Verify schema (expect 8 tables: accounts, strategies, runs, orders, fills,
positions, equity_snapshots, + alembic_version):

```bash
PGPASSWORD=bot psql -h 127.0.0.1 -U bot -d trading_bot -c "\dt"
```

## Configuration

All config is env-driven via `BOT_`-prefixed vars, loaded by
`src/trading_bot/config.py` (pydantic-settings) from `.env`. Copy `.env.example`
to `.env`. Never commit `.env` (real secrets land here from Week 5). Use a
TRADE-only Binance key (no withdraw) when trading work begins.

## Layout

```
src/trading_bot/
  config.py            # Settings (env-driven, single source of truth)
  logging_config.py    # structlog setup
  db/                  # SQLAlchemy base + models (every table has account_id)
  market_data/         # Bar/Timeframe types, parquet store, Binance downloader + CLI
migrations/            # Alembic env + versions
docs/superpowers/specs # design spec / 8-week plan
tests/                 # pytest unit tests (mirror src/ layout)
```

Parquet data lands in `data/symbol=<SYM>/timeframe=<TF>/data.parquet`.

## Conventions

- **uv for everything** — never call bare `python`/`pip`; use `uv run` / `uv add`.
- **Tests first / alongside.** New behavior needs a test in `tests/`. Tests must
  pass with no network and no DB unless the test is explicitly an integration test.
- **`account_id` on every persisted table** — the one SaaS seam. Don't drop it.
- **No mode-specific strategy/risk code** — preserve backtest/live parity.
- **Keep the canonical `Bar` type** as the single market-data interchange type.
- Match surrounding code style; run `ruff` before considering work done.

## Progress & "definition of done" (per the 8-week plan)

- **Week 1 — Foundations & data: DONE.** Scaffold, config, logging, canonical
  `Bar`, parquet store, Binance klines downloader, DB schema (8 tables w/ `account_id`).
- **Week 2 — IN PROGRESS (pivoted to live trading demo):** Building live-trading
  capability ahead of schedule — `trade` CLI (typer + rich), Binance testnet broker,
  MCP server so Claude can place orders conversationally. Backtest loop (`Strategy`,
  `SimulatedBroker`, MA-crossover) remains on the roadmap but follows live wiring.
- **Weeks 3–8:** analytics/research → risk & portfolio → live data + Binance broker
  (testnet) → live runtime + reliability → go-live (tiny capital) → Streamlit
  dashboard. See the spec for each week's deliverables.

When finishing a week, update this section so the next session knows where to start.

## Definition of done for any change

1. `uv run pytest` passes.
2. `uv run ruff check src/ tests/` is clean.
3. DB changes have an Alembic migration and `uv run alembic upgrade head` applies cleanly.
4. README / this file updated if setup, commands, or progress changed.
