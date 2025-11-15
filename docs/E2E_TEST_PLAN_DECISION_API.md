# E2E Test Plan: Decision/Generate API

## Overview

This document outlines the comprehensive end-to-end (E2E) test plan for the `/api/v1/decisions/generate` HTTP API endpoint. The endpoint is responsible for generating AI-powered trading decisions using the LLM Decision Engine.

## Test Objectives

1. **Validate API functionality** - Ensure the endpoint works correctly with real HTTP requests
2. **Test authentication flow** - Verify wallet-based authentication works end-to-end
3. **Validate request/response contracts** - Ensure API adheres to OpenAPI specification
4. **Test error handling** - Verify proper error responses for various failure scenarios
5. **Validate integration** - Test integration with decision engine, database, and external services
6. **Performance testing** - Verify response times and rate limiting behavior

## API Endpoint Details

**Endpoint:** `POST /api/v1/decisions/generate`

**Authentication:** Required (JWT Bearer token via wallet signature)

**Request Body:**
```json
{
  "symbol": "BTCUSDT",
  "account_id": 1,
  "strategy_override": "aggressive",  // optional
  "force_refresh": false,             // optional
  "ab_test_name": "test_variant_a"    // optional
}
```

**Success Response (200):**
```json
{
  "decision": {
    "asset": "BTCUSDT",
    "action": "buy|sell|hold",
    "allocation_usd": 1000.0,
    "confidence": 0.85,
    "risk_level": "medium",
    "rationale": "...",
    "exit_plan": {...}
  },
  "context": {...},
  "validation_passed": true,
  "validation_errors": [],
  "processing_time_ms": 250.0,
  "model_used": "x-ai/grok-4",
  "api_cost": 0.05
}
```

## Test Scenarios

### 1. Authentication Tests

#### 1.1 Successful Authentication Flow
- **Objective:** Verify complete wallet-based authentication works
- **Steps:**
  1. Request challenge for wallet address
  2. Sign challenge with private key
  3. Login with signature to get JWT token
  4. Use JWT token to call decision/generate endpoint
- **Expected:** 200 OK with valid decision result
- **Priority:** P0 (Critical)

#### 1.2 Missing Authentication Token
- **Objective:** Verify endpoint rejects unauthenticated requests
- **Steps:** Call endpoint without Authorization header
- **Expected:** 401 Unauthorized
- **Priority:** P0 (Critical)

#### 1.3 Invalid JWT Token
- **Objective:** Verify endpoint rejects invalid tokens
- **Steps:** Call endpoint with malformed/expired JWT
- **Expected:** 401 Unauthorized or 403 Forbidden
- **Priority:** P0 (Critical)

#### 1.4 Token Expiration
- **Objective:** Verify expired tokens are rejected
- **Steps:** Use expired JWT token
- **Expected:** 401 Unauthorized with appropriate error message
- **Priority:** P1 (High)

### 2. Request Validation Tests

#### 2.1 Valid Request - Minimal Fields
- **Objective:** Test with only required fields
- **Request:** `{"symbol": "BTCUSDT", "account_id": 1}`
- **Expected:** 200 OK with decision result
- **Priority:** P0 (Critical)

#### 2.2 Valid Request - All Fields
- **Objective:** Test with all optional fields
- **Request:** Include strategy_override, force_refresh, ab_test_name
- **Expected:** 200 OK with decision result
- **Priority:** P0 (Critical)

#### 2.3 Invalid Symbol Format
- **Objective:** Test with invalid/empty symbol
- **Request:** `{"symbol": "", "account_id": 1}`
- **Expected:** 400 Bad Request or 422 Unprocessable Entity
- **Priority:** P1 (High)

#### 2.4 Invalid Account ID
- **Objective:** Test with invalid account ID
- **Request:** `{"symbol": "BTCUSDT", "account_id": -1}`
- **Expected:** 400 Bad Request
- **Priority:** P1 (High)

#### 2.5 Missing Required Fields
- **Objective:** Test with missing required fields
- **Request:** `{"symbol": "BTCUSDT"}` (missing account_id)
- **Expected:** 422 Unprocessable Entity
- **Priority:** P1 (High)

