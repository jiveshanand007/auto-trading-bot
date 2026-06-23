# Live Trading Demo — Design Spec

**Date:** 2026-06-24  
**Goal:** Demoable in one week. Place a real market order with stop-loss and take-profit on Binance testnet, triggered from the terminal or by an AI agent.

---

## 1. Scope

Build the minimum needed to execute a trade end-to-end:

- `BinanceBroker` — places a market entry + OCO (stop-loss/take-profit) on Binance testnet
- `trade` CLI — terminal command to trigger trades
- MCP server — exposes broker tools so Claude (or any MCP-compatible AI) can trigger trades

**Out of scope (later weeks):** Strategy interface, SimulatedBroker, backtest engine, event loop, position DB writes.

---

## 2. Architecture

```
CLI (typer)  ──┐
               ├──▶  BinanceBroker  ──▶  Binance Testnet REST API
MCP server   ──┘
```

Single broker implementation, two thin interface layers. The existing `Settings` class (`BOT_BINANCE_API_KEY`, `BOT_BINANCE_API_SECRET`, `BOT_BINANCE_TESTNET=true`) plugs in with no config changes.

---

## 3. BinanceBroker

**Location:** `src/trading_bot/broker/binance_broker.py`

**Responsibilities:**
1. Accept a trade request: symbol, side (BUY/SELL), quantity, stop_loss price, take_profit price
2. Place a market order to enter the position
3. On fill confirmation, place an OCO order:
   - Take-profit leg: limit order at `take_profit`
   - Stop-loss leg: stop-limit order at `stop_loss` (limit = stop_loss × 0.999 to ensure fill)
4. Return a `TradeResult` dataclass: entry fill price, entry order ID, OCO order list ID

**Key design decisions:**
- OCO is placed synchronously after market fill (REST poll for fill, max 5s / 10 retries)
- No position persistence to DB in this iteration — that comes with the backtest integration
- Raises `BrokerError` (custom exception) on any Binance API error, with the raw error attached

**Binance testnet base URL:** `https://testnet.binance.vision/api`

---

## 4. CLI

**Location:** `src/trading_bot/trade_cli.py`  
**Entrypoint:** `uv run trade` (registered as a script in `pyproject.toml`)

**Commands:**

```bash
# Place a trade
trade buy  BTCUSDT 0.001 --sl 95000 --tp 105000
trade sell BTCUSDT 0.001 --sl 105000 --tp 95000

# Inspect
trade orders          # list open orders for all symbols
trade orders BTCUSDT  # filter by symbol
trade balance         # show USDT + BTC testnet balance

# Cancel
trade cancel ORDER_ID
```

**Output:** human-readable table via `rich` (already a transitive dep, or add it explicitly). On success, prints fill price, order IDs, and a confirmation line.

---

## 5. MCP Server

**Location:** `src/trading_bot/mcp_server.py`  
**Transport:** stdio (compatible with Claude Code MCP integration out of the box)  
**Package:** `mcp[cli]` added to dev extras

**Tools exposed:**

| Tool | Arguments | Returns |
|------|-----------|---------|
| `place_trade` | symbol, side, quantity, stop_loss, take_profit | TradeResult as JSON |
| `get_open_orders` | symbol (optional) | list of open orders |
| `get_balance` | — | dict of asset → free/locked |
| `cancel_order` | symbol, order_id | confirmation |

Claude usage example:
> "Buy 0.001 BTC with stop loss at 95000 and take profit at 105000"
→ Claude calls `place_trade(symbol="BTCUSDT", side="BUY", quantity=0.001, stop_loss=95000, take_profit=105000)`

**MCP server registration:** add to `.claude/settings.json` under `mcpServers` so it's auto-loaded in Claude Code sessions.

---

## 6. Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Binance API error on market order | Raise `BrokerError`, surface message to CLI/MCP, no OCO placed |
| Market order fills but OCO fails | Log warning with order ID; user must cancel/manage manually; surface clearly |
| Invalid SL/TP (e.g. SL above entry for a BUY) | Validate before sending, raise `ValueError` with clear message |
| Missing API keys | Raise `ConfigError` at broker init time with setup instructions |

---

## 7. Testing

- **Unit tests** (`tests/test_broker.py`): mock `python-binance` client, test OCO construction logic, validate SL/TP parameter assembly, test `BrokerError` propagation
- **Unit tests** (`tests/test_cli.py`): test CLI argument parsing and output formatting with broker mocked
- **Integration test** (marked `@pytest.mark.integration`): real testnet call, skipped in CI unless `BOT_BINANCE_API_KEY` is set

---

## 8. Setup (Testnet Keys)

1. Go to [testnet.binance.vision](https://testnet.binance.vision) → log in with GitHub
2. Generate API key + secret
3. Add to `.env`:
   ```
   BOT_BINANCE_API_KEY=<your-testnet-key>
   BOT_BINANCE_API_SECRET=<your-testnet-secret>
   BOT_BINANCE_TESTNET=true
   ```
4. Testnet gives 1 BTC + 10,000 USDT automatically

---

## 9. New Dependencies

```toml
dependencies = [
    # existing...
    "typer>=0.12",
    "rich>=13.0",
]

[project.optional-dependencies]
dev = [
    # existing...
    "mcp[cli]>=1.0",
]

[project.scripts]
trade = "trading_bot.trade_cli:app"
```

---

## 10. Definition of Done

- [ ] `uv run trade buy BTCUSDT 0.001 --sl 95000 --tp 105000` fires a real testnet trade with OCO
- [ ] Claude Code can trigger the same trade via MCP tools
- [ ] `uv run pytest` passes (no network needed for unit tests)
- [ ] `uv run ruff check src/ tests/` clean
