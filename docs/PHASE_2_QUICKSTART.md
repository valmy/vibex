# Phase 2: Infrastructure Setup - Quick Start Guide

**Status**: Ready to Begin
**Estimated Duration**: 1-2 days
**Prerequisites**: Phase 1 Complete ✅

---

## Overview

Phase 2 focuses on setting up the development infrastructure, installing dependencies, and verifying that all services can communicate properly.

---

## Step 1: Install Dependencies

### 1.1 Install uv (if not already installed)

```bash
# On Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.sh | iex"
```

### 1.2 Sync Python Dependencies

```bash
cd backend
uv sync
```

This will:
- Create a virtual environment
- Install all dependencies from `pyproject.toml`
- Generate `uv.lock` file

### 1.3 Verify Installation

```bash
# Check Python version
python --version  # Should be 3.13+

# Check FastAPI
uv run python -c "import fastapi; print(fastapi.__version__)"

# Check SQLAlchemy
uv run python -c "import sqlalchemy; print(sqlalchemy.__version__)"
```

---

## Step 2: Set Up Environment Variables

### 2.1 Create .env File

```bash
cd backend
cp .env.example .env
```

### 2.2 Edit .env File

```bash
# Edit with your editor
nano .env
# or
vim .env
```

**Minimum Required Variables:**
```env
ENVIRONMENT=development
DEBUG=true
ASTERDEX_API_KEY=your_key_here
ASTERDEX_API_SECRET=your_secret_here
OPENROUTER_API_KEY=your_key_here
```

### 2.3 Verify Configuration

```bash
# Test configuration loading
uv run python -c "from src.app.core.config import config; print(f'Environment: {config.ENVIRONMENT}')"
```

---

## Step 3: Set Up Database

### 3.1 Start PostgreSQL Container

```bash
cd backend
podman-compose up -d postgres
```

### 3.2 Verify PostgreSQL is Running

```bash
# Check container status
podman-compose ps

# Check logs
podman-compose logs postgres
```

### 3.3 Wait for Database to Be Ready

```bash
# Wait for health check to pass (should see "healthy")
podman-compose ps postgres
```

### 3.4 Initialize Database

```bash
# Connect to PostgreSQL and run init script
podman exec -i trading-agent-postgres psql -U trading_user -d trading_db < init-db.sql
```

### 3.5 Verify Database Setup

```bash
# Connect to database
podman exec -it trading-agent-postgres psql -U trading_user -d trading_db

# In psql prompt:
\dt trading.*  # List tables
\q             # Quit
```

---

## Step 4: Install Development Tools

### 4.1 Install Development Dependencies

```bash
cd backend
uv sync --all-extras
```

### 4.2 Set Up Pre-commit Hooks

```bash
# Install pre-commit
uv pip install pre-commit

# Create .pre-commit-config.yaml (if not exists)
# Then install hooks
pre-commit install
```

### 4.3 Verify Code Quality Tools

```bash
# Check black
uv run black --version

# Check ruff
uv run ruff --version

# Check mypy
uv run mypy --version
```

---

## Step 5: Test Development Environment

### 5.1 Start Backend Service

```bash
cd backend

# Option 1: Using podman-compose
podman-compose up -d backend

# Option 2: Using uvicorn directly
uv run uvicorn src.app.main:app --reload --host 0.0.0.0 --port 3000
```

### 5.2 Verify API is Running

```bash
# In another terminal
curl http://localhost:3000/health

# Expected response:
# {"status":"healthy","app":"AI Trading Agent","version":"1.0.0","environment":"development"}
```

### 5.3 Check API Documentation

```bash
# Open in browser
http://localhost:3000/docs        # Swagger UI
http://localhost:3000/redoc       # ReDoc
http://localhost:3000/openapi.json # OpenAPI JSON
```

### 5.4 Verify Logging

```bash
# Check logs directory
ls -la backend/logs/

# View app logs
tail -f backend/logs/app.log

# View in JSON format
cat backend/logs/app.log | jq .
```

---

## Step 6: Run Tests

### 6.1 Run All Tests

```bash
cd backend
uv run pytest
```

### 6.2 Run with Coverage

```bash
uv run pytest --cov=src --cov-report=html
```

### 6.3 View Coverage Report

```bash
# Open in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

---

## Step 7: Code Quality Checks

### 7.1 Format Code

```bash
cd backend
uv run black src tests
```

### 7.2 Lint Code

```bash
uv run ruff check src tests
```

### 7.3 Type Checking

```bash
uv run mypy src
```

### 7.4 Run All Checks

```bash
uv run pre-commit run --all-files
```

---

## Step 8: Verify Services Communication

### 8.1 Test Database Connection

```bash
# Create a test script
cat > test_db.py << 'EOF'
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def test_connection():
    engine = create_async_engine(
        "postgresql+asyncpg://trading_user:trading_password@localhost:5432/trading_db"
    )
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT 1"))
        print("Database connection successful!")
        print(result.fetchone())

asyncio.run(test_connection())
EOF

# Run test
uv run python test_db.py
```

### 8.2 Test API Endpoints

```bash
# Health check
curl http://localhost:3000/health

# Status
curl http://localhost:3000/status

# Root
curl http://localhost:3000/
```

---

## Troubleshooting

### Issue: Port Already in Use

```bash
# Find process using port 3000
lsof -i :3000

# Kill process
kill -9 <PID>
```

### Issue: Database Connection Failed

```bash
# Check PostgreSQL is running
podman-compose ps postgres

# Check logs
podman-compose logs postgres

# Restart PostgreSQL
podman-compose restart postgres
```

### Issue: Module Import Errors

```bash
# Reinstall dependencies
cd backend
uv sync --force

# Clear Python cache
find . -type d -name __pycache__ -exec rm -r {} +
find . -type f -name "*.pyc" -delete
```

### Issue: Permission Denied

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Check file permissions
ls -la backend/src/app/
```

---

## Verification Checklist

- [ ] Python 3.12+ installed
- [ ] uv installed and working
- [ ] Dependencies installed (`uv sync`)
- [ ] .env file created and configured
- [ ] PostgreSQL container running
- [ ] Database initialized
- [ ] Backend service running
- [ ] API endpoints responding
- [ ] Logging working
- [ ] Tests passing
- [ ] Code quality checks passing

---

## Next Steps

Once Phase 2 is complete:

1. ✅ All dependencies installed
2. ✅ Database running and initialized
3. ✅ Backend service running
4. ✅ API endpoints responding
5. ✅ Logging working
6. ✅ Tests passing

**Proceed to Phase 3**: FastAPI Skeleton Development

---

## Useful Commands

```bash
# Start all services
podman-compose up -d

# Stop all services
podman-compose down

# View logs
podman-compose logs -f backend

# Restart a service
podman-compose restart backend

# Run a command in container
podman exec -it trading-agent-backend bash

# View database
podman exec -it trading-agent-postgres psql -U trading_user -d trading_db

# Clean up everything
podman-compose down -v
```

---

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Podman Documentation](https://docs.podman.io/)
- [uv Documentation](https://docs.astral.sh/uv/)

---

**Status**: Ready to Begin Phase 2
**Estimated Time**: 1-2 days
**Next Phase**: Phase 3 - FastAPI Skeleton Development