#### 2.6 Invalid Data Types
- **Objective:** Test with wrong data types
- **Request:** `{"symbol": 123, "account_id": "abc"}`
- **Expected:** 422 Unprocessable Entity
- **Priority:** P1 (High)

### 3. Success Scenarios

#### 3.1 Generate Decision for BTC
- **Objective:** Test decision generation for Bitcoin
- **Request:** `{"symbol": "BTCUSDT", "account_id": 1}`
- **Expected:** Valid decision with BTC-specific analysis
- **Priority:** P0 (Critical)

#### 3.2 Generate Decision for ETH
- **Objective:** Test decision generation for Ethereum
- **Request:** `{"symbol": "ETHUSDT", "account_id": 1}`
- **Expected:** Valid decision with ETH-specific analysis
- **Priority:** P0 (Critical)

#### 3.3 Generate Decision for SOL
- **Objective:** Test decision generation for Solana
- **Request:** `{"symbol": "SOLUSDT", "account_id": 1}`
- **Expected:** Valid decision with SOL-specific analysis
- **Priority:** P0 (Critical)

#### 3.4 Strategy Override
- **Objective:** Test custom strategy override
- **Request:** `{"symbol": "BTCUSDT", "account_id": 1, "strategy_override": "aggressive"}`
- **Expected:** Decision reflects aggressive strategy parameters
- **Priority:** P1 (High)

#### 3.5 Force Refresh
- **Objective:** Test cache bypass with force_refresh
- **Request:** `{"symbol": "BTCUSDT", "account_id": 1, "force_refresh": true}`
- **Expected:** Fresh decision generated, not from cache
- **Priority:** P1 (High)

#### 3.6 A/B Testing
- **Objective:** Test A/B test variant tracking
- **Request:** `{"symbol": "BTCUSDT", "account_id": 1, "ab_test_name": "variant_a"}`
- **Expected:** Decision includes A/B test metadata
- **Priority:** P2 (Medium)

### 4. Error Handling Tests

#### 4.1 Rate Limit Exceeded
- **Objective:** Test rate limiting (60 req/min per account)
- **Steps:** Make >60 requests in 1 minute
- **Expected:** 429 Too Many Requests
- **Priority:** P0 (Critical)

#### 4.2 Decision Engine Error
- **Objective:** Test handling of decision engine failures
- **Steps:** Trigger decision engine error (mock or real)
- **Expected:** 400 Bad Request with error details
- **Priority:** P1 (High)

#### 4.3 Database Connection Error
- **Objective:** Test handling of database failures
- **Steps:** Simulate database unavailability
- **Expected:** 500 Internal Server Error
- **Priority:** P1 (High)

#### 4.4 LLM Service Timeout
- **Objective:** Test handling of LLM API timeouts
- **Steps:** Simulate LLM service timeout
- **Expected:** 500 Internal Server Error or 504 Gateway Timeout
- **Priority:** P1 (High)

#### 4.5 Insufficient Market Data
- **Objective:** Test handling when market data is unavailable
- **Steps:** Request decision for symbol with no market data
- **Expected:** 400 Bad Request with appropriate error message
- **Priority:** P1 (High)

#### 4.6 Account Not Found
- **Objective:** Test with non-existent account ID
- **Request:** `{"symbol": "BTCUSDT", "account_id": 999999}`
- **Expected:** 404 Not Found or 400 Bad Request
- **Priority:** P1 (High)

### 5. Response Validation Tests

#### 5.1 Response Structure Validation
- **Objective:** Verify response has all required fields
- **Validation:**
  - decision object with all required fields
  - context object with market_data, account_state, risk_metrics
  - validation_passed boolean
  - processing_time_ms number
  - model_used string
- **Priority:** P0 (Critical)

#### 5.2 Decision Object Validation
- **Objective:** Verify decision object structure
- **Validation:**
  - asset matches request symbol
  - action is one of: buy, sell, hold
  - allocation_usd is positive number
  - confidence is between 0 and 1
  - risk_level is valid enum
  - rationale is non-empty string
  - exit_plan has stop_loss and take_profit
