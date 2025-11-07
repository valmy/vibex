# Quick Reference: E2E Tests Real Data Integration

## TL;DR - What Needs to Be Done

**5 changes needed to make E2E tests use real data successfully:**

### 1️⃣ Add Authentication (5 min)
**File**: `backend/src/app/api/routes/decision_engine.py` Line 79-80

```python
# Add to imports
from fastapi import Depends
from ...models.account import User
from ...core.security import get_current_user

# Update endpoint
@router.post("/generate", response_model=DecisionResult)
async def generate_decision(
    request: DecisionRequest,
    current_user: User = Depends(get_current_user)  # ADD THIS
):
```

### 2️⃣ Fix Async Event Loop (30 min)
**File**: `backend/tests/conftest.py`

```python
@pytest_asyncio.fixture
async def authenticated_client(async_client, test_wallet):
    try:
        # ... existing code ...
        yield async_client
    finally:
        try:
            await async_client.aclose()
        except Exception:
            pass
```

### 3️⃣ Create Test Fixtures (1 hour)
**File**: `backend/tests/conftest.py`

```python
@pytest_asyncio.fixture
async def test_account_with_data(test_wallet):
    """Create test account with market data."""
    db = await get_db()
    try:
        # Create account
        account = Account(
            user_address=test_wallet['address'],
            name="Test Account",
            balance_usd=10000.0,
            available_balance=8000.0,
            total_position_value_usd=2000.0,
            leverage=1.0,
            margin_ratio=0.5,
            max_position_size_usd=5000.0,
        )
        db.add(account)
        
        # Create market data (100 candles)
        now = datetime.now(timezone.utc)
        for i in range(100):
            timestamp = now - timedelta(minutes=5*i)
            market_data = MarketData(
                symbol="BTCUSDT",
                timestamp=timestamp,
                open=50000.0 + i*10,
                high=50500.0 + i*10,
                low=49500.0 + i*10,
                close=50250.0 + i*10,
                volume=1000.0,
            )
            db.add(market_data)
        
        await db.commit()
        await db.refresh(account)
        return account
    finally:
        await db.close()
```

### 4️⃣ Update E2E Tests (1-2 hours)
**File**: `backend/tests/e2e/test_decision_generate_api_e2e.py`

Remove mocks of decision engine, keep only LLM mocks:

```python
# REMOVE THIS
with patch("app.api.routes.decision_engine.get_decision_engine") as mock_get_engine:
    mock_engine = AsyncMock()
    mock_engine.make_trading_decision.return_value = mock_decision_result
    mock_get_engine.return_value = mock_engine

# USE THIS INSTEAD
with patch("app.services.llm.llm_service.LLMService.generate_trading_decision") as mock_llm:
    mock_llm.return_value = mock_decision
    # Let real decision engine run
```

### 5️⃣ Add Real Data Assertions (30 min)
**File**: `backend/tests/e2e/test_decision_generate_api_e2e.py`

```python
# Verify real data was used
assert data["context"]["market_data"]["current_price"] > 0
assert data["context"]["market_data"]["volume_24h"] > 0
assert data["context"]["account_state"]["balance_usd"] == 10000.0
assert len(data["context"]["market_data"]["technical_indicators"]) > 0
```

---

## Current Test Results

```
✅ PASSED:  3 tests
❌ FAILED:  2 tests (authentication not enforced)
⚠️  ERROR:   7 tests (async event loop issues)
⏭️  SKIPPED: 5 tests
```

## Expected Results After Implementation

```
✅ PASSED:  17/17 tests
❌ FAILED:  0 tests
⚠️  ERROR:   0 tests
⏭️  SKIPPED: 0 tests
```

---

## Why These Changes Matter

| Change | Why | Impact |
|--------|-----|--------|
| Add Auth | Security - prevent unauthorized access | Fixes 2 FAILED tests |
| Fix Async | Unblock fixture setup | Fixes 7 ERROR tests |
| Test Fixtures | Enable real data | Enables real data flow |
| Update Tests | Use real data | Validates integration |
| Add Assertions | Verify real data | Ensures data is real |

---

## Data Flow Comparison

### Before ❌
```
Test → Mock Engine → Mock LLM → Mock Decision
```

### After ✅
```
Test → Real Engine → Real Context Builder → Real DB
                  → Mock LLM (avoid costs)
                  → Real Validator
                  → Real Decision with Real Data
```

---

## Files to Modify

1. `backend/src/app/api/routes/decision_engine.py` (1 line)
2. `backend/tests/conftest.py` (50+ lines)
3. `backend/tests/e2e/test_decision_generate_api_e2e.py` (100+ lines)

---

## Implementation Time

| Phase | Task | Time |
|-------|------|------|
| 1 | Add authentication | 5 min |
| 1 | Fix async loop | 30 min |
| 2 | Create fixtures | 1 hour |
| 3 | Update tests | 1-2 hours |
| 4 | Add assertions | 30 min |
| **Total** | | **3-4 hours** |

---

## Success Criteria

- [ ] All 17 E2E tests pass
- [ ] Authentication enforced (401 for missing token)
- [ ] No async event loop errors
- [ ] Real data from database used
- [ ] Real data verified in assertions
- [ ] Decision engine not mocked
- [ ] Only LLM service mocked

---

## Key Insights

1. **Authentication Issue**: Endpoint missing `get_current_user` dependency
2. **Async Issue**: Database cleanup not properly handled on Windows
3. **Data Issue**: Tests mock everything instead of using real data
4. **Validation Issue**: Tests don't verify real data is being used
5. **Integration Issue**: Real services (context builder, validator) never run

---

## Related Documents

- `WHAT_NEEDS_TO_BE_DONE.md` - Detailed explanation of each issue
- `REAL_DATA_E2E_ACTION_PLAN.md` - Step-by-step implementation guide
- `E2E_TEST_REAL_DATA_REPORT.md` - Complete test analysis

---

## Quick Start

1. Read `WHAT_NEEDS_TO_BE_DONE.md` for full context
2. Follow `REAL_DATA_E2E_ACTION_PLAN.md` for implementation
3. Use this document as quick reference while coding
4. Run tests after each phase to verify progress

