# Tests Directory Structure

This directory contains all test-related files, documentation, scripts, and data for the trading agent backend.

## Directory Organization

### `/e2e` - End-to-End Tests
Complete workflow tests that validate the entire LLM Decision Engine pipeline with real data.

**Key Test Files:**
- `test_decision_generate_api_e2e_http.py` - HTTP E2E tests for `/api/v1/decisions/generate` endpoint
- `test_decision_generate_api_e2e.py` - E2E tests with real authentication
- `test_decision_api_e2e.py` - Decision Engine HTTP API endpoint tests
- `test_llm_decision_engine_e2e.py` - Complete decision workflow with real market data
- `test_technical_analysis_e2e.py` - Technical indicator integration tests
- `test_context_builder_e2e.py` - Trading context building tests
- `test_db_market_data_e2e.py` - Database market data integration tests
- `test_full_pipeline_e2e.py` - Full pipeline integration tests
- `test_decision_accuracy_regression.py` - Decision accuracy regression tests

**Running E2E Tests:**
```bash
# Run all E2E tests
cd backend && uv run pytest tests/e2e/ -v

# Run specific test file
cd backend && uv run pytest tests/e2e/test_decision_generate_api_e2e_http.py -v

# Run with coverage
cd backend && uv run pytest tests/e2e/ --cov=src/app
```

### `/unit` - Unit Tests
Isolated tests for individual components and functions.

**Key Test Files:**
- `test_decision_api_with_real_data.py` - Decision API with real data
- `test_context_builder.py` - Context builder unit tests
- `test_llm_service.py` - LLM service unit tests
- `test_technical_analysis.py` - Technical analysis unit tests
- `test_decision_validator.py` - Decision validator unit tests
- `test_config_*.py` - Configuration management tests

### `/integration` - Integration Tests
Tests for component interactions and external service integrations.

**Key Test Files:**
- `test_llm_decision_engine_integration.py` - LLM engine integration
- `test_technical_analysis_integration.py` - Technical analysis integration
- `test_config_integration.py` - Configuration integration

### `/performance` - Performance Tests
Performance and load testing for the decision engine.

**Key Test Files:**
- `test_llm_decision_performance.py` - Decision engine performance tests

### `/docs` - Test Documentation
Comprehensive documentation for E2E tests and test planning.

**Key Documents:**
- `E2E_TEST_REAL_DATA_REPORT.md` - Test results and status report
- `REAL_DATA_E2E_ACTION_PLAN.md` - Action plan for E2E testing with real data
- `WHAT_NEEDS_TO_BE_DONE.md` - Outstanding tasks and improvements
- `QUICK_REFERENCE.md` - Quick reference guide for testing

### `/scripts` - Test Utility Scripts
Helper scripts for test data management and debugging.

**Key Scripts:**
- `create_test_data.py` - Create test data in database (accounts, market data, users)
- `delete_test_data.py` - Clean up test data from database
- `add_funding_rate.py` - Add funding rate data to market data
- `check_db.py` - Check database status and contents
- `check_users.py` - Check user data in database
- `test_scheduler.py` - Test market data scheduler

**Running Scripts:**
```bash
# Create test data
cd backend && uv run python tests/scripts/create_test_data.py

# Delete test data
cd backend && uv run python tests/scripts/delete_test_data.py

# Check database
cd backend && uv run python tests/scripts/check_db.py

# Check users
cd backend && uv run python tests/scripts/check_users.py
```

### `/data` - Test Output and Results
Test execution outputs and result files.

**Files:**
- `e2e_test_output.txt` - E2E test execution output
- `test_output*.txt` - Various test run outputs

## Test Configuration

### `conftest.py`
Pytest configuration and fixtures for all tests.

**Key Fixtures:**
- `db_session` - Database session for testing
- `async_client` - Async HTTP client for ASGI testing
- `authenticated_http_client` - HTTP client with authentication
- `test_wallet` - Test wallet for authentication
- `test_user_in_db` - Test user in database

### `__init__.py`
Package initialization file.

## Running Tests

### All Tests
```bash
cd backend && uv run pytest tests/ -v
```

### By Category
```bash
# Unit tests only
cd backend && uv run pytest tests/unit/ -v

# Integration tests only
cd backend && uv run pytest tests/integration/ -v

# E2E tests only (requires running backend)
cd backend && uv run pytest tests/e2e/ -v

# Performance tests
cd backend && uv run pytest tests/performance/ -v
```

### With Coverage
```bash
cd backend && uv run pytest tests/ --cov=src/app --cov-report=html
```

### Specific Test
```bash
cd backend && uv run pytest tests/e2e/test_decision_generate_api_e2e_http.py::TestDecisionGenerateAPIHTTP::test_generate_decision_btc_real_data -v
```

## E2E Test Prerequisites

For E2E tests to run successfully:

1. **Backend Services Running:**
   ```bash
   cd backend && podman-compose up -d
   ```

2. **Test Data Created:**
   ```bash
   cd backend && uv run python tests/scripts/create_test_data.py
   ```

3. **Database Healthy:**
   - PostgreSQL running on `localhost:5432`
   - Redis running on `localhost:6379`
   - Backend API running on `127.0.0.1:3000`

## Test Coverage Goals

- **Code Coverage:** ≥80% for decision_engine.py
- **Scenario Coverage:** All documented scenarios tested
- **Error Coverage:** All error codes tested
- **Integration Coverage:** All external dependencies tested

## Troubleshooting

### Database Connection Issues
```bash
# Check database status
cd backend && uv run python tests/scripts/check_db.py

# Restart services
cd backend && podman-compose down && podman-compose up -d
```

### Test Data Issues
```bash
# Delete and recreate test data
cd backend && uv run python tests/scripts/delete_test_data.py
cd backend && uv run python tests/scripts/create_test_data.py
```

### Event Loop Issues
- Tests use `NullPool` for database connections to avoid event loop issues
- Ensure proper async/await usage in test fixtures

## Related Documentation

- See `/docs` folder for detailed test plans and reports
- See individual test files for specific test documentation
- See `conftest.py` for fixture documentation

