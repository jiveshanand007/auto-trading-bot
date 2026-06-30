# Next Phase Design: Strategy Framework, SimulatedBroker, Backtest Engine, Risk & Analytics

> Date: 2026-06-30
> Status: Approved — ready for implementation planning
> Implements: REQ-1 through REQ-7 in `requirement.md`

---

## North Star

Backtest/live parity. The exact same `Strategy → Risk → IBroker` code runs in
backtest, testnet, and live. Only the data source and broker implementation swap.

---

## New Domain Types

### `Signal` — `core/domain/signal.py`

Frozen dataclass produced by a strategy. Single SL/TP (not multi-stage).

```python
@dataclass(frozen=True)
class Signal:
    symbol: str
    side: Side          # from core.domain.order
    quantity: float
    stop_loss: float
    take_profit: float
    reason: str         # human-readable, for audit log
```

### `PortfolioState` — `core/domain/portfolio.py`

Frozen snapshot passed into every `on_bar` call and every risk check.

```python
@dataclass(frozen=True)
class PortfolioState:
    equity: float
    cash: float
    open_positions: list[Position]
    daily_start_equity: float
    is_halted: bool
```

---

## New Protocols

### `IStrategy` — `core/ports/strategy.py`

```python
class IStrategy(Protocol):
    def on_bar(self, bar: Bar, portfolio: PortfolioState) -> Signal | None: ...
    def name(self) -> str: ...
```

Strategies are stateless with respect to portfolio — they maintain only a price
history buffer (internal `deque`) accumulated across `on_bar` calls.
No exchange imports allowed inside strategy code.

### `IRiskManager` — `core/ports/risk.py`

```python
class IRiskManager(Protocol):
    def validate(self, signal: Signal, state: PortfolioState) -> Signal | None: ...
```

Validation is pure (no side effects). Returns adjusted signal or `None` (rejected).

---

## Package Layout

```
src/trading_bot/
  core/
    domain/
      signal.py        # Signal (new)
      portfolio.py     # PortfolioState (new)
      trade.py         # TradePlan, ActiveTrade (existing)
      order.py         # Side, OrderType (existing)
      position.py      # Position (existing)
    ports/
      broker.py        # IBroker (existing)
      strategy.py      # IStrategy (new)
      risk.py          # IRiskManager (new)
      trade_store.py   # ITradeStore (existing)

  strategy/
    __init__.py
    ma_crossover.py    # MACrossoverStrategy
    rsi.py             # RSIStrategy

  risk/
    __init__.py
    manager.py         # RiskManager (concrete implementation)

  backtest/
    __init__.py
    simulated_broker.py  # SimulatedBroker (implements IBroker)
    engine.py            # run_backtest(), signal_to_plan()
    result.py            # BacktestResult, ClosedTrade dataclasses

  analytics/
    __init__.py
    metrics.py           # compute_metrics(), compare_strategies()
```

---

## SimulatedBroker

Implements `IBroker` entirely in memory. No network calls, no DB writes.

**Construction:**
```python
SimulatedBroker(
    initial_capital: float = 10_000.0,
    fee_rate: float = 0.001,       # 0.1% taker
    slippage_rate: float = 0.0005, # 0.05%
)
```

**Fill mechanics:**
- `place_trade(plan)` → records trade as *pending*; does not fill immediately
- `advance_bar(bar)` → called by the engine each tick:
  1. Fills any pending entry at `bar.open` (+ slippage)
  2. Checks open positions: if `bar.low ≤ stop_loss` → SL triggered; if `bar.high ≥ take_profit` → TP triggered
  3. Closed trades move to a completed list; equity updated
- `close_position(symbol)` → fills at current bar's close
- `get_balance()` → `{"USDT": {"free": cash, "locked": margin}}`
- `get_positions()` → list of open simulated `Position` objects

