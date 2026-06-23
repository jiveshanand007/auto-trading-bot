# Binance REST API Reference

Source: https://developers.binance.com/docs/algo/general-info (and related Binance API docs)
Captured for offline reference. Relevant to this trading bot.

## Base Endpoints

| Environment | URL |
|-------------|-----|
| Live (primary) | `https://api.binance.com` |
| Live (alts, faster but less stable) | `https://api1.binance.com` … `https://api4.binance.com` |
| Spot testnet | `https://testnet.binance.vision` |
| Paper trading (demo) | `https://demo-api.binance.com` |
| Futures testnet | `https://testnet.binancefuture.com` |
| Futures live (USDT-M) | `https://fapi.binance.com` |

**Config:** set via `BOT_BINANCE_TESTNET_URL` / `BOT_BINANCE_LIVE_URL` in `.env`.

---

## HTTP Return Codes

| Code | Meaning |
|------|---------|
| 4XX | Malformed request — issue on sender's side |
| 403 | WAF limit violated |
| 409 | cancelReplace partially succeeded |
| 429 | Rate limit exceeded — back off immediately |
| 418 | IP auto-banned after repeated 429s |
| 5XX | Internal Binance error — execution status UNKNOWN, may have succeeded |

---

## Rate Limits

- **IP limit:** 6,000 weight per minute across all `/api/*` endpoints
- **Order limit:** per account, tracked separately
- Response header `X-MBX-USED-WEIGHT-1M` shows current IP weight used
- Response header `X-MBX-ORDER-COUNT-1M` shows current order count
- On 429: check `Retry-After` header; on 418: you are banned until `Retry-After`
- **Do not spam after a 429** — it escalates to an IP ban (2 min → 3 days)

---

## Security Types

| Type | Description |
|------|-------------|
| NONE | Public endpoint, no key needed |
| TRADE | Requires API key + HMAC signature |
| USER_DATA | Requires API key + HMAC signature |
| USER_STREAM | Requires API key only (no signature) |
| MARKET_DATA | Requires API key only |

**Important:** API keys cannot TRADE by default — must enable trading in API Management.

---

## Signed Request Format (HMAC)

All TRADE / USER_DATA endpoints require:
1. `timestamp` param (milliseconds, current time)
2. `signature` param — HMAC-SHA256 of the full query string + body, using secret key as signing key

```
signature = HMAC-SHA256(secret_key, query_string + body)
```

`recvWindow` (optional, default 5000ms, max 60000ms) — request rejected if `serverTime - timestamp > recvWindow`.

---

## Key Endpoints Used by This Bot

### Market Data (public, no auth)
```
GET /api/v3/ticker/price?symbol=BTCUSDT
```

### Account Balance (USER_DATA)
```
GET /api/v3/account
```
Returns `balances[]` array with `{asset, free, locked}`.

### Place Market Order (TRADE)
```
POST /api/v3/order
  symbol, side (BUY|SELL), type=MARKET, quantity
```

### Place OCO Order — New Format (TRADE)
```
POST /api/v3/orderList/oco
```

**Required params (as of 2024+ API):**

For a **SELL OCO** (after a BUY entry — protecting a long position):
```
symbol       = BTCUSDT
side         = SELL
quantity     = 0.0016
aboveType    = LIMIT_MAKER          # take-profit leg (triggers when price rises)
abovePrice   = <take_profit>
belowType    = STOP_LOSS_LIMIT      # stop-loss leg (triggers when price drops)
belowStopPrice = <stop_loss>
belowPrice   = <stop_loss * 0.999>  # limit price after stop triggers
belowTimeInForce = GTC
```

For a **BUY OCO** (after a SELL entry — protecting a short position):
```
symbol       = BTCUSDT
side         = BUY
quantity     = 0.0016
aboveType    = STOP_LOSS_LIMIT      # stop-loss leg (triggers when price rises)
aboveStopPrice = <stop_loss>
abovePrice   = <stop_loss * 1.001>
aboveTimeInForce = GTC
belowType    = LIMIT_MAKER          # take-profit leg (triggers when price drops)
belowPrice   = <take_profit>
```

> **Note:** Old `create_oco_order()` in python-binance uses legacy params without `aboveType`/`belowType`
> and will fail with `-1102` on the demo and newer live API.
> Use `client._post("orderList/oco", True, data={...})` directly.

### Get Open Orders (USER_DATA)
```
GET /api/v3/openOrders?symbol=BTCUSDT
```

### Cancel Order (TRADE)
```
DELETE /api/v3/order
  symbol, orderId
```

---

## Lot Size Rules (BTCUSDT)

Binance enforces `LOT_SIZE` filter per symbol. For BTCUSDT:
- Min qty: `0.00001` BTC
- Step size: `0.00001` BTC
- Quantity must be a multiple of step size

Check live rules via:
```
GET /api/v3/exchangeInfo?symbol=BTCUSDT
```

---

## Key Signature Types

| Type | Notes |
|------|-------|
| HMAC-SHA256 | Most common, case-insensitive signature |
| RSA (PKCS#8) | Signature is base64-encoded, case-sensitive |
| Ed25519 | Recommended for best performance + security |

python-binance uses HMAC by default.
