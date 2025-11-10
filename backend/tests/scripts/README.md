# Test Utility Scripts

This directory contains helper scripts for managing test data and debugging the trading agent backend.

## Scripts Overview

### 1. create_test_data.py
**Purpose:** Create test data in the database for E2E testing

**What it creates:**
- Test user with wallet address
- Test account with trading parameters
- Market data for BTCUSDT, ETHUSDT, SOLUSDT (100 candles each)
- 5-minute interval candles with realistic price data

**Usage:**
```bash
cd backend && uv run python tests/scripts/create_test_data.py
```

**Output:**
```
✓ Test user created
✓ Test account created
✓ BTCUSDT market data created (100 candles)
✓ ETHUSDT market data created (100 candles)
✓ SOLUSDT market data created (100 candles)
```

**Prerequisites:**
- PostgreSQL running on localhost:5432
- Database initialized with schema
- Connection credentials in environment or .env file

**Notes:**
- Creates data with naive datetimes (no timezone)
- Uses 5-minute intervals as expected by context builder
- Prices gradually increase to simulate market trends
- Safe to run multiple times (checks for existing data)

---

### 2. delete_test_data.py
**Purpose:** Clean up test data from the database

**What it deletes:**
- Test market data (BTCUSDT, ETHUSDT, SOLUSDT)
- Test account (ID: 1)
- Test user (specific wallet address)

**Usage:**
```bash
cd backend && uv run python tests/scripts/delete_test_data.py
```

**Output:**
```
✓ Test market data deleted
✓ Test account deleted
✓ Test user deleted
```

**Prerequisites:**
- PostgreSQL running on localhost:5432
- Test data exists in database

**Notes:**
- Only deletes specific test data
- Safe to run even if data doesn't exist
- Use before recreating test data

---

### 3. add_funding_rate.py
**Purpose:** Add funding rate data to market data records

**What it does:**
- Adds funding_rate column to market_data table if missing
- Populates funding_rate values for existing records
- Sets realistic funding rates (0.00001 to 0.0001)

**Usage:**
```bash
cd backend && uv run python tests/scripts/add_funding_rate.py
```

**Output:**
```
✓ Funding rate column added
✓ Funding rates populated
```

**Prerequisites:**
- PostgreSQL running on localhost:5432
- Market data exists in database

**Notes:**
- Idempotent (safe to run multiple times)
- Generates realistic funding rate values
- Required for complete market data

---

### 4. check_db.py
**Purpose:** Check database status and contents

**What it checks:**
- Database connection status
- Table existence and row counts
- Market data availability
- Account information
- User information

**Usage:**
```bash
cd backend && uv run python tests/scripts/check_db.py
```

**Output:**
```
Database Status:
✓ Connected to trading_db
✓ Schema: trading

Tables:
- users: 20 rows
- accounts: 1 row
- market_data: 300 rows
  - BTCUSDT: 100 candles
  - ETHUSDT: 100 candles
  - SOLUSDT: 100 candles

Accounts:
- ID: 1, Name: Test Account, Status: active

Market Data:
- Latest BTCUSDT: 50990.00 (5m interval)
- Latest ETHUSDT: 3495.00 (5m interval)
- Latest SOLUSDT: 150.00 (5m interval)
```

**Prerequisites:**
- PostgreSQL running on localhost:5432

**Notes:**
- Non-destructive (read-only)
- Useful for debugging test setup
- Shows data availability for E2E tests

---

### 5. check_users.py
**Purpose:** Check user data in the database

**What it shows:**
- Total user count
- User details (ID, address, admin status)
- Account associations
- User creation timestamps

**Usage:**
```bash
cd backend && uv run python tests/scripts/check_users.py
```

**Output:**
```
Total Users: 20

Users:
ID  Address                                    Admin  Created
1   0x1234567890abcdef...                      Yes    2025-11-07 09:50:05
2   0xabcdefghijklmnop...                      No     2025-11-07 09:50:05
...
```

**Prerequisites:**
- PostgreSQL running on localhost:5432

**Notes:**
- Non-destructive (read-only)
- Useful for verifying test user creation
- Shows admin status for each user

---

### 6. test_scheduler.py
**Purpose:** Test the market data scheduler

**What it does:**
- Verifies scheduler is running
- Checks scheduled tasks
- Tests market data collection
- Validates data storage

**Usage:**
```bash
cd backend && uv run python tests/scripts/test_scheduler.py
```

**Output:**
```
Scheduler Status:
✓ Scheduler running
✓ Tasks scheduled: 3
  - BTCUSDT (5m interval)
  - ETHUSDT (5m interval)
  - SOLUSDT (5m interval)

Latest Data:
- BTCUSDT: 2025-11-09 10:30:00
- ETHUSDT: 2025-11-09 10:30:00
- SOLUSDT: 2025-11-09 10:30:00
```

**Prerequisites:**
- Backend running: `podman-compose up -d`
- Market data scheduler active

**Notes:**
- Requires running backend
- Useful for verifying scheduler health
- Checks data freshness

---

## Typical Workflow

### Setup for E2E Testing
```bash
# 1. Start backend services
cd backend && podman-compose up -d

# 2. Create test data
cd backend && uv run python tests/scripts/create_test_data.py

# 3. Verify setup
cd backend && uv run python tests/scripts/check_db.py

# 4. Run E2E tests
cd backend && uv run pytest tests/e2e/ -v
```

### Cleanup After Testing
```bash
# 1. Delete test data
cd backend && uv run python tests/scripts/delete_test_data.py

# 2. Verify cleanup
cd backend && uv run python tests/scripts/check_db.py

# 3. Stop services (optional)
cd backend && podman-compose down
```

### Debugging Issues
```bash
# 1. Check database status
cd backend && uv run python tests/scripts/check_db.py

# 2. Check users
cd backend && uv run python tests/scripts/check_users.py

# 3. Verify scheduler
cd backend && uv run python tests/scripts/test_scheduler.py

# 4. Recreate data if needed
cd backend && uv run python tests/scripts/delete_test_data.py
cd backend && uv run python tests/scripts/create_test_data.py
```

---

## Environment Variables

All scripts use the following environment variables (with defaults):

```bash
DATABASE_URL=postgresql+asyncpg://trading_user:trading_password@localhost:5432/trading_db
REDIS_URL=redis://localhost:6379/0
```

Set in `.env` file or export before running scripts.

---

## Troubleshooting

### Connection Refused
- Ensure PostgreSQL is running: `podman ps`
- Check connection string in script
- Verify database credentials

### Table Not Found
- Ensure database schema is initialized
- Run migrations: `cd backend && alembic upgrade head`

### No Data Found
- Run `create_test_data.py` to populate database
- Check data with `check_db.py`

### Event Loop Issues
- Ensure no other async operations running
- Close other database connections
- Restart PostgreSQL if needed

---

## Script Dependencies

All scripts require:
- Python 3.13+
- SQLAlchemy with asyncpg
- PostgreSQL driver
- Environment variables or .env file

Install dependencies:
```bash
cd backend && uv pip install -e .
```

---

## Notes

- All scripts are idempotent (safe to run multiple times)
- Scripts use async/await for database operations
- Connection pooling uses NullPool to avoid event loop issues
- Scripts handle connection cleanup properly

