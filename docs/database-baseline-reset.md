# Database Schema Baseline Reset Guide

This document explains how to apply the database schema baseline reset and the new unified approach for database schema management.

## Table of Contents

- [Purpose](#purpose)
- [Background](#background)
- [Prerequisites](#prerequisites)
- [Step-by-Step Instructions](#step-by-step-instructions)
- [Verification Steps](#verification-steps)
- [Going Forward: New Schema Change Workflow](#going-forward-new-schema-change-workflow)
- [Troubleshooting](#troubleshooting)

## Purpose

This baseline reset was necessary to resolve critical inconsistencies in the database schema management:

1. **Dual Sources of Truth**: The database schema was being defined in two places:
   - `backend/init-db.sql` - Used for initial container setup via PostgreSQL's entrypoint
   - `backend/alembic/versions/*.py` - Alembic migration files for schema versioning

2. **Schema Drift**: Over time, columns added via Alembic migrations were not reflected in `init-db.sql`, causing:
   - New development environments to have incomplete schemas
   - Inconsistent behavior between fresh installs and migrated databases

3. **Corrupted Migration State**: The `alembic_version` table contained **two records** instead of one, indicating a corrupted migration history that could cause unpredictable behavior.

4. **Missing Database Defaults**: Some columns (e.g., `accounts.balance_usd`) had defaults defined in SQLAlchemy models but not at the database level.

## Background

### What Changed

The baseline reset consolidated all schema definitions into a single source of truth:

| Component | Before | After |
|-----------|--------|-------|
| `init-db.sql` | Incomplete, missing columns | Complete schema matching SQLAlchemy models |
| Alembic migrations | 6 incremental migrations | 1 baseline migration capturing full schema |
| `alembic_version` | 2 records (corrupted) | 1 record (clean state) |

### Columns Added to init-db.sql

- **accounts**: `maker_fee_bps`, `taker_fee_bps`, `balance_usd`
- **strategies**: `order_preference`, `funding_rate_threshold`
- **strategy_performances**: `total_fees_paid`, `total_funding_paid`, `total_liquidations`
- **decisions**: `asset_decisions`, `portfolio_rationale`, `total_allocation_usd`, `portfolio_risk_level`
- **market_data**: `funding_rate`

## Prerequisites

Before starting the baseline reset, ensure you have:

1. **Podman or Docker** installed and running
2. **Access to the repository** with the latest changes pulled
3. **No critical data** in your local database (this process destroys all data)
4. **Python environment** with `uv` package manager installed
5. **Backend dependencies** installed: `cd backend && uv pip install -e .[dev]`

## Step-by-Step Instructions

### Step 1: Pull the Latest Changes

```bash
cd /path/to/vibex
git pull origin main
```

### Step 2: Stop and Remove Existing Containers and Volumes

This will destroy all existing data. Back up any important data first.

```bash
cd backend
podman-compose down -v
```

The `-v` flag removes the volumes, ensuring a fresh database.

### Step 3: Start the Database

```bash
cd backend
podman-compose up -d postgres
```

Wait for the database to initialize (approximately 10-15 seconds):

```bash
sleep 15
podman logs --tail 30 trading-agent-postgres
```

You should see output ending with:

```text
PostgreSQL init process complete; ready for start up.
...
database system is ready to accept connections
```

### Step 4: Verify the Database Schema

Connect to the database and verify tables exist:

```bash
# Using psql inside the container
podman exec -it trading-agent-postgres psql -U trading_user -d trading_db -c "\dt trading.*"
```

Expected output should list 14 tables in the `trading` schema.

### Step 5: Stamp the Database with Baseline Revision

This marks the database as being at the current Alembic version without running migrations:

```bash
cd backend
ENVIRONMENT=testing uv run alembic stamp head
```

Expected output:

```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running stamp_revision  -> bfb15195438f
```

### Step 6: Start All Services

```bash
cd backend
podman-compose up -d
```

## Verification Steps

After completing the reset, verify the setup is correct:

### 1. Check Alembic Version Table

```bash
cd backend
ENVIRONMENT=testing uv run alembic current
```

Expected output:

```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
bfb15195438f (head)
```

### 2. Verify Single Record in alembic_version

```bash
podman exec -it trading-agent-postgres psql -U trading_user -d trading_db \
  -c "SELECT COUNT(*) as record_count FROM public.alembic_version;"
```

Expected output:

```text
 record_count
--------------
            1
```

### 3. Verify Schema Columns

Check that the accounts table has all expected columns:

```bash
podman exec -it trading-agent-postgres psql -U trading_user -d trading_db \
  -c "SELECT column_name FROM information_schema.columns WHERE table_schema='trading' AND table_name='accounts' ORDER BY ordinal_position;"
```

Should include: `maker_fee_bps`, `taker_fee_bps`, `balance_usd` among others.

### 4. Test Application Startup

```bash
cd backend
podman-compose logs -f backend
```

The application should start without database-related errors.

## Going Forward: New Schema Change Workflow

After the baseline reset, all future schema changes should follow this workflow:

### Making Schema Changes

1. **Modify SQLAlchemy Models**

   Edit the model files in `backend/src/app/models/`:

   ```python
   # Example: Adding a new column to Account
   class Account(Base):
       # ... existing columns ...
       new_column = Column(String(100), nullable=True)
   ```

2. **Generate Migration**

   ```bash
   cd backend
   ENVIRONMENT=testing uv run alembic revision -m "add_new_column_to_accounts" --autogenerate
   ```

3. **Review Generated Migration**

   Check the generated file in `backend/alembic/versions/` to ensure it correctly captures your changes.

4. **Apply Migration**

   ```bash
   cd backend
   ENVIRONMENT=testing uv run alembic upgrade head
   ```

5. **Update init-db.sql** (Important!)

   Also update `backend/init-db.sql` to include the new column so fresh installations have the complete schema.

### Important Notes

- **Always use `ENVIRONMENT=testing`** when running Alembic commands from outside containers (uses `localhost` instead of `postgres` hostname)
- **Keep init-db.sql in sync** with your models for fresh installations
- **TimescaleDB hypertable** for `market_data` is managed in `init-db.sql`, not Alembic
- **Never manually edit** the `alembic_version` table

## Troubleshooting

### Connection Refused Error

```text
psycopg2.OperationalError: could not connect to server: Connection refused
```

**Solution**: Wait for PostgreSQL to fully start:

```bash
sleep 15
podman logs --tail 10 trading-agent-postgres
```

### Host Name Resolution Error

```text
could not translate host name "postgres" to address: Name or service not known
```

**Solution**: Use `ENVIRONMENT=testing` to use `localhost`:

```bash
ENVIRONMENT=testing uv run alembic current
```

### Permission Denied on Volume Removal

```text
Error: removing container ... permission denied
```

**Solution**: This is usually harmless. The volumes are still removed. Verify with:

```bash
podman volume ls
```

### Multiple Records in alembic_version

If you see multiple records after the reset:

```bash
podman exec -it trading-agent-postgres psql -U trading_user -d trading_db \
  -c "DELETE FROM public.alembic_version; INSERT INTO public.alembic_version (version_num) VALUES ('bfb15195438f');"
```

### Tables Already Exist Error

If running `alembic upgrade head` fails with "table already exists":

```bash
# Stamp the database instead of upgrading
ENVIRONMENT=testing uv run alembic stamp head
```

### Database Connection from Application Fails

Ensure environment variables are set correctly:

```bash
# Check the application's database URL
podman exec -it trading-agent-backend env | grep DATABASE
```

### TimescaleDB Extension Not Found

If you see errors about `create_hypertable`:

```bash
podman exec -it trading-agent-postgres psql -U trading_user -d trading_db \
  -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Check current Alembic version | `ENVIRONMENT=testing uv run alembic current` |
| Generate new migration | `ENVIRONMENT=testing uv run alembic revision -m "description" --autogenerate` |
| Apply migrations | `ENVIRONMENT=testing uv run alembic upgrade head` |
| Stamp database (skip migrations) | `ENVIRONMENT=testing uv run alembic stamp head` |
| Rollback one migration | `ENVIRONMENT=testing uv run alembic downgrade -1` |
| View migration history | `ENVIRONMENT=testing uv run alembic history` |
| Reset database completely | `podman-compose down -v && podman-compose up -d` |

---

*Document created: November 2025*
*Baseline revision: `bfb15195438f`*
