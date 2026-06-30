# Live Strategy Runner — Design Spec

> Date: 2026-06-30
> Status: Approved — ready for implementation planning

---

## Goal

Wire the existing `Strategy → RiskManager → IBroker` stack to real-time Binance
WebSocket kline feeds so strategies execute automatically on testnet (and later live)
without manual intervention.

**NFR: speed is first-class.** Every microsecond of avoidable latency before the
broker REST call is eliminated.

---

## North Star

Same parity guarantee as backtest: the identical `Strategy → Risk → IBroker` code
runs in backtest, testnet, and live. Only the data source (WebSocket vs parquet) and
broker implementation (SimulatedBroker vs SpotBroker/FuturesBroker) swap.

---

## Architecture

```
Binance WebSocket (one stream per symbol/timeframe)
        ↓
    WsFeed                  emits Bar only on closed klines (kline.x == True)
        ↓
  asyncio.Queue[Bar]        decouples feed from processing
        ↓
    Runner coroutine        one per symbol/strategy pair
        ↓
  IStrategySelector.select(symbol, timeframe) → IStrategy
        ↓
  strategy.on_bar(bar, portfolio) → Signal | None
        ↓
  RiskManager.validate(signal, state) → Signal | None
        ↓
  await broker.place_trade(plan)      async REST via aiohttp — never blocks loop
```

One shared `RiskManager` per market type (spot / futures) so portfolio-level
limits (max open positions, daily drawdown) apply across all symbols.

---

## Components

### `market_data/ws_feed.py` — WebSocket Feed

- Uses `python-binance` `AsyncClient` + `BinanceSocketManager`
- Subscribes to `<symbol>@kline_<interval>` streams
- Filters `kline.x == True` before constructing and emitting a `Bar`
- One `asyncio.Queue[Bar]` per symbol/timeframe pair
- Reconnection handled automatically by `python-binance` — no custom retry logic

### `core/ports/strategy_selector.py` — IStrategySelector Protocol

```python
class IStrategySelector(Protocol):
    def select(self, symbol: str, timeframe: Timeframe) -> IStrategy: ...
```

Extension point for future auto-selection (regime detection, rolling Sharpe, etc.).
Today's implementation reads from config. Tomorrow's picks based on market conditions.

### `runner/config.py` — Config Loader

Pydantic models for `runner.yaml`. Validated at startup — bad config fails fast
with a clear error message, never silently.

```yaml
capital: 10000.0
fee_rate: 0.001

strategies:
  - strategy: ma-crossover
    symbol: BTCUSDT
    timeframe: H1
    market: spot          # spot | futures
    params:
      fast: 9
      slow: 21

  - strategy: rsi
    symbol: ETHUSDT
    timeframe: H1
    market: futures
    params:
      period: 14
      oversold: 30
      overbought: 70
```

`params` passed directly to the strategy constructor — zero runner code changes
needed to add a new strategy.

### `runner/config_selector.py` — ConfigSelector

Implements `IStrategySelector`. Returns a **new** strategy instance each time
`select()` is called. The runner calls `select()` **once per coroutine at startup**
and holds the instance for the lifetime of that coroutine — so each symbol/strategy
pair accumulates its own price buffer independently across bars.

### `runner/live_runner.py` — Async Live Runner

Core orchestration:

1. **Startup:**
   - Install `uvloop` as the event loop engine
   - Load and validate `runner.yaml`
   - For each configured symbol: fetch the last **500 closed bars** via REST to
     warm up strategy price buffers (covers MA slow=200 + RSI period=21 with
     headroom; EMA/RSI ready from bar 1, no cold-start lag)
   - Query `broker.get_positions()` to reconstruct in-memory state from any
     existing open positions (state recovery on restart)
   - Subscribe to WebSocket feeds

