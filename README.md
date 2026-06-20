# Trading Bot

Strategy research → live-validation platform for Binance. Single operator now,
architected with an `account_id` seam so it can become multi-tenant SaaS later.

Design & 8-week plan: `docs/superpowers/specs/2026-06-21-trading-bot-8-week-design.md`.

## Stack

- **Python 3.10+**, managed with [uv](https://docs.astral.sh/uv/)
- **python-binance** for market data (and, later, orders/streams)
- **pandas + pyarrow** for parquet OHLCV storage
- **SQLAlchemy 2.0 + Alembic** over **PostgreSQL** (Docker)
- **structlog** structured logging, **pytest** + **ruff**

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

### Database (needs Docker)

```bash
docker compose up -d         # start Postgres
uv run alembic upgrade head  # apply schema
```

> Note: historical klines are pulled from Binance **production** (public data);
> the testnet flag only affects trading, which arrives in Week 5.

## Tests & lint

```bash
uv run pytest                # unit tests
uv run ruff check src/ tests/
```