**Invariant:** `SimulatedBroker` must never import from `trading_bot.exchanges`.
This is enforced by `tests/test_parity.py`.

---

## Backtest Engine

### `signal_to_plan(signal: Signal) -> TradePlan`

Pure helper. Wraps a `Signal` into a single-stage `TradePlan`:
- `initial_stop_loss = signal.stop_loss`
- `stages = [TradeStage(take_profit=signal.take_profit, next_stop_loss=signal.stop_loss)]`
- `leverage = 1`, `margin_type = ISOLATED`

### `run_backtest()`

```python
def run_backtest(
    strategy: IStrategy,
    risk: IRiskManager,
    broker: SimulatedBroker,
    bars: list[Bar],
) -> BacktestResult: ...
```

**Loop (per bar, chronological):**
1. `broker.advance_bar(bar)` — SL/TP check + fill pending entries
2. `portfolio = broker.portfolio_state()`
3. `signal = strategy.on_bar(bar, portfolio)`
4. If signal: `approved = risk.validate(signal, portfolio)`
5. If approved: `broker.place_trade(signal_to_plan(approved))`
6. Record equity snapshot

**Rules:**
- No look-ahead bias: strategy only sees bars up to and including the current one
- SL/TP evaluation happens before signal generation on each bar
- Deterministic: same bars + same config → same result (golden-file testable)

### `BacktestResult` — `backtest/result.py`

```python
@dataclass
class ClosedTrade:
    symbol: str
    side: Side
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    entry_bar_index: int
    exit_bar_index: int

@dataclass
class BacktestResult:
    strategy_name: str
    symbol: str
    initial_capital: float
    trades: list[ClosedTrade]
    equity_curve: pd.Series   # index = bar open_time, value = equity
```

---

## Strategies

### `MACrossoverStrategy(fast: int = 9, slow: int = 21, quantity: float = 0.001)`

- Maintains an internal `deque` of close prices
- On each bar: compute fast EMA and slow EMA over the accumulated buffer
- BUY signal when fast EMA crosses above slow EMA (previous bar: fast < slow; current: fast > slow)
- SELL signal when fast EMA crosses below slow EMA
- SL = entry_price × 0.98 (2% below entry); TP = entry_price × 1.04 (4% above entry)
- No signal until buffer has at least `slow` bars

### `RSIStrategy(period: int = 14, oversold: float = 30, overbought: float = 70, quantity: float = 0.001)`

- Maintains an internal `deque` of close prices
- RSI computed from accumulated closes using Wilder's smoothing
- BUY signal when RSI crosses above `oversold` threshold
- SELL signal when RSI crosses below `overbought` threshold
- SL/TP same proportional rules as MA crossover
- No signal until buffer has at least `period + 1` bars

---

## RiskManager

`risk/manager.py` implements `IRiskManager`.

**Constructor:**
```python
RiskManager(
    max_position_pct: float = 0.20,
    max_open_positions: int = 3,
    max_order_usdt: float = 1000.0,
    max_daily_drawdown_pct: float = 0.05,
)
```

**Six checks (in order), any failure returns `None` and logs rejection reason:**
1. **Halted** — if `state.is_halted` or internal `_halted`, reject all signals
2. **Max position size** — `signal.quantity × current_price ≤ max_position_pct × state.equity`
3. **Max open positions** — `len(state.open_positions) < max_open_positions`
4. **Per-order cap** — `signal.quantity × current_price ≤ max_order_usdt`
5. **SL/TP validity** — for BUY: `stop_loss < current_price < take_profit`; for SELL: reversed
6. **Daily drawdown circuit breaker** — if `(state.daily_start_equity - state.equity) / state.daily_start_equity > max_daily_drawdown_pct` → set `_halted = True`, reject

**Methods:**
- `halt()` → set `_halted = True`
- `reset()` → set `_halted = False`

Note: For checks 2, 4, 5 the RiskManager uses the signal's stop_loss/take_profit
proximity as a price proxy in backtest context. In live mode a price lookup would be injected.

