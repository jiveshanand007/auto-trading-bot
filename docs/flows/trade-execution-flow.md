# Trade Execution Flow Diagrams

> Last updated: 2026-06-30. Reflects `SpotBroker` + `FuturesBroker` ports-and-adapters architecture.

---

## 1. System Architecture

```mermaid
architecture-beta
    group interface_layer(internet)[Interface Layer]
        service cli(server)[trade CLI - typer + rich] in interface_layer
        service mcp(server)[MCP Server - FastMCP stdio] in interface_layer

    group core_layer(cloud)[Core - pure domain]
        service ibroker(server)[IBroker Protocol] in core_layer
        service domain(disk)[TradePlan / ActiveTrade / TradeStage] in core_layer

    group broker_layer(server)[Broker Adapters]
        service spot_broker(server)[SpotBroker] in broker_layer
        service fut_broker(server)[FuturesBroker] in broker_layer
        service config(disk)[.env Config - BOT_ vars] in broker_layer

    group binance_grp(internet)[Binance Endpoints]
        service spot_testnet(server)[testnet.binance.vision - spot testnet] in binance_grp
        service fut_testnet(server)[testnet.binancefuture.com - futures testnet] in binance_grp
        service spot_live(server)[api.binance.com - spot live] in binance_grp
        service fut_live(server)[fapi.binance.com - futures live] in binance_grp

    cli:R --> L:ibroker
    mcp:R --> L:ibroker
    ibroker:R --> L:spot_broker
    ibroker:R --> L:fut_broker
    config:T --> B:spot_broker
    config:T --> B:fut_broker
    spot_broker:R --> L:spot_testnet
    spot_broker:R --> L:spot_live
    fut_broker:R --> L:fut_testnet
    fut_broker:R --> L:fut_live
```

---

## 2. Spot Trade Execution Flow

Spot uses a single atomic OTOCO order (entry MARKET + OCO with LIMIT_MAKER TP + STOP_LOSS_LIMIT SL).

```mermaid
flowchart TD
    classDef interface fill:#4a90d9,stroke:#2c5f8a,color:#fff
    classDef broker fill:#2ecc71,stroke:#1a7a43,color:#fff
    classDef binance fill:#f39c12,stroke:#9a6208,color:#fff
    classDef decision fill:#ecf0f1,stroke:#7f8c8d,color:#2c3e50
    classDef error fill:#e74c3c,stroke:#922b21,color:#fff
    classDef success fill:#27ae60,stroke:#1a6b3b,color:#fff

    USER(["User / Claude AI"]):::interface

    subgraph INTERFACE ["Interface Layer"]
        CLI["trade buy/sell\ntyper + rich"]:::interface
        MCP["MCP place_spot_trade"]:::interface
    end

    subgraph SPOT ["SpotBroker"]
        VALIDATE{"Validate\nSL / TP vs price"}:::decision
        OTOCO["POST /api/v3/orderList/otoco\nentry MARKET + OCO (TP + SL)\nAtomic — all or nothing"]:::broker
        FILL["Extract fill price\nfrom orderReports"]:::broker
    end

    PANEL["Pre-Trade Panel\nprice · balance · notional\nSL% · TP% · R:R ratio"]:::interface
    CONFIRM{"Confirm?"}:::decision
    RESULT(["ActiveTrade returned\nentry_price · order_ids\ncurrent_stage=0"]):::success

    ERR_CANCEL(["Cancelled"]):::error
    ERR_VALIDATE(["ValueError — nothing sent"]):::error
    ERR_API(["BrokerError — atomic reject\nno position opened"]):::error

    USER --> CLI
    USER --> MCP
    CLI --> PANEL
    MCP --> VALIDATE
    PANEL --> CONFIRM
    CONFIRM -->|"no"| ERR_CANCEL
    CONFIRM -->|"yes"| VALIDATE
    VALIDATE -->|"invalid"| ERR_VALIDATE
    VALIDATE -->|"valid"| OTOCO
    OTOCO -->|"API error"| ERR_API
    OTOCO -->|"ok"| FILL
    FILL --> RESULT
```

---

## 3. Futures Trade Execution Flow

Futures places **three separate orders**: MARKET entry, then STOP_MARKET SL, then TAKE_PROFIT_MARKET TP (each with `closePosition=True`). Leverage and margin type are set first.

