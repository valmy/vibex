# What Needs to Be Done: E2E Tests for Decisions/Generate with Real Data

## Executive Summary

To make E2E tests for `/api/v1/decisions/generate` use real data successfully, **5 specific changes** are needed:

| # | Task | Priority | Time | Status |
|---|------|----------|------|--------|
| 1 | Add authentication dependency to endpoint | 🔴 CRITICAL | 5 min | ❌ TODO |
| 2 | Fix async event loop in test fixtures | 🔴 HIGH | 30 min | ❌ TODO |
| 3 | Create test database fixtures with real data | 🔴 HIGH | 1 hour | ❌ TODO |
| 4 | Update E2E tests to use real data | 🔴 HIGH | 1-2 hours | ❌ TODO |
| 5 | Add real data verification assertions | 🟡 MEDIUM | 30 min | ❌ TODO |

**Total Effort**: ~3-4 hours

---

## Current State vs Desired State

### Current State ❌
```
E2E Tests
  ├─ Mock Decision Engine
  ├─ Mock LLM Service
  ├─ Mock Context Builder
  └─ Return Mock Decision
  
Result: Tests don't use real data from database
```

### Desired State ✅
```
E2E Tests
  ├─ Real Decision Engine
  │  ├─ Real Context Builder
  │  │  ├─ Real Market Data (from database)
  │  │  ├─ Real Account Data (from database)
  │  │  └─ Real Technical Indicators (calculated)
  │  ├─ Mock LLM Service (avoid API costs)
  │  └─ Real Decision Validator
  └─ Return Real Decision with Real Data
  
Result: Tests validate entire real data flow
```

---

## Problem #1: Authentication Not Enforced

### Current Issue
- Endpoint accepts requests **without valid JWT tokens**
- Tests expect 401 Unauthorized but get 200 OK
- Security vulnerability

### Root Cause
The `/api/v1/decisions/generate` endpoint doesn't have authentication dependency.

### Solution
Add `get_current_user` dependency to the endpoint.

**File**: `backend/src/app/api/routes/decision_engine.py` (Line 79-80)

```python
# BEFORE
@router.post("/generate", response_model=DecisionResult)
async def generate_decision(request: DecisionRequest):

# AFTER
@router.post("/generate", response_model=DecisionResult)
async def generate_decision(
    request: DecisionRequest,
    current_user: User = Depends(get_current_user)
):
```

**Why**: Ensures only authenticated users can generate decisions.

---

## Problem #2: Async Event Loop Closed

### Current Issue
- 7 E2E tests fail during fixture setup
- Error: `RuntimeError: Event loop is closed`
- Error: `AttributeError: 'NoneType' object has no attribute 'send'`
- Blocks authenticated_client fixture from working

### Root Cause
Database connections not properly cleaned up on Windows. The asyncio event loop closes before database cleanup completes.

### Solution
Implement proper async context management in fixtures.

**File**: `backend/tests/conftest.py`

Add proper cleanup:
```python
@pytest_asyncio.fixture
async def authenticated_client(async_client, test_wallet):
    try:
        # ... authentication code ...
        yield async_client
    finally:
        try:
            await async_client.aclose()
        except Exception:
            pass
```

**Why**: Ensures resources are properly released before event loop closes.

---

## Problem #3: No Real Data in Tests

### Current Issue
- Tests mock the entire decision engine
- Real data from database is never used
- Can't validate real data integration

### Root Cause
Tests use `patch("app.api.routes.decision_engine.get_decision_engine")` to mock the entire engine.

### Solution
Create test database fixtures with real data.

**File**: `backend/tests/conftest.py`

Add fixture:
```python
@pytest_asyncio.fixture
async def test_account_with_data(test_wallet):
    """Create test account with market data."""
    # Create account for test wallet
    # Create market data for BTCUSDT (100 candles)
    # Return account with real data
```

**Why**: Enables tests to use real data from database.

---

## Problem #4: Tests Don't Verify Real Data Usage

### Current Issue
- Tests don't check if real data is actually being used
- Can't distinguish between mock and real data
- No validation of data flow

### Root Cause
Tests only check response status code, not response content.

### Solution
Add assertions to verify real data usage.

**File**: `backend/tests/e2e/test_decision_generate_api_e2e.py`

Add assertions:
```python
# Verify real data was used
assert data["context"]["market_data"]["current_price"] > 0
assert data["context"]["market_data"]["volume_24h"] > 0
assert data["context"]["account_state"]["balance_usd"] == 10000.0
assert len(data["context"]["market_data"]["technical_indicators"]) > 0
```

**Why**: Validates that real data is actually being used in decisions.

---

## Problem #5: Tests Mock Decision Engine

### Current Issue
- Tests mock the entire decision engine
- Real context builder never runs
- Real decision validator never runs
- Only tests HTTP API structure, not business logic

### Root Cause
Tests use mocks to avoid external dependencies (LLM API costs).

### Solution
Remove decision engine mocks, keep only LLM mocks.

**File**: `backend/tests/e2e/test_decision_generate_api_e2e.py`

Change from:
```python
with patch("app.api.routes.decision_engine.get_decision_engine") as mock_get_engine:
    mock_engine = AsyncMock()
    mock_engine.make_trading_decision.return_value = mock_decision_result
    mock_get_engine.return_value = mock_engine
```

To:
```python
with patch("app.services.llm.llm_service.LLMService.generate_trading_decision") as mock_llm:
    mock_llm.return_value = mock_decision
    # Let real decision engine run
```

**Why**: Tests real data flow while avoiding LLM API costs.

---

## Implementation Checklist

### Phase 1: Fix Critical Issues (35 min)
- [ ] Add authentication dependency to endpoint (5 min)
- [ ] Fix async event loop in fixtures (30 min)

### Phase 2: Enable Real Data (1 hour)
- [ ] Create test database fixtures (1 hour)

### Phase 3: Integrate Real Data (1-2 hours)
- [ ] Update E2E tests to use real data (1-2 hours)

### Phase 4: Verify (30 min)
- [ ] Add real data verification assertions (30 min)
- [ ] Run full test suite
- [ ] Verify all 17 tests pass

---

## Expected Results After Implementation

### Test Results
- ✅ 17/17 tests PASS (currently 3 PASS, 2 FAIL, 7 ERROR)
- ✅ 0 authentication failures
- ✅ 0 async event loop errors

### Data Flow
- ✅ Real market data from database
- ✅ Real account data from database
- ✅ Real technical indicators calculated
- ✅ Real decision validation

### Code Quality
- ✅ No mocks of decision engine
- ✅ Only LLM service mocked (external API)
- ✅ Full integration testing
- ✅ Real data validation

---

## Key Files

1. **backend/src/app/api/routes/decision_engine.py**
   - Add authentication dependency
   - 1 line change

2. **backend/tests/conftest.py**
   - Fix async cleanup
   - Add test data fixtures
   - ~50 lines added

3. **backend/tests/e2e/test_decision_generate_api_e2e.py**
   - Remove decision engine mocks
   - Add real data assertions
   - ~100 lines modified

---

## Success Criteria

✅ All 17 E2E tests pass
✅ Authentication properly enforced
✅ No async event loop errors
✅ Real data from database used
✅ Real data verified in assertions
✅ Decision engine not mocked
✅ Only LLM service mocked

---

## Next Steps

1. Review this document
2. Implement changes in order (Phase 1 → Phase 2 → Phase 3 → Phase 4)
3. Run tests after each phase
4. Verify success criteria met

See `REAL_DATA_E2E_ACTION_PLAN.md` for detailed implementation steps.

