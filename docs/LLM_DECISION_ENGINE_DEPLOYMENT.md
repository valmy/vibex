# LLM Decision Engine - Deployment and Operations Guide

## Overview

This guide covers the deployment, configuration, monitoring, and operational aspects of the LLM Decision Engine for multi-asset perpetual futures trading.

## Table of Contents

1. [Environment Configuration](#environment-configuration)
2. [Database Setup and Migration](#database-setup-and-migration)
3. [Multi-Asset Configuration](#multi-asset-configuration)
4. [Deployment Options](#deployment-options)
5. [Monitoring and Observability](#monitoring-and-observability)
6. [Performance Tuning](#performance-tuning)
7. [Troubleshooting](#troubleshooting)
8. [Migration from Single-Asset](#migration-from-single-asset)

## Environment Configuration

### Required Environment Variables

```bash
# API Keys (Required)
ASTERDEX_API_KEY=your_asterdex_api_key
ASTERDEX_API_SECRET=your_asterdex_api_secret
OPENROUTER_API_KEY=your_openrouter_api_key

# Database Configuration (Required)
DATABASE_URL=postgresql+asyncpg://trading_user:password@localhost:5432/trading_db

# Multi-Asset Configuration (Required)
ASSETS=BTCUSDT,ETHUSDT,SOLUSDT

# LLM Configuration (Optional - defaults shown)
LLM_MODEL=x-ai/grok-4
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2000
LLM_TIMEOUT=30

# Trading Configuration (Optional - defaults shown)
INTERVAL=1h
LONG_INTERVAL=4h
LEVERAGE=2.0
MAX_POSITION_SIZE_USD=10000.0

# Application Configuration (Optional - defaults shown)
API_HOST=0.0.0.0
API_PORT=3000
LOG_LEVEL=INFO
ENVIRONMENT=production
```

### Multi-Account Configuration

For managing multiple trading accounts with separate configurations:

```bash
# Enable multi-account mode
MULTI_ACCOUNT_MODE=true
ACCOUNT_IDS=account1,account2,account3

# Per-account API keys
ASTERDEX_API_KEY_account1=key1
ASTERDEX_API_SECRET_account1=secret1
OPENROUTER_API_KEY_account1=router_key1

ASTERDEX_API_KEY_account2=key2
ASTERDEX_API_SECRET_account2=secret2
OPENROUTER_API_KEY_account2=router_key2

# Per-account LLM models (optional)
LLM_MODEL_account1=x-ai/grok-4
LLM_MODEL_account2=openai/gpt-4

# Per-account asset lists (optional)
ASSETS_account1=BTCUSDT,ETHUSDT
ASSETS_account2=BTCUSDT,SOLUSDT,ADAUSDT
```

### Configuration Validation

Validate your configuration before deployment:

```bash
cd backend
uv run python -c "from app.core.config import get_settings; settings = get_settings(); print('Configuration valid')"
```

## Database Setup and Migration

### Initial Database Setup

1. **Start PostgreSQL with TimescaleDB:**

```bash
cd backend
podman-compose up -d postgres
```

2. **Verify database connection:**

```bash
podman exec -it backend-postgres-1 psql -U trading_user -d trading_db -c "SELECT version();"
```

3. **Run initial database setup:**

```bash
cd backend
podman exec -i backend-postgres-1 psql -U trading_user -d trading_db < init-db.sql
```

### Multi-Asset Schema Migration

The multi-asset decision engine requires database schema updates. Run the migration:

```bash
cd backend
uv run alembic upgrade head
```

This migration (`c38b24f60f6d_add_multi_asset_decision_support.py`) performs the following changes:

**New Tables:**
- `asset_decisions` - Stores individual asset decisions within a trading decision

**Modified Tables:**
- `decisions` table updated with:
  - `portfolio_rationale` (TEXT) - Overall portfolio strategy
  - `total_allocation_usd` (NUMERIC) - Total capital allocation
  - `portfolio_risk_level` (VARCHAR) - Portfolio risk assessment
  - Removed single-asset fields: `symbol`, `action`, `allocation_usd`, `tp_price`, `sl_price`, `rationale`, `confidence`, `risk_level`

**Relationships:**
- One-to-many relationship between `decisions` and `asset_decisions`
- Foreign key: `asset_decisions.decision_id` → `decisions.id`

### Verify Migration

```bash
cd backend
uv run alembic current
```

Expected output:
```
c38b24f60f6d (head) - Add multi-asset decision support
```

### Rollback Migration (if needed)

```bash
cd backend
uv run alembic downgrade -1
```

### Database Backup Before Migration

**Always backup your database before running migrations:**

```bash
# Backup
podman exec backend-postgres-1 pg_dump -U trading_user trading_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore (if needed)
podman exec -i backend-postgres-1 psql -U trading_user -d trading_db < backup_20250115_103000.sql
```

## Multi-Asset Configuration

### Understanding the ASSETS Environment Variable

The `ASSETS` environment variable defines which perpetual futures contracts the LLM Decision Engine will analyze:

```bash
# Analyze BTC, ETH, and SOL perpetual futures
export ASSETS="BTCUSDT,ETHUSDT,SOLUSDT"

# Analyze more assets
export ASSETS="BTCUSDT,ETHUSDT,SOLUSDT,ADAUSDT,DOGEUSDT"

# Single asset (still uses multi-asset structure)
export ASSETS="BTCUSDT"
```

**Important Notes:**
- Use comma-separated values without spaces
- Symbol format must match your exchange (typically `{BASE}{QUOTE}` like `BTCUSDT`)
- All symbols must be valid perpetual futures contracts on AsterDEX
- Minimum: 1 asset, Recommended: 3-5 assets, Maximum: 10 assets

### Asset Selection Best Practices

**For Conservative Trading:**
```bash
ASSETS="BTCUSDT,ETHUSDT"  # Major assets only
```

**For Balanced Trading:**
```bash
ASSETS="BTCUSDT,ETHUSDT,SOLUSDT"  # Mix of major and mid-cap
```

**For Aggressive Trading:**
```bash
ASSETS="BTCUSDT,ETHUSDT,SOLUSDT,ADAUSDT,DOGEUSDT"  # Diverse portfolio
```

### Performance Considerations

- **3-5 assets**: Optimal balance between opportunity and performance
- **6-10 assets**: Increased decision time (3-5 seconds), higher API costs
- **10+ assets**: Not recommended - significant performance impact

### Verifying Asset Configuration

```bash
cd backend
uv run python -c "
from app.core.config import get_settings
settings = get_settings()
print(f'Configured assets: {settings.ASSETS}')
print(f'Asset count: {len(settings.ASSETS)}')
"
```

## Deployment Options

### Option 1: Docker/Podman Compose (Recommended)

**Production deployment with all services:**

1. **Create production environment file:**

```bash
cp backend/.env.example backend/.env
# Edit .env with your production values
```

2. **Start all services:**

```bash
cd backend
podman-compose up -d
```

3. **Verify services:**

```bash
podman-compose ps
podman-compose logs -f backend
```

4. **Run database migrations:**

```bash
podman-compose exec backend uv run alembic upgrade head
```

5. **Health check:**

```bash
curl http://localhost:3000/health
```

### Option 2: Standalone Deployment

**For running outside containers:**

1. **Install dependencies:**

```bash
cd backend
uv pip install -e .
uv pip install -e .[dev,test]
```

2. **Start PostgreSQL separately:**

```bash
podman run -d \
  --name trading-postgres \
  -e POSTGRES_USER=trading_user \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=trading_db \
  -p 5432:5432 \
  timescale/timescaledb:latest-pg17
```

3. **Run migrations:**

```bash
cd backend
uv run alembic upgrade head
```

4. **Start application:**

```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 3000
```

### Option 3: Development Mode

**For development with hot-reload:**

1. **Copy development override:**

```bash
cd backend
cp compose.override.yml.example compose.override.yml
```

2. **Start with development settings:**

```bash
cd backend
podman-compose up -d
```

This enables:
- Hot-reload on code changes
- Debug logging
- Development-friendly settings

## Monitoring and Observability

### Log Files

The LLM Decision Engine generates structured logs in multiple files:

```
backend/logs/
├── app.log           # General application logs
├── llm.log          # LLM-specific logs (decisions, API calls)
├── trading.log      # Trading execution logs
├── market_data.log  # Market data collection logs
└── errors.log       # Error-only logs
```

### Monitoring LLM Decision Generation

**View LLM decision logs:**

```bash
tail -f backend/logs/llm.log | grep "decision_generated"
```

**Monitor API calls:**

```bash
tail -f backend/logs/llm.log | grep "llm_api_call"
```

**Track validation failures:**

```bash
tail -f backend/logs/llm.log | grep "validation_failed"
```

### Key Metrics to Monitor

1. **Decision Generation Metrics:**
   - Decision generation time (target: < 5 seconds)
   - Validation success rate (target: > 95%)
   - Cache hit rate (target: > 60%)
   - API error rate (target: < 1%)

2. **Performance Metrics:**
   - Win rate by asset
   - Total P&L
   - Sharpe ratio
   - Maximum drawdown

3. **System Health Metrics:**
   - API response times
   - Database query performance
   - Memory usage
   - CPU utilization

### Monitoring Endpoints

**System health:**
```bash
curl http://localhost:3000/health
```

**Decision metrics:**
```bash
curl "http://localhost:3000/api/v1/decisions/metrics?timeframe=24h"
```

**Strategy performance:**
```bash
curl "http://localhost:3000/api/v1/strategies/conservative_swing/performance?timeframe=7d"
```

### Prometheus Integration (Optional)

If using Prometheus for monitoring:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'trading-agent'
    static_configs:
      - targets: ['localhost:3000']
    metrics_path: '/metrics'
    scrape_interval: 15s
```

### Alerting Recommendations

Set up alerts for:

1. **Critical Issues:**
   - Decision generation failures > 5% in 5 minutes
   - Database connection failures
   - LLM API unavailability > 2 minutes

2. **Performance Issues:**
   - Decision generation time > 10 seconds
   - Validation failure rate > 10%
   - Cache hit rate < 40%

3. **Trading Issues:**
   - Daily loss exceeds threshold
   - Win rate drops below 40%
   - Position size violations

## Performance Tuning

### LLM Model Selection

Different models have different performance characteristics:

| Model | Speed | Cost | Quality | Best For |
|-------|-------|------|---------|----------|
| x-ai/grok-4 | Fast | Low | High | Production (default) |
| openai/gpt-4 | Medium | High | Very High | High-stakes decisions |
| deepseek/deepseek-r1 | Fast | Very Low | Good | High-frequency trading |

**Configure model per account:**

```bash
# Global default
LLM_MODEL=x-ai/grok-4

# Per-account override
LLM_MODEL_account1=openai/gpt-4
LLM_MODEL_account2=deepseek/deepseek-r1
```

### Caching Strategy

The decision engine implements intelligent caching:

**Cache Duration:**
- Market data: 30 seconds
- Technical indicators: 60 seconds
- Decisions: 5 minutes (invalidated on significant price changes)

**Cache Configuration:**

```bash
# Adjust cache TTL (seconds)
DECISION_CACHE_TTL=300
MARKET_DATA_CACHE_TTL=30
INDICATOR_CACHE_TTL=60

# Disable caching (not recommended for production)
ENABLE_CACHING=false
```

### Database Performance

**Connection Pool Settings:**

```bash
# Adjust based on load
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
```

**Query Optimization:**

```sql
-- Create indexes for common queries
CREATE INDEX idx_decisions_account_timestamp ON decisions(account_id, timestamp DESC);
CREATE INDEX idx_asset_decisions_symbol ON asset_decisions(asset);
CREATE INDEX idx_decisions_strategy ON decisions(strategy_used);
```

### Multi-Asset Performance Optimization

**Optimal Asset Count:**
- 3-5 assets: Best balance (2-3 second decisions)
- 6-8 assets: Acceptable (3-5 second decisions)
- 9-10 assets: Maximum recommended (5-8 second decisions)

**Parallel Processing:**

The engine processes assets in parallel where possible. Ensure adequate resources:

```bash
# Increase worker threads for parallel processing
WORKER_THREADS=4

# Adjust based on CPU cores
MAX_CONCURRENT_REQUESTS=10
```

### API Rate Limiting

**Configure rate limits:**

```bash
# Requests per minute
DECISION_RATE_LIMIT=60
HISTORY_RATE_LIMIT=120
STRATEGY_RATE_LIMIT=30
```

## Troubleshooting

### Common Issues and Solutions

#### Issue 1: "Insufficient market data" Error

**Symptoms:**
```json
{
  "error": "Insufficient market data",
  "details": "Unable to fetch data for SOLUSDT"
}
```

**Solutions:**

1. **Verify symbol format:**
```bash
# Check configured assets
echo $ASSETS

# Verify symbols are valid on AsterDEX
curl "https://api.asterdex.com/v1/symbols" | grep SOLUSDT
```

2. **Check market data service:**
```bash
# View market data logs
tail -f backend/logs/market_data.log

# Test market data endpoint
curl "http://localhost:3000/api/v1/market-data/SOLUSDT"
```

3. **Reduce asset count temporarily:**
```bash
# Test with fewer assets
export ASSETS="BTCUSDT,ETHUSDT"
```

#### Issue 2: High Validation Failure Rate

**Symptoms:**
- Validation success rate < 90%
- Frequent "allocation exceeds available capital" errors

**Solutions:**

1. **Review strategy risk parameters:**
```bash
# Check current strategy
curl "http://localhost:3000/api/v1/strategies/account/1"

# Adjust risk parameters
curl -X POST "http://localhost:3000/api/v1/strategies/account/1/switch" \
  -H "Content-Type: application/json" \
  -d '{"strategy_id": "conservative_swing"}'
```

2. **Check account balance:**
```bash
# Verify available capital
curl "http://localhost:3000/api/v1/accounts/1"
```

3. **Review validation logs:**
```bash
tail -f backend/logs/llm.log | grep "validation_failed"
```

#### Issue 3: Slow Decision Generation

**Symptoms:**
- Decision generation > 10 seconds
- Timeout errors

**Solutions:**

1. **Reduce asset count:**
```bash
# Analyze fewer assets
export ASSETS="BTCUSDT,ETHUSDT,SOLUSDT"
```

2. **Switch to faster LLM model:**
```bash
export LLM_MODEL="deepseek/deepseek-r1"
```

3. **Check technical analysis performance:**
```bash
# Monitor indicator calculation time
tail -f backend/logs/app.log | grep "indicator_calculation"
```

4. **Optimize database queries:**
```bash
# Check slow queries
podman exec backend-postgres-1 psql -U trading_user -d trading_db -c "
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;"
```

#### Issue 4: LLM API Errors

**Symptoms:**
```json
{
  "error": "LLM API unavailable",
  "code": "LLM_API_ERROR"
}
```

**Solutions:**

1. **Verify API key:**
```bash
# Test OpenRouter API
curl -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  "https://openrouter.ai/api/v1/models"
```

2. **Check rate limits:**
```bash
# View API usage
curl "http://localhost:3000/api/v1/decisions/metrics?timeframe=1h"
```

3. **Enable circuit breaker:**
```bash
# Circuit breaker automatically enabled
# Check status
tail -f backend/logs/llm.log | grep "circuit_breaker"
```

4. **Switch to backup model:**
```bash
# Automatic fallback configured
# Or manually switch
export LLM_MODEL="openai/gpt-4"
```

#### Issue 5: Database Migration Failures

**Symptoms:**
- Migration fails with constraint errors
- Data loss concerns

**Solutions:**

1. **Backup database first:**
```bash
podman exec backend-postgres-1 pg_dump -U trading_user trading_db > backup.sql
```

2. **Check current migration state:**
```bash
cd backend
uv run alembic current
uv run alembic history
```

3. **Resolve conflicts:**
```bash
# If migration is stuck
uv run alembic stamp head

# Or rollback and retry
uv run alembic downgrade -1
uv run alembic upgrade head
```

4. **Manual data migration (if needed):**
```sql
-- Connect to database
podman exec -it backend-postgres-1 psql -U trading_user -d trading_db

-- Check existing data
SELECT COUNT(*) FROM decisions;

-- Verify new schema
\d decisions
\d asset_decisions
```

### Debug Mode

Enable debug logging for troubleshooting:

```bash
export LOG_LEVEL=DEBUG
export ENVIRONMENT=development
```

View detailed logs:
```bash
tail -f backend/logs/app.log | grep DEBUG
```

## Migration from Single-Asset

### Overview

If you're migrating from a single-asset implementation to the multi-asset system, follow these steps:

### Step 1: Backup Existing Data

```bash
# Backup database
podman exec backend-postgres-1 pg_dump -U trading_user trading_db > backup_pre_migration.sql

# Backup configuration
cp backend/.env backend/.env.backup
```

### Step 2: Update Configuration

```bash
# Update .env file
# Change from:
SYMBOL=BTCUSDT

# To:
ASSETS=BTCUSDT,ETHUSDT,SOLUSDT
```

### Step 3: Run Database Migration

```bash
cd backend
uv run alembic upgrade head
```

The migration automatically:
- Creates `asset_decisions` table
- Migrates existing single-asset decisions to multi-asset format
- Preserves all historical data
- Updates relationships

### Step 4: Verify Migration

```bash
# Check decision count
podman exec backend-postgres-1 psql -U trading_user -d trading_db -c "
SELECT COUNT(*) as total_decisions FROM decisions;
SELECT COUNT(*) as total_asset_decisions FROM asset_decisions;
"

# Verify data integrity
podman exec backend-postgres-1 psql -U trading_user -d trading_db -c "
SELECT d.id, d.portfolio_rationale, COUNT(ad.id) as asset_count
FROM decisions d
LEFT JOIN asset_decisions ad ON d.id = ad.decision_id
GROUP BY d.id
LIMIT 10;
"
```

### Step 5: Update Application Code

If you have custom integrations:

**Before (single-asset):**
```python
decision = {
    "symbol": "BTCUSDT",
    "action": "buy",
    "allocation_usd": 5000.0,
    "rationale": "Strong momentum"
}
```

**After (multi-asset):**
```python
decision = {
    "decisions": [
        {
            "asset": "BTCUSDT",
            "action": "buy",
            "allocation_usd": 5000.0,
            "rationale": "Strong momentum",
            "confidence": 85.0,
            "risk_level": "medium"
        }
    ],
    "portfolio_rationale": "Focus on BTC strength",
    "total_allocation_usd": 5000.0,
    "portfolio_risk_level": "medium"
}
```

### Step 6: Test Multi-Asset Functionality

```bash
# Generate test decision
curl -X POST "http://localhost:3000/api/v1/decisions/generate" \
  -H "Content-Type: application/json" \
  -d '{"account_id": 1}'

# Verify response structure
# Should contain "decisions" array with multiple assets
```

### Step 7: Monitor Performance

```bash
# Monitor decision generation
tail -f backend/logs/llm.log | grep "decision_generated"

# Check performance metrics
curl "http://localhost:3000/api/v1/decisions/metrics?timeframe=1h"
```

### Rollback Plan

If migration issues occur:

```bash
# Stop application
podman-compose down

# Restore database
podman exec -i backend-postgres-1 psql -U trading_user -d trading_db < backup_pre_migration.sql

# Restore configuration
cp backend/.env.backup backend/.env

# Rollback migration
cd backend
uv run alembic downgrade -1

# Restart application
podman-compose up -d
```

## Production Checklist

Before deploying to production:

- [ ] Environment variables configured and validated
- [ ] Database backup completed
- [ ] Database migrations applied successfully
- [ ] ASSETS environment variable configured with valid symbols
- [ ] LLM API keys tested and working
- [ ] AsterDEX API keys tested and working
- [ ] Log rotation configured
- [ ] Monitoring and alerting set up
- [ ] Rate limits configured appropriately
- [ ] Strategy risk parameters reviewed
- [ ] Performance testing completed
- [ ] Rollback plan documented
- [ ] Team trained on operations procedures

## Support and Resources

- **API Documentation:** `docs/LLM_DECISION_ENGINE_API.md`
- **Troubleshooting FAQ:** `docs/TROUBLESHOOTING_FAQ.md`
- **System Logs:** `backend/logs/`
- **Database Migrations:** `backend/alembic/versions/`
- **Configuration Examples:** `backend/.env.example`

## Maintenance Tasks

### Daily

- Monitor decision generation metrics
- Review error logs
- Check API usage and costs
- Verify trading performance

### Weekly

- Review strategy performance
- Analyze win rates by asset
- Check database size and performance
- Update risk parameters if needed

### Monthly

- Database backup and archival
- Performance optimization review
- Cost analysis and optimization
- Strategy effectiveness evaluation
- Security updates and patches

## Conclusion

The LLM Decision Engine provides powerful multi-asset trading capabilities. Proper deployment, configuration, and monitoring ensure reliable operation and optimal performance. Follow this guide for successful deployment and ongoing operations.
