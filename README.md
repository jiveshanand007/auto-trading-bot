# Trading Bot

Strategy research → live-validation platform for Binance. Single operator now,
architected with an `account_id` seam so it can become multi-tenant SaaS later.

Design & 8-week plan: `docs/superpowers/specs/2026-06-21-trading-bot-8-week-design.md`.

## Stack

- **Python 3.10+**, managed with [uv](https://docs.astral.sh/uv/)
- **python-binance** for market data (and, later, orders/streams)
- **pandas + pyarrow** for parquet OHLCV storage
- **SQLAlchemy 2.0 + Alembic** over **PostgreSQL** (local install or Docker)
- **structlog** structured logging, **pytest** + **ruff**

## Quickstart — run it locally

> There is **no web server / API yet** — that arrives in Weeks 5–6 (live runtime)
> and Week 8 (dashboard). Today you can run the test suite and the historical
> data pipeline, and optionally stand up the database.

**Prereqs:** Python 3.10+ and [uv](https://docs.astral.sh/uv/). Install uv with
`curl -LsSf https://astral.sh/uv/install.sh | sh` (no root needed). A Postgres
(local install or Docker) is only needed for the database steps (6–7).

```bash
# 1. Install dependencies into a local venv
uv sync --extra dev

# 2. configure — copy the example; defaults are fine for local use
cp .env.example .env

# 3. Run the tests — proves everything built so far works (no network/DB needed)
uv run pytest

# 4. Download real historical data from Binance → parquet (needs internet, no API key)
uv run python -m trading_bot.market_data.download_cli \
    --symbols BTCUSDT ETHUSDT --timeframe H1 \
    --start 2024-01-01 --end 2024-02-01

# 5. Verify the data landed
uv run python -c "from trading_bot.config import get_settings; from trading_bot.market_data.storage import ParquetBarStore; from trading_bot.market_data.types import Timeframe; b=ParquetBarStore(get_settings().data_dir).read('BTCUSDT', Timeframe.H1); print(f'{len(b)} bars, first close={b[0].close}')"

# 6. Apply the database schema (after a one-time DB setup — see "Database" below)
uv run alembic upgrade head

# 7. Verify the schema landed — expect 8 tables
PGPASSWORD=bot psql -h 127.0.0.1 -U bot -d trading_bot -c "\dt"
```

Steps 3–5 need **no Postgres and no API keys**. Steps 6–7 need a running Postgres
with the `bot` role + `trading_bot` database created once — see [Database](#database).

## Setup

```bash
uv sync --extra dev          # create venv + install deps
cp .env.example .env         # configure (defaults are fine for klines)
```

## Week 1 — Foundations & data (done)

- Project scaffold, config (`BOT_*` env vars), structured logging
- Canonical `Bar` type — the backtest/live parity foundation
- Parquet OHLCV store, partitioned by `symbol/timeframe`
- Binance historical klines downloader (paginated)
- DB schema (SQLAlchemy models + Alembic migration); every table carries `account_id`

### Download historical klines

```bash
uv run python -m trading_bot.market_data.download_cli \
    --symbols BTCUSDT ETHUSDT --timeframe H1 \
    --start 2024-01-01 --end 2024-02-01
```

Data lands in `data/symbol=<SYM>/timeframe=<TF>/data.parquet`.

### Database

The bot connects as user `bot` / password `bot` to database `trading_bot` on
`localhost:5432` (see `BOT_DATABASE_URL` in `.env`). You can back this with either
a **locally-installed Postgres** or the bundled **Docker** one — pick *one*, since
both use port 5432.

**Option A — local system Postgres (no Docker).** One-time setup creates the role
and database, then applies the schema:

```bash
# Create the role + database (uses your OS Postgres; needs sudo once)
sudo -u postgres psql \
    -c "CREATE ROLE bot LOGIN PASSWORD 'bot' CREATEDB;" \
    -c "CREATE DATABASE trading_bot OWNER bot;"

uv run alembic upgrade head        # apply schema
```

> If `sudo -u postgres psql` asks for a password, your `pg_hba.conf` local lines
> are set to `md5` — switch them to `peer` (the Ubuntu default), then
> `sudo systemctl reload postgresql`.

**Option B — Docker.** Don't run this if a local Postgres already owns port 5432:

```bash
docker compose up -d               # start Postgres
uv run alembic upgrade head        # apply schema
```

**Verify the database is up and the schema applied** (works for either option):

```bash
PGPASSWORD=bot psql -h 127.0.0.1 -U bot -d trading_bot -c "\dt"
```

You should see 8 tables: `accounts, strategies, runs, orders, fills, positions,
equity_snapshots` (+ `alembic_version`).

> Note: historical klines are pulled from Binance **production** (public data);
> the testnet flag only affects trading, which arrives in Week 5.

## Tests & lint

```bash
uv run pytest                # unit tests
uv run ruff check src/ tests/
```
