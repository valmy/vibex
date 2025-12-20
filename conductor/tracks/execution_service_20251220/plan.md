# Implementation Plan - Execution Service

## Phase 1: Core Execution Engine

- [ ] Task: Scaffold Execution Service
    - Create `backend/src/app/services/execution/` directory.
    - Create `service.py`, `exceptions.py`, and `models.py`.
    - **Test:** Verify service can be instantiated and dependencies injected.

- [ ] Task: Implement Basic Market Order Execution
    - Implement `execute_market_order` method.
    - Integrate with AsterDEX client for actual API calls.
    - **Test:** Mock AsterDEX client and verify correct API payload is sent for buy/sell.

- [ ] Task: Implement TP/SL Orchestration
    - Implement logic to place TP and SL orders *after* primary fill.
    - Handle partial fills (optional MVP: assume full fill or wait).
    - **Test:** Verify sequence: Primary Order -> Success -> TP Order + SL Order.

- [ ] Task: Conductor - User Manual Verification 'Phase 1: Core Execution Engine' (Protocol in workflow.md)

## Phase 2: State Reconciliation & Safety

- [ ] Task: Implement Position Reconciliation
    - Create `reconcile_positions` method.
    - Fetch remote positions and compare with local DB.
    - Update/Close local records based on remote state.
    - **Test:** Mock remote state and verify local DB updates (e.g., closing a position that was closed on exchange).

- [ ] Task: Implement Risk Checks (Leverage & Cooldown)
    - Add pre-execution validation for 25x leverage limit.
    - Add cooldown check using last trade timestamp.
    - **Test:** Verify order is rejected if leverage > 25x or within cooldown window.

- [ ] Task: Conductor - User Manual Verification 'Phase 2: State Reconciliation & Safety' (Protocol in workflow.md)

## Phase 3: Integration & API

- [ ] Task: Connect Decision Engine to Execution Service
    - Update `DecisionEngine.make_trading_decision` to call `ExecutionService` when a trade is generated.
    - **Test:** E2E test: Generate Decision -> Execution Service called -> Order "Placed" (Mocked).

- [ ] Task: Add Execution Status Endpoints
    - Create `backend/src/app/api/routes/execution.py`.
    - Endpoints for manual reconciliation trigger and status view.
    - **Test:** Verify API returns correct status.

- [ ] Task: Conductor - User Manual Verification 'Phase 3: Integration & API' (Protocol in workflow.md)