```mermaid
flowchart TD
    classDef interface fill:#4a90d9,stroke:#2c5f8a,color:#fff
    classDef broker fill:#7b68ee,stroke:#4b3ba0,color:#fff
    classDef decision fill:#ecf0f1,stroke:#7f8c8d,color:#2c3e50
    classDef error fill:#e74c3c,stroke:#922b21,color:#fff
    classDef success fill:#27ae60,stroke:#1a6b3b,color:#fff

    USER(["User / Claude AI"]):::interface

    subgraph INTERFACE ["Interface Layer"]
        CLI["trade futures buy/sell"]:::interface
        MCP["MCP place_futures_trade"]:::interface
    end

    subgraph FUT ["FuturesBroker"]
        VALIDATE{"Validate\nSL / TP vs price"}:::decision
        LEV["futures_change_leverage\nfutures_change_margin_type"]:::broker
        ENTRY["futures_create_order\nMARKET — fills immediately"]:::broker
        SL_ORD["futures_create_order\nSTOP_MARKET closePosition=True"]:::broker
        TP_ORD["futures_create_order\nTAKE_PROFIT_MARKET closePosition=True"]:::broker
    end

    PANEL["Pre-Trade Panel\nprice · balance · notional\nlev · margin · SL% · TP%"]:::interface
    CONFIRM{"Confirm?"}:::decision
    RESULT(["ActiveTrade returned\nentry_price · sl/tp order ids\ncurrent_stage=0"]):::success

    ERR_CANCEL(["Cancelled"]):::error
    ERR_VALIDATE(["ValueError — nothing sent"]):::error
    ERR_API(["BrokerError\nentry may have filled\nwithout SL/TP protection"]):::error

    USER --> CLI
    USER --> MCP
    CLI --> PANEL
    MCP --> VALIDATE
    PANEL --> CONFIRM
    CONFIRM -->|"no"| ERR_CANCEL
    CONFIRM -->|"yes"| VALIDATE
    VALIDATE -->|"invalid"| ERR_VALIDATE
    VALIDATE -->|"valid"| LEV
    LEV --> ENTRY
    ENTRY -->|"API error"| ERR_API
    ENTRY -->|"filled"| SL_ORD
    SL_ORD --> TP_ORD
    TP_ORD --> RESULT
```

---

## 4. Spot OCO Leg Logic — Which Leg Fires When

```mermaid
flowchart LR
    classDef entry fill:#3498db,stroke:#1a6091,color:#fff
    classDef tp fill:#27ae60,stroke:#1a6b3b,color:#fff
    classDef sl fill:#e74c3c,stroke:#922b21,color:#fff
    classDef cancel fill:#95a5a6,stroke:#616a6b,color:#fff

    BUY_ENTRY(["BUY entry filled\nlong position open"]):::entry
    SELL_ENTRY(["SELL entry filled\nshort position"]):::entry

    subgraph BUY_OCO ["OCO protecting a LONG"]
        direction TB
        BUY_TP["Price rises → hits LIMIT_MAKER @ take_profit\nProfit locked in"]:::tp
        BUY_SL["Price drops → hits STOP_LOSS_LIMIT @ stop_loss\nLoss capped"]:::sl
        BUY_TP -->|"cancels"| BUY_SL_CANCEL["SL cancelled"]:::cancel
        BUY_SL -->|"cancels"| BUY_TP_CANCEL["TP cancelled"]:::cancel
    end

    subgraph SELL_OCO ["OCO protecting a SHORT"]
        direction TB
        SELL_TP["Price drops → hits LIMIT_MAKER @ take_profit\nProfit locked in"]:::tp
        SELL_SL["Price rises → hits STOP_LOSS_LIMIT @ stop_loss\nLoss capped"]:::sl
        SELL_TP -->|"cancels"| SELL_SL_CANCEL["SL cancelled"]:::cancel
        SELL_SL -->|"cancels"| SELL_TP_CANCEL["TP cancelled"]:::cancel
    end

    BUY_ENTRY --> BUY_TP
    BUY_ENTRY --> BUY_SL
    SELL_ENTRY --> SELL_TP
    SELL_ENTRY --> SELL_SL
```

---

## 5. Multi-Stage Futures Trade Lifecycle

A trade can have N stages. Each stage has its own TP and the next stage's SL. Calling `advance` locks in profit by moving the SL above entry.

