# Implementation Plan - Execution Service

## Phase 1: Paper Trading Engine (Simulation)

- [x] Task: Scaffold Execution Service & Adapters [11264a9]
    - Create `backend/src/app/services/execution/` directory.
    - Define `ExecutionAdapter` interface (or abstract base class).
    - Implement `PaperExecutionAdapter` skeleton.
    - Implement factory logic to select adapter based on `Account.is_paper_trading`.
    - **Test:** Verify Adapter factory correctly returns `PaperExecutionAdapter` when `account.is_paper_trading` is True.

- [ ] Task: Implement Paper Market Order Simulation
    - Implement `PaperExecutionAdapter.execute_market_order`.
    - Logic: Fetch real-time price from AsterDEX (read-only) -> Create local "Trade" record -> Update local "Position".
    - **Test:** Mock `AsterClient.get_orderbook` / price fetch. Verify `execute_market_order` creates a Trade record with the fetched price without calling `place_order`.

- [ ] Task: Implement Paper Position Tracking
    - Implement logic to track and update simulated positions in local DB.
    - Ensure Paper positions are distinguished from Live positions (implicit via Account).
    - **Test:** Verify opening a paper trade creates a position; verify PnL calculations based on new price updates.

- [ ] Task: Conductor - User Manual Verification 'Phase 1: Paper Trading Engine' (Protocol in workflow.md)

## Phase 2: Live Execution & Safety

- [ ] Task: Implement Live Execution Adapter
    - Implement `LiveExecutionAdapter.execute_market_order` using `AsterClient`.
    - **Test:** Mock `AsterClient` and verify correct API calls are made for market orders.

- [ ] Task: Implement TP/SL Orchestration (Live & Paper)
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
