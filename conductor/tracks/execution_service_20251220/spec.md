# Specification: Trading Execution Service

## 1. Overview
The Trading Execution Service is the final link in the automated trading chain. It receives structured trading decisions from the Decision Engine and executes them on the AsterDEX exchange. It is responsible for order lifecycle management, including automated Take-Profit (TP) and Stop-Loss (SL) placement, and ensures the local state remains consistent with the exchange.

It supports two modes of operation: **Paper Trading** (simulation) and **Live Trading**.

## 2. Core Requirements

### 2.1 Paper Trading Mode (Priority)
- **Configuration:** Utilize the existing `Account.is_paper_trading` boolean field in the database to determine the mode per account.
- **Simulation:**
  - **Market Orders:** Instead of sending orders to the exchange, the service must fetch real-time "Ask" (for Buy) or "Bid" (for Sell) prices from AsterDEX API and simulate an immediate fill.
  - **Fills:** Record the simulated fill price, timestamp, and fees (estimated).
  - **Positions:** detailed tracking of "paper" positions in the local database, distinct from real on-chain positions.
- **Data Source:** Must use the live AsterDEX API to fetch current Order Book / Price data to ensure realistic simulation.
- **Safety:** Paper trading must **never** execute a write operation (create/cancel order) on the real exchange API.

### 2.2 Live Order Execution
- **Market Orders:** Execute 'buy' or 'sell' market orders immediately via AsterDEX API.
- **TP/SL Orchestration:**
  - Place primary market order.
  - Upon confirmation of fill, place TP and SL orders.
  - **Failure Handling:** Retry with exponential backoff; alert on persistent failure.

### 2.3 State Management
- **Source of Truth (Live):** AsterDEX is the authoritative source.
- **Source of Truth (Paper):** Local Database is the authoritative source.
- **Reconciliation:**
  - **Live:** Periodically sync with AsterDEX.
  - **Paper:** No external sync needed, but simulate PnL updates based on live market price.

### 2.4 Risk & Safety
- **Max Leverage:** Hard limit of **25x** (applied to both Paper and Live).
- **Cooldown:** Mandatory cooldown period between trades.
- **Error Handling:** Exponential backoff for API connection errors.

## 3. Architecture

### 3.1 Service Class
`ExecutionService` in `backend/src/app/services/execution/service.py`

### 3.2 Abstraction
- Implement an `ExecutionAdapter` interface (or Strategy pattern).
- `PaperAdapter`: Simulates execution using read-only market data.
- `LiveAdapter`: Uses full `AsterClient` for execution.
- Factory logic to select adapter based on `Account.is_paper_trading`.

### 3.3 Dependencies
- `AsterClient` (read-only for Paper, read-write for Live)
- `DecisionRepository`
- `TradeRepository`
- `AccountRepository` (to check `is_paper_trading` status)

## 4. API & Integration
- **Input:** `TradingDecision`
- **Output:** `ExecutionResult`
- **Events:** Publish events (OrderPlaced, PositionUpdated) - flagged as `is_paper`.