```mermaid
flowchart TD
    classDef open fill:#3498db,stroke:#1a6091,color:#fff
    classDef stage fill:#7b68ee,stroke:#4b3ba0,color:#fff
    classDef action fill:#f39c12,stroke:#9a6208,color:#fff
    classDef closed fill:#27ae60,stroke:#1a6b3b,color:#fff
    classDef loss fill:#e74c3c,stroke:#922b21,color:#fff

    PLAN(["TradePlan created\nstages=[S0, S1, S2]"]):::open

    PLACE["place_trade\nMARKET entry fills\nSL = initial_stop_loss\nTP = stages[0].take_profit"]:::open

    subgraph STAGE0 ["Stage 0 — in progress"]
        SL0["STOP_MARKET\n@ initial_stop_loss"]:::loss
        TP0["TAKE_PROFIT_MARKET\n@ stages[0].take_profit"]:::stage
    end

    ADVANCE1["advance BTCUSDT\nCancel SL0 + TP0\nPlace SL = stages[0].next_stop_loss\nPlace TP = stages[1].take_profit"]:::action

    subgraph STAGE1 ["Stage 1 — profit locked"]
        SL1["STOP_MARKET\n@ stages[0].next_stop_loss\n(above entry = guaranteed profit)"]:::stage
        TP1["TAKE_PROFIT_MARKET\n@ stages[1].take_profit"]:::stage
    end

    ADVANCE2["advance BTCUSDT\nCancel SL1 + TP1\nPlace SL = stages[1].next_stop_loss\nPlace TP = stages[2].take_profit"]:::action

    subgraph STAGE2 ["Stage 2 — final stage"]
        SL2["STOP_MARKET\n@ stages[1].next_stop_loss"]:::stage
        TP2["TAKE_PROFIT_MARKET\n@ stages[2].take_profit"]:::stage
    end

    HIT_SL(["SL fires — position closed\nrealized loss or locked profit"]):::loss
    HIT_TP(["TP fires — position closed\nmax profit"]):::closed
    CLOSE(["close BTCUSDT\nMARKET close at any time"]):::action

    PLAN --> PLACE
    PLACE --> STAGE0
    SL0 -->|"price hits SL"| HIT_SL
    TP0 -->|"user calls advance"| ADVANCE1
    ADVANCE1 --> STAGE1
    SL1 -->|"price hits SL"| HIT_SL
    TP1 -->|"user calls advance"| ADVANCE2
    ADVANCE2 --> STAGE2
    SL2 -->|"price hits SL"| HIT_SL
    TP2 -->|"price hits TP"| HIT_TP
    STAGE0 -->|"user calls close"| CLOSE
    STAGE1 -->|"user calls close"| CLOSE
    STAGE2 -->|"user calls close"| CLOSE
```

---

## 6. Error Scenarios

```mermaid
flowchart TD
    classDef normal fill:#3498db,stroke:#1a6091,color:#fff
    classDef decision fill:#ecf0f1,stroke:#7f8c8d,color:#2c3e50
    classDef error fill:#e74c3c,stroke:#922b21,color:#fff
    classDef warn fill:#f39c12,stroke:#9a6208,color:#fff
    classDef success fill:#27ae60,stroke:#1a6b3b,color:#fff

    START(["place_trade called"]):::normal

    VALIDATE{"Validate SL / TP\nvs current price"}:::decision
    VAL_ERR(["ValueError\nnothing placed\nno position opened"]):::error

    SPOT_OTOCO["Spot: POST orderList/otoco\nAtomic — all or nothing"]:::normal
    FUT_SEQ["Futures: MARKET → STOP_MARKET → TAKE_PROFIT_MARKET\nNot atomic — partial failure possible"]:::normal

    SPOT_ERR(["BrokerError — atomic reject\nno position opened\ne.g. -1102 bad params\nor insufficient balance"]):::error
    FUT_ERR(["BrokerError — entry may have filled\nbut SL/TP placement failed\nposition is unprotected"]):::warn

    RESULT(["ActiveTrade returned\nposition protected"]):::success

    START --> VALIDATE
    VALIDATE -->|"SL/TP wrong side of price"| VAL_ERR
    VALIDATE -->|"valid — spot"| SPOT_OTOCO
    VALIDATE -->|"valid — futures"| FUT_SEQ
    SPOT_OTOCO -->|"API error"| SPOT_ERR
    SPOT_OTOCO -->|"ok"| RESULT
    FUT_SEQ -->|"SL/TP placement fails"| FUT_ERR
    FUT_SEQ -->|"ok"| RESULT
```
