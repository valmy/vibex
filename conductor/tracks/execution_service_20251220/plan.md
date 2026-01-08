# Implementation Plan - Execution Service

## Phase 1: Paper Trading Engine (Simulation) [checkpoint: 8809a16]

- [x] Task: Scaffold Execution Service & Adapters [11264a9]
- [x] Task: Implement Paper Market Order Simulation [ce50281]
- [x] Task: Implement Paper Position Tracking [9cd1c53]
- [x] Task: Conductor - User Manual Verification 'Phase 1: Paper Trading Engine' (Protocol in workflow.md) [8809a16]

## Phase 2: Live Execution & Safety

- [x] Task: Implement Live Execution Adapter [b98107f]
    - Implement `LiveExecutionAdapter.execute_market_order` using `AsterClient`.
    - **Test:** Mock `AsterClient` and verify correct API calls are made for market orders.

- [x] Task: Implement TP/SL Orchestration (Live & Paper) [2680fd8]
    - Implement logic to place TP/SL orders.
    - **Paper:** Simulate TP/SL as "pending orders" in DB that trigger on price updates.
    - **Live:** Execute actual API calls to place Trigger orders.
    - **Test:** Verify orchestration flow for both modes.

- [ ] Task: Implement Risk Checks (Leverage & Cooldown)
    - Add pre-execution validation for 25x leverage limit.
    - Add cooldown checks.
    - **Test:** Verify order is rejected if leverage > 25x or within cooldown window.

- [ ] Task: Conductor - User Manual Verification 'Phase 2: Live Execution & Safety' (Protocol in workflow.md)

## Phase 3: Reconciliation & Integration

- [ ] Task: Implement Live Position Reconciliation
    - Fetch remote positions from AsterDEX.
    - Reconcile with local DB (Live trades only).
    - **Test:** Verify local state updates to match remote state.

- [ ] Task: Connect Decision Engine to Execution Service
    - Update `DecisionEngine` to call `ExecutionService`.
    - Ensure correct mode (Paper/Live) is used based on Account config.
    - **Test:** E2E test: Generate Decision -> Execution Service called -> Order "Placed" (Mocked).

- [ ] Task: Add Execution Status Endpoints
    - Endpoints to view active Paper/Live positions and status.
    - **Test:** Verify API response.

- [ ] Task: Conductor - User Manual Verification 'Phase 3: Reconciliation & Integration' (Protocol in workflow.md)
