# Automated Trading Bot — 8-Week Design & Plan

**Date:** 2026-06-21
**Author:** jivesha
**Status:** Approved (design); ready for implementation planning

## 1. Goal & Scope

Build a **strategy research → live-validation platform** for a single trader, architected
so it could later become multi-tenant SaaS — but **without** building multi-tenancy now.

Priorities, in order:

1. **Strategy research & profitability measurement** (main goal): backtest → testnet → live
   with real (small) capital, measuring how much profit each strategy actually generates.
2. **Execution/system reliability ("99%")**: the live trading path must be trustworthy so that
   measured profitability is real — no dropped signals, wrong sizes, missed fills, or crashes.
3. **Risk controls** (mandatory even at small scale): position sizing, stop-loss/take-profit,
   daily-drawdown circuit breaker, manual kill-switch.

Single user (the author) trades for now. Not built for scale.

### Out of scope (cut from `requirement.md`, YAGNI for 1 user / 8 weeks)

Seams are kept where noted so a later SaaS build is not blocked.

- ❌ Kafka/Redis messaging → **in-process event bus**
- ❌ Kubernetes → **Docker Compose**
- ❌ Multi-exchange → **Binance only**
- ❌ React SPA + Node backend → **Streamlit** (personal visualization only)
- ❌ Multi-user auth / tenancy → **`account_id` column seam only**
- ❌ Full ELK/Prometheus → **structured logs + a few simple metrics**

## 2. Key Decisions

- **Language: Python-centric core.** Research is the main goal (best ecosystem: pandas,
  vectorbt/backtrader, easy ML later), and a single language in the trading path guarantees
  backtest/live parity. (Author is strongest in Java but accepts a Python ramp-up; Java/polyglot
  considered and rejected because cross-language strategy code breaks parity.)
- **Backtest/live parity is the backbone.** The exact same `Strategy → Risk → Broker` code runs
  in backtest, testnet, and live. Only the **data source** and **broker implementation** swap.
- **Database: PostgreSQL** in a Docker container, with an `account_id` on every table as the one
  SaaS seam built now.
- **Dashboard: Streamlit, last priority**, time-boxed — for the author's own visualization.

## 3. Architecture

```
                 ┌─────────── same code in all modes ───────────┐
 Data source  →  │  Strategy  →  Risk/Portfolio  →  Broker iface │  →  Persistence (Postgres)
                 └──────────────────────────────────────────────┘
 Backtest:   historical bars            +  SimulatedBroker (fees/slippage)
 Testnet:    live WS feed               +  BinanceBroker (testnet)
 Live:       live WS feed               +  BinanceBroker (prod, tiny capital)
```

### Components (small, independently testable units)

- **Market Data** — historical loader (backtest) + live WebSocket feed (testnet/live), both
  emitting a canonical `Bar`/market-event type.
- **Strategy** — clean interface (`on_bar → Signal`). Sample strategies (MA crossover, RSI,
  breakout) prove the framework's generality. This is where research happens.
- **Risk & Portfolio Manager** — position sizing, max position %, max open positions, per-order
  cap, order-rate limit, stop-loss/take-profit, daily-drawdown circuit breaker, manual kill-switch.
  Validates every signal before it becomes an order. Owns portfolio accounting + equity curve.
- **Broker interface** — `SimulatedBroker` (fees + slippage) and `BinanceBroker` (testnet/prod).
  Idempotent orders (`clientOrderId`), user-data-stream fills, reconciliation against exchange truth.
- **Backtest engine + Analytics** — event loop replaying history through the stack; metrics:
  total/CAGR return, Sharpe/Sortino, max drawdown, win rate, profit factor, # trades, avg win/loss,
  exposure. Parameter-sweep / multi-strategy comparison harness.
- **Persistence** — Postgres (Docker). Schema: `accounts, strategies, runs, orders, fills,
  positions, equity_snapshots` — all carrying `account_id`.
- **Orchestrator/Runtime** — wires the event loop per mode (backtest / testnet / live), with state
  recovery on restart.
- **Dashboard** — Streamlit: equity curve, positions, trade history, risk settings, kill-switch.

## 4. Reliability & Risk Design