2. **Per closed bar (hot path):**
   - Dequeue `Bar` from `asyncio.Queue`
   - `selector.select(symbol, timeframe)` → strategy
   - `strategy.on_bar(bar, portfolio)` → signal (pure, in-memory, ~0.1ms)
   - `risk.validate(signal, state)` → approved signal (pure checks, ~0.01ms)
   - `await broker.place_trade(plan)` → REST call via aiohttp (~50–200ms network)
   - Log result asynchronously — never on the critical path

3. **Fault isolation:**
   Each symbol/strategy pair runs in its own coroutine. Unhandled exceptions
   are caught, logged, and that coroutine restarts after backoff. Other symbols
   are unaffected.

4. **Graceful shutdown (SIGINT / SIGTERM):**
   - Cancel all feed coroutines
   - Await in-flight broker calls
   - Positions remain open on the exchange (managed by their SL/TP orders)
   - No automatic position closing on shutdown

### CLI — `uv run trade run`

```bash
uv run trade run --config runner.yaml
uv run trade run --config runner.yaml --dry-run   # log signals, skip order placement
```

`--dry-run` routes to `SimulatedBroker` instead of the real broker — full live
flow exercised without touching the exchange.

---

## Performance Design

| Decision | Rationale |
|---|---|
| `uvloop` event loop | libuv-based, 2–4× faster than CPython default. One line: `uvloop.install()`. Falls back to asyncio if removed. Linux/macOS only. |
| `AsyncClient` (python-binance) | Native async REST via `aiohttp` — no thread pool overhead |
| `aiohttp` session reused | Persistent TCP connection to Binance REST — no reconnect cost per order |
| Strategy buffers pre-warmed via REST | First closed bar fires immediately |
| No DB writes on signal→order path | DB persistence runs async after order placed |
| One `asyncio.Queue` per feed | Feed never waits on strategy computation |
| `structlog` bound once per runner | No per-call logger construction overhead |

**Critical path target: < 1ms from `kline.x == True` to `broker.place_trade()` call.**
The network round-trip to Binance (~50–200ms) is the only irreducible latency.

---

## Error Taxonomy

| Category | Example | Action |
|---|---|---|
| Transient | Network blip, Binance 429 | Exponential backoff, retry up to 3× |
| Signal rejected | Risk check fails, bad SL/TP | Log + skip, loop continues |
| Fatal | Invalid API key, daily drawdown breached | Halt that symbol's coroutine, others continue |

---

## State Recovery on Restart

1. On startup, call `broker.get_positions(symbol)` for each configured symbol
2. Fetch last `N` closed bars via REST to warm strategy buffers
3. Resume loop — existing positions tracked, no orphaned trades

---

## Testing Strategy

**Unit tests (no network):**
- `WsFeed` — fake WebSocket pushes kline JSON; assert Bar emitted only on `kline.x == True`
- `ConfigSelector` — in-memory config dict; assert correct strategy returned per symbol
- Runner loop — mock feed queue + mock broker; assert signal flow end-to-end

**Integration tests (testnet, opt-in):**
- Marked `@pytest.mark.integration`, skipped by default
- Real WebSocket → real strategy → real testnet order
- Not part of `uv run pytest`

---

## File Layout

```
src/trading_bot/
  market_data/
    ws_feed.py                 # WebSocket kline subscriber → Bar
  core/ports/
    strategy_selector.py       # IStrategySelector protocol
  runner/
    __init__.py
    config.py                  # Pydantic models for runner.yaml
    config_selector.py         # ConfigSelector: IStrategySelector from config
    live_runner.py             # Async event loop — wires everything
  cli/
    trade_cli.py               # +run subcommand

runner.yaml                    # User config (gitignored)
runner.yaml.example            # Committed example
```

---

## Dependencies to Add

- `uvloop` — fast event loop engine
- `pyyaml` — runner config parsing

---

## Definition of Done

1. `uv run trade run --config runner.yaml.example --dry-run` runs without errors,
   logs signals on each closed H1 bar
2. `uv run pytest` passes (unit tests, no network)
3. `uv run ruff check src/ tests/` clean
4. Per-symbol fault isolation verified: one failing coroutine does not affect others
5. State recovery verified: restart mid-run, open positions detected and tracked
