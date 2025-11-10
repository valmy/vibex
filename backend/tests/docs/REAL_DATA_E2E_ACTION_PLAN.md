# Action Plan: E2E Tests for Decisions/Generate with Real Data

## Overview
To make E2E tests for `/api/v1/decisions/generate` use real data successfully, we need to:
1. Fix authentication enforcement
2. Fix async event loop issues in tests
3. Integrate real data from database
4. Create test database fixtures
5. Update tests to verify real data usage

---

## Step 1: Fix Authentication Enforcement (CRITICAL - 5 min)

### Problem
The endpoint doesn't enforce JWT authentication. Tests expect 401 but get 200 OK.

### Solution
Add `get_current_user` dependency to the endpoint.

**File**: `backend/src/app/api/routes/decision_engine.py`

**Changes**:
```python
# Line 12: Add Depends import
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Depends

# Line 15: Add User import
from ...models.account import User
from ...core.security import get_current_user

# Line 79-80: Update endpoint signature
@router.post("/generate", response_model=DecisionResult)
async def generate_decision(
    request: DecisionRequest,
    current_user: User = Depends(get_current_user)  # ADD THIS LINE
):
    """
    Generate a trading decision for a specific symbol and account.
    ...
    """
    # Rest of implementation stays the same
```

**Why**: This ensures only authenticated users can call the endpoint.

---

## Step 2: Fix Async Event Loop Issues (HIGH - 30 min)

### Problem
Database connections fail during cleanup on Windows. The `authenticated_client` fixture fails.

### Solution
Implement proper async context management in test fixtures.

**File**: `backend/tests/conftest.py`

**Changes**:
1. Add proper cleanup for database connections
2. Use function-scoped fixtures instead of class-scoped
3. Properly close async clients

```python
@pytest_asyncio.fixture
async def authenticated_client(async_client, test_wallet):
    """Create authenticated HTTP client with JWT token."""
    try:
        # Step 1: Request challenge
        challenge_response = await async_client.post(
            f"/api/v1/auth/challenge?address={test_wallet['address']}"
        )
        assert challenge_response.status_code == 200
        challenge = challenge_response.json()["challenge"]

        # Step 2: Sign challenge
        message = encode_defunct(text=challenge)
        signed_message = Account.sign_message(message, private_key=test_wallet["private_key"])
        signature = signed_message.signature.hex()
        if not signature.startswith("0x"):
            signature = f"0x{signature}"

        # Step 3: Login to get JWT
        login_response = await async_client.post(
            f"/api/v1/auth/login?challenge={challenge}&signature={signature}&address={test_wallet['address']}"
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        # Step 4: Add token to client headers
        async_client.headers["Authorization"] = f"Bearer {token}"
        yield async_client
    finally:
        # Proper cleanup
        try:
            await async_client.aclose()
        except Exception:
            pass
```

---

## Step 3: Create Test Database Fixtures (HIGH - 1 hour)

### Problem
Tests use random wallet addresses that don't own accounts. No real data in database.

### Solution
Create fixtures that populate test data.

**File**: `backend/tests/conftest.py`

**Add**:
```python
@pytest_asyncio.fixture
async def test_account_with_data(test_wallet):
    """Create a test account with market data."""
    from app.db.session import get_db
    from app.models.account import Account
    from app.models.market_data import MarketData
    from datetime import datetime, timezone, timedelta
    
    db = await get_db()
    try:
        # Create account for test wallet
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
        await db.flush()
        
        # Create market data for BTCUSDT
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

---

## Step 4: Update E2E Tests (HIGH - 1-2 hours)

### Problem
Tests mock the entire decision engine, so real data isn't used.

### Solution
Remove mocks and let real decision engine run with only LLM mocked.

**File**: `backend/tests/e2e/test_decision_generate_api_e2e.py`

**Changes**:
1. Use `test_account_with_data` fixture
2. Remove decision engine mocks
3. Mock only LLM service
4. Add real data verification assertions

```python
@pytest.mark.asyncio
async def test_decision_uses_real_market_data(
    authenticated_client, 
    test_account_with_data
):
    """Test that decision generation uses real market data."""
    with patch("app.services.llm.llm_service.LLMService.generate_trading_decision") as mock_llm:
        # Mock only the LLM to avoid API costs
        mock_decision = TradingDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=1000.0,
            tp_price=52000.0,
            sl_price=48000.0,
            exit_plan="Take profit at resistance",
            rationale="Strong bullish momentum",
            confidence=75.0,
            risk_level="medium",
        )
        mock_llm.return_value = mock_decision
        
        # Call endpoint with real account
        response = await authenticated_client.post(
            "/api/v1/decisions/generate",
            json={
                "symbol": "BTCUSDT",
                "account_id": test_account_with_data.id
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify real data was used
        assert data["context"]["market_data"]["current_price"] > 0
        assert data["context"]["market_data"]["volume_24h"] > 0
        assert data["context"]["account_state"]["balance_usd"] == 10000.0
        assert len(data["context"]["market_data"]["technical_indicators"]) > 0
```

---

## Step 5: Verify Real Data Flow (MEDIUM - 30 min)

### Add Assertions
Verify that:
- Market data comes from database
- Account data comes from database
- Technical indicators are calculated
- Decision uses real context

---

## Implementation Order

1. **First**: Fix authentication (5 min) - Unblocks security tests
2. **Second**: Fix async event loop (30 min) - Unblocks 7 tests
3. **Third**: Create test fixtures (1 hour) - Enables real data
4. **Fourth**: Update tests (1-2 hours) - Integrate real data
5. **Fifth**: Verify flow (30 min) - Validate everything works

**Total Time**: ~3-4 hours

---

## Success Criteria

✅ All 17 E2E tests pass
✅ Tests use real data from database
✅ Authentication properly enforced (401 for missing token)
✅ Decision generation includes real market data
✅ Account context uses real account data
✅ Technical indicators calculated from real OHLCV data
✅ No mocks of decision engine (only LLM mocked)

---

## Files to Modify

1. `backend/src/app/api/routes/decision_engine.py` - Add authentication
2. `backend/tests/conftest.py` - Fix fixtures, add test data
3. `backend/tests/e2e/test_decision_generate_api_e2e.py` - Update tests

---

## Key Insights

**Current Flow**:
```
Test → Mock Decision Engine → Mock LLM → Return Mock Decision
```

**Desired Flow**:
```
Test → Real Decision Engine → Real Context Builder → Real Database
                           → Mock LLM (avoid API costs)
                           → Real Decision Validator
                           → Return Real Decision with Real Data
```

**Why This Matters**:
- Tests real data integration
- Validates context builder works
- Validates decision validator works
- Only mocks external LLM API (cost/time)
- Catches real data issues early