- **Priority:** P0 (Critical)

#### 5.3 Context Object Validation
- **Objective:** Verify context contains complete data
- **Validation:**
  - market_data has current_price, indicators, etc.
  - account_state has balance, positions, etc.
  - risk_metrics has VaR, drawdown, etc.
- **Priority:** P1 (High)

#### 5.4 Validation Errors Format
- **Objective:** Verify validation_errors array format
- **Validation:** Each error has rule, severity, message
- **Priority:** P1 (High)

### 6. Performance Tests

#### 6.1 Response Time - Cached
- **Objective:** Verify cached responses are fast
- **Expected:** < 100ms for cached decisions
- **Priority:** P1 (High)

#### 6.2 Response Time - Fresh
- **Objective:** Verify fresh decision generation time
- **Expected:** < 5000ms for new decisions
- **Priority:** P1 (High)

#### 6.3 Concurrent Requests
- **Objective:** Test handling of concurrent requests
- **Steps:** Send 10 concurrent requests
- **Expected:** All requests succeed without errors
- **Priority:** P2 (Medium)

### 7. Integration Tests

#### 7.1 Database Integration
- **Objective:** Verify decision is saved to database
- **Steps:** Generate decision, query database
- **Expected:** Decision record exists in decisions table
- **Priority:** P1 (High)

#### 7.2 Market Data Integration
- **Objective:** Verify market data is fetched correctly
- **Steps:** Generate decision, verify market data in context
- **Expected:** Context contains recent market data
- **Priority:** P1 (High)

#### 7.3 Account State Integration
- **Objective:** Verify account state is loaded correctly
- **Steps:** Generate decision, verify account data in context
- **Expected:** Context contains current account state
- **Priority:** P1 (High)

## Test Data Requirements

### Test Accounts
- Account ID 1: Standard test account with balance
- Account ID 2: Account with existing positions
- Account ID 999999: Non-existent account

### Test Symbols
- BTCUSDT: Primary test symbol with full market data
- ETHUSDT: Secondary test symbol
- SOLUSDT: Tertiary test symbol
- INVALIDUSDT: Invalid symbol for error testing

### Test Wallets
- Dev Wallet 1: For authentication testing
- Dev Wallet 2: For multi-user testing

## Test Environment Setup

### Prerequisites
1. Backend server running on localhost:3000
2. PostgreSQL database with test data
3. Market data synced for test symbols
4. Test wallet with private key for authentication

### Environment Variables
```bash
API_BASE=http://localhost:3000
ADDR=0xTestWalletAddress
PRIVATE_KEY=0xTestPrivateKey
```

## Test Execution

### Manual Testing
```bash
# 1. Authenticate
cd backend
export ADDR=0xYourTestAddress
export PRIVATE_KEY=0xYourTestPrivateKey
TOKEN=$(uv run python scripts/sign.py | head -1)

# 2. Test endpoint
curl -X POST "$API_BASE/api/v1/decisions/generate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSDT", "account_id": 1}'
```

### Automated Testing
```bash
cd backend
uv run pytest tests/e2e/test_decision_generate_api_e2e.py -v
```

## Success Criteria

- All P0 tests pass: 100%
- All P1 tests pass: ≥95%
- All P2 tests pass: ≥90%
- Response times meet SLA
- No security vulnerabilities
- API documentation matches implementation

## Test Coverage Goals

- **Code Coverage:** ≥80% for decision_engine.py route
- **Scenario Coverage:** All documented scenarios tested
- **Error Coverage:** All error codes tested
- **Integration Coverage:** All external dependencies tested

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM API unavailable | High | Mock LLM responses for critical tests |
| Database connection issues | High | Use test database with retry logic |
| Rate limiting affects tests | Medium | Use separate test account with higher limits |
| Test data inconsistency | Medium | Reset test data before each test run |

## Test Maintenance

- Review and update test plan quarterly
- Add new tests for bug fixes
- Update tests when API changes
- Monitor test execution time
- Archive obsolete tests