**Reliability (the "99%" target, earned in Weeks 5–6):**
- Idempotent order placement via `clientOrderId`.
- Reconciliation against exchange truth (user data stream + periodic REST sync).
- WebSocket reconnect, ping/pong, listenKey keepalive.
- Retry with backoff on transient errors; error taxonomy (transient vs fatal); halt-on-persistent.
- Full audit trail of every signal → order → fill; heartbeat; state recovery on restart.

**Risk controls (mandatory):**
- Pre-trade checks: max position size (% equity), max open positions, per-order size cap, order-rate limit.
- Per-trade stop-loss + take-profit.
- Portfolio-level daily-drawdown circuit breaker → kill-switch cancels orders & halts.
- Manual kill-switch.

## 5. Testing Strategy

- **Unit tests** — strategy logic, risk checks, position-sizing math.
- **Mock-Binance tests** — execution paths, partial fills, error/429 handling.
- **Backtest determinism** — golden price series produce known results (parity guard).
- **Testnet integration** — end-to-end signal → order → fill → log on Binance testnet.
- **Paper/dry-run soak** — extended unattended testnet run before live; watch reconciliation,
  memory, and reliability metrics.

## 6. 8-Week Plan (solo)

Weeks 1–3 build the research engine; Weeks 4–7 make it safe and live; Week 8 is dashboard + polish.

| Week | Focus | Key deliverables |
|------|-------|------------------|
| **1** | Foundations & data | Python scaffold (uv/poetry, pytest, ruff, structured logging, config). Postgres-in-Docker + schema (all tables carry `account_id`). Binance historical klines downloader → parquet. Canonical `Bar`/event types. **→ Pull & store OHLCV history.** |
| **2** | Strategy iface + backtest engine | `Strategy` interface, `Broker` interface + `SimulatedBroker` (fees + slippage). Event-driven backtest loop. First strategy (MA crossover). **→ Backtest end-to-end, trade log.** |
| **3** | Analytics + research workflow *(main-goal milestone)* | Metrics (return, CAGR, Sharpe/Sortino, max drawdown, win rate, profit factor, # trades, avg win/loss). Report output (tables + plots, Jupyter-friendly). Parameter-sweep / multi-strategy comparison. 2 more strategies (RSI, breakout). **→ Rigorously compare strategy profitability on history.** |
| **4** | Risk & portfolio manager | Sizing, max position %, max open positions, per-order cap, order-rate limit. Stop-loss/take-profit. Shared portfolio accounting + equity curve. Daily-drawdown circuit breaker + manual kill-switch. Wire risk into backtest. **→ Strategies run through full risk layer.** |
| **5** | Live data + Binance broker (testnet) | Live WebSocket feed (reconnect, ping/pong, multiplex). `BinanceBroker`: signed REST orders, idempotent `clientOrderId`, user-data-stream fills, listenKey keepalive. Testnet config + reconciliation. **→ Place & track orders on testnet through the same stack.** |
| **6** | Live runtime + reliability hardening | Orchestrator running continuously on testnet. Retry/backoff, error taxonomy, halt-on-persistent, full audit log, heartbeat. State recovery on restart. Extended testnet soak. **→ Unattended testnet run for days; clean reconciliation; measure toward 99%.** |
| **7** | Go-live, minimal real capital | Prod broker config + secrets (`.env` uncommitted, no-withdraw key scope, IP allowlist). Pre-live checklist; tiny capital; tight risk caps. Monitor live vs backtest (slippage/fees/fills). **→ Real-money trades executing safely; live profitability measured vs backtest.** |
| **8** | Personal dashboard + polish | Streamlit dashboard (equity curve, positions, trades, risk settings, kill-switch). Buffer for bugfixes, runbook/docs, Docker Compose one-command run. **→ Personal visualization + stable, documented system.** |

### Risk callouts

1. **Python ramp-up** — Weeks 1–2 may run long; buffer is in Week 8. First trim if needed is the
   breakout strategy (Week 3).
2. **The 99% reliability target is earned in Weeks 5–6**, not at the end — hence two full weeks of
   testnet hardening before any real money in Week 7.

## 7. SaaS-Later Seams (built now, cheaply)

- `account_id` on every persisted table.
- Broker credentials loaded per-account (even with one account).
- Strategy config scoped per-account.
- No single-user assumptions hardcoded into schema or runtime context.

(Not built now: auth, user management, billing, multi-tenant isolation, horizontal scaling.)