---

## Analytics

`analytics/metrics.py`

**`compute_metrics(result: BacktestResult) -> AnalyticsResult`**

```python
@dataclass
class AnalyticsResult:
    strategy_name: str
    total_return_pct: float
    cagr: float
    sharpe: float
    sortino: float
    max_drawdown_pct: float
    win_rate_pct: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    total_trades: int
    exposure_pct: float
    equity_curve: pd.Series
```

Formulas:
- Total return: `(final_equity - initial) / initial × 100`
- CAGR: `(final/initial)^(365/days) - 1` where days = calendar days in backtest span
- Sharpe: `mean(daily_returns) / std(daily_returns) × √252`
- Sortino: `mean(daily_returns) / std(negative_daily_returns) × √252`
- Max drawdown: `max((peak - trough) / peak)` over cumulative equity curve
- Win rate: `winning_trades / total_trades × 100`
- Profit factor: `gross_profit / gross_loss` (0 if no losses)
- Avg win/loss: per-trade PnL averages
- Exposure: `bars_in_position / total_bars × 100`

Dependencies: `numpy` added to `pyproject.toml`.

**`compare_strategies(results: list[BacktestResult]) -> rich.Table`**

Returns a Rich `Table` with one row per strategy, all metrics columns, sorted by Sharpe descending.

---

## CLI — Backtest Command

New `backtest` subcommand added to `cli/trade_cli.py`.

```bash
# Single strategy
uv run trade backtest \
    --strategy ma-crossover \
    --symbol BTCUSDT \
    --timeframe H1 \
    --start 2024-01-01 \
    --end 2024-06-01 \
    --capital 10000 \
    --fee 0.001

# Compare strategies
uv run trade backtest \
    --strategy ma-crossover rsi \
    --symbol BTCUSDT \
    --timeframe H1 \
    --start 2024-01-01 --end 2024-06-01
```

Data loading: reads from parquet store; if data is missing for the requested
symbol/timeframe/date range, auto-downloads from Binance before running.

Output: Rich table of all 10 metrics + ASCII sparkline equity curve.
Multi-strategy: calls `compare_strategies()` for side-by-side Rich table.

---

## Parity Guard — `tests/test_parity.py`

Two tests:

1. **Determinism test** — run the same strategy + bars twice, assert `BacktestResult`
   trades and equity curve are identical.

2. **Exchange isolation test** — grep `src/trading_bot/backtest/simulated_broker.py`
   for any import of `trading_bot.exchanges` and assert none found. This is the
   mechanical enforcement of the parity promise.

---

## Test Coverage Plan

| File | What it covers |
|---|---|
| `tests/strategy/test_ma_crossover.py` | Synthetic bar sequences, crossover timing, warmup period |
| `tests/strategy/test_rsi.py` | RSI crossover detection, oversold/overbought thresholds |
| `tests/risk/test_manager.py` | Each of 6 checks, halt/reset, rejection logging |
| `tests/backtest/test_simulated_broker.py` | Fill logic, SL/TP triggers, fee+slippage, advance_bar |
| `tests/backtest/test_engine.py` | Full loop determinism (golden-file), no look-ahead |
| `tests/analytics/test_metrics.py` | Each metric formula with known inputs |
| `tests/test_parity.py` | Determinism + exchange isolation grep |

Target: ≥ 80% coverage on all new modules. All tests pass with no network, no DB.

---

## Definition of Done

1. `uv run pytest` passes (coverage ≥ 80% on new modules)
2. `uv run ruff check src/ tests/` clean
3. `uv run trade backtest --strategy ma-crossover --symbol BTCUSDT --timeframe H1 --start 2024-01-01 --end 2024-06-01` produces a full metrics table
4. Parity guard test passes
5. `SimulatedBroker` never imports from `trading_bot.exchanges` (enforced by test)
