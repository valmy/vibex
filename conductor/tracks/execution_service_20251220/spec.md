# Specification: Trading Execution Service

## 1. Overview
The Trading Execution Service is the final link in the automated trading chain. It receives structured trading decisions from the Decision Engine and executes them on the AsterDEX exchange. It is responsible for order lifecycle management, including automated Take-Profit (TP) and Stop-Loss (SL) placement, and ensures the local state remains consistent with the exchange.

## 2. Core Requirements

### 2.1 Order Execution
- **Market Orders:** Execute 'buy' or 'sell' market orders immediately upon receiving a signal.
- **TP/SL Orchestration:**
  - If a trade includes TP/SL prices, the service must place the primary market order first.
  - Upon confirmation of the primary fill, it must immediately place the corresponding TP (Limit/Trigger) and SL (Stop/Trigger) orders.
  - **Failure Handling:** If the primary order fills but TP/SL placement fails, the system must retry with exponential backoff. If retries fail, it must alert and potentially close the position to avoid unprotected exposure.

### 2.2 State Management
- **Source of Truth:** AsterDEX is the authoritative source of truth.
- **Reconciliation:** The service must periodically (or event-driven) fetch open positions and orders from AsterDEX and update the local database to match.
- **Stale Data:** Local records of "open" trades that no longer exist on the exchange must be marked as closed/reconciled.

### 2.3 Risk & Safety
- **Max Leverage:** Hard limit of **25x**. Any decision requesting higher leverage must be capped or rejected.
- **Cooldown:** Enforce a mandatory cooldown period (configurable, e.g., 5 minutes) between trades on the same asset to prevent rapid-fire losses.
- **Error Handling:** Implement exponential backoff for API connection errors (HTTP 429, 5xx).

## 3. Architecture

### 3.1 Service Class
`ExecutionService` in `backend/src/app/services/execution/service.py`

### 3.2 Dependencies
- `AsterClient` (from `aster-connector-python` or wrapper)
- `DecisionRepository` (to update decision outcomes)
- `TradeRepository` (to log executed trades)

## 4. API & Integration
- **Input:** `TradingDecision` object (from Decision Engine).
- **Output:** `ExecutionResult` (Success/Fail, Fill Price, Order IDs).
- **Events:** Publish events for WebSocket streaming (OrderPlaced, PositionUpdated).
