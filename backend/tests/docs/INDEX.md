# E2E Test Documentation Index

This directory contains comprehensive documentation for the Decision/Generate API E2E tests.

## Documents

### 1. E2E_TEST_REAL_DATA_REPORT.md
**Purpose:** Test execution report and status summary

**Contents:**
- Test status overview (passed, failed, errors, skipped)
- Detailed test results for each test case
- Issues identified and their impact
- Recommendations for fixes
- Test coverage analysis

**When to Read:** After running E2E tests to understand results and identify issues

---

### 2. REAL_DATA_E2E_ACTION_PLAN.md
**Purpose:** Comprehensive action plan for implementing E2E tests with real data

**Contents:**
- Problem statement and objectives
- Detailed implementation steps
- Code examples and patterns
- Database setup requirements
- Test data creation procedures
- Troubleshooting guide

**When to Read:** When implementing or debugging E2E tests with real data

---

### 3. WHAT_NEEDS_TO_BE_DONE.md
**Purpose:** Outstanding tasks and improvements for E2E testing

**Contents:**
- List of pending tasks
- Known issues and bugs
- Improvement opportunities
- Priority levels for each task
- Estimated effort for completion

**When to Read:** When planning next steps or prioritizing work

---

### 4. QUICK_REFERENCE.md
**Purpose:** Quick reference guide for common E2E testing tasks

**Contents:**
- Common commands and shortcuts
- Frequently used fixtures and utilities
- Quick troubleshooting tips
- Common error solutions
- Testing best practices

**When to Read:** During development and testing for quick lookup

---

## Quick Navigation

### For Test Execution
1. Start with **QUICK_REFERENCE.md** for commands
2. Check **E2E_TEST_REAL_DATA_REPORT.md** for current status
3. Refer to **REAL_DATA_E2E_ACTION_PLAN.md** if issues arise

### For Implementation
1. Read **REAL_DATA_E2E_ACTION_PLAN.md** for detailed steps
2. Check **WHAT_NEEDS_TO_BE_DONE.md** for requirements
3. Use **QUICK_REFERENCE.md** for common patterns

### For Troubleshooting
1. Check **QUICK_REFERENCE.md** for quick fixes
2. Review **REAL_DATA_E2E_ACTION_PLAN.md** troubleshooting section
3. Check **E2E_TEST_REAL_DATA_REPORT.md** for known issues

---

## Key Test Files

### Main E2E Test Files
- `tests/e2e/test_decision_generate_api_e2e_http.py` - HTTP E2E tests (9 tests)
- `tests/e2e/test_decision_generate_api_e2e.py` - ASGI E2E tests with authentication
- `tests/e2e/test_decision_api_e2e.py` - Decision API endpoint tests

### Supporting Test Files
- `tests/e2e/test_llm_decision_engine_e2e.py` - Full decision workflow
- `tests/e2e/test_technical_analysis_e2e.py` - Technical indicators
- `tests/e2e/test_context_builder_e2e.py` - Context building
- `tests/e2e/test_full_pipeline_e2e.py` - Complete pipeline

---

## Test Data Scripts

Located in `tests/scripts/`:
- `create_test_data.py` - Create test accounts, users, and market data
- `delete_test_data.py` - Clean up test data
- `check_db.py` - Verify database contents
- `check_users.py` - Check user data

---

## Running E2E Tests

### Prerequisites
```bash
# Start backend services
cd backend && podman-compose up -d

# Create test data
cd backend && uv run python tests/scripts/create_test_data.py
```

### Execute Tests
```bash
# Run all E2E tests
cd backend && uv run pytest tests/e2e/ -v

# Run specific test file
cd backend && uv run pytest tests/e2e/test_decision_generate_api_e2e_http.py -v

# Run with coverage
cd backend && uv run pytest tests/e2e/ --cov=src/app
```

---

## Test Coverage

### Current Status
- **HTTP E2E Tests:** 9 tests (all passing ✅)
- **ASGI E2E Tests:** Multiple tests
- **Integration Tests:** Full pipeline coverage
- **Code Coverage:** ≥80% for decision_engine.py

### Test Categories
1. **Authentication Tests** - Wallet-based auth flow
2. **Decision Generation Tests** - Real data decision generation
3. **Response Validation Tests** - Response structure and content
4. **Error Handling Tests** - Error scenarios and edge cases
5. **Performance Tests** - Concurrent requests and load
6. **Integration Tests** - Full pipeline integration

---

## Common Issues and Solutions

### Database Connection Issues
- See REAL_DATA_E2E_ACTION_PLAN.md → Troubleshooting section
- Check database is running: `podman ps`
- Verify test data exists: `uv run python tests/scripts/check_db.py`

### Authentication Failures
- Ensure test wallet is created in database
- Check JWT token generation
- Verify middleware configuration

### Real Data Not Found
- Run `create_test_data.py` to populate database
- Verify market data interval is "5m"
- Check account exists with ID 1

### Event Loop Issues
- Tests use NullPool for database connections
- Ensure proper async/await in fixtures
- Check conftest.py for fixture setup

---

## Next Steps

1. **Review Current Status:** Read E2E_TEST_REAL_DATA_REPORT.md
2. **Understand Implementation:** Read REAL_DATA_E2E_ACTION_PLAN.md
3. **Check Outstanding Work:** Read WHAT_NEEDS_TO_BE_DONE.md
4. **Quick Reference:** Use QUICK_REFERENCE.md during development

---

## Support

For questions or issues:
1. Check QUICK_REFERENCE.md for common solutions
2. Review REAL_DATA_E2E_ACTION_PLAN.md troubleshooting
3. Check test file comments for specific test documentation
4. Review conftest.py for fixture documentation

