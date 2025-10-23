# Quick Reference Guide

**Document Version**: 1.0  
**Created**: October 23, 2025

---

## Directory Structure at a Glance

```
backend/
├── src/app/
│   ├── main.py                 # FastAPI app entry point
│   ├── core/
│   │   ├── config.py          # Configuration management
│   │   ├── logging.py         # Logging setup
│   │   └── constants.py       # Constants
│   ├── services/
│   │   ├── trading/           # Trading operations
│   │   ├── market_data/       # Market data handling
│   │   ├── decision_engine/   # LLM decision making
│   │   ├── execution/         # Order execution
│   │   ├── account/           # Account management
│   │   └── reconciliation/    # State reconciliation
│   ├── models/                # SQLAlchemy ORM models
│   ├── schemas/               # Pydantic validation schemas
│   ├── api/
│   │   ├── routes/            # HTTP endpoints
│   │   └── websockets/        # WebSocket handlers
│   ├── db/
│   │   ├── database.py        # Connection management
│   │   └── migrations/        # Alembic migrations
│   └── utils/                 # Utility functions
├── tests/
│   ├── unit/                  # Unit tests
│   └── integration/           # Integration tests
├── pyproject.toml             # Project metadata
├── Dockerfile                 # Container image
├── podman-compose.yml         # Orchestration
├── .env.example               # Example env vars
└── logs/                      # Application logs
```

---

## Key Files and Their Purpose

| File | Purpose |
|------|---------|
| `src/app/main.py` | FastAPI application entry point |
| `src/app/core/config.py` | Environment configuration |
| `src/app/core/logging.py` | Logging setup |
| `pyproject.toml` | Project metadata and dependencies |
| `Dockerfile` | Container image definition |
| `podman-compose.yml` | Service orchestration |
| `.env.example` | Template for environment variables |
| `tests/conftest.py` | Pytest fixtures and configuration |

---

## Environment Variables

### Required
```bash
ASTERDEX_API_KEY=your_key
ASTERDEX_API_SECRET=your_secret
OPENROUTER_API_KEY=your_key
DATABASE_URL=postgresql://user:password@postgres:5432/trading_db
```

### Optional
```bash
API_HOST=0.0.0.0
API_PORT=3000
LLM_MODEL=x-ai/grok-4
ASSETS=BTC,ETH,SOL
INTERVAL=1h
LOG_LEVEL=INFO
ENVIRONMENT=development
```

---

## Common Commands

### Development Setup
```bash
# Install dependencies
uv sync

# Start development environment
podman-compose up

# Run development server
uvicorn src.app.main:app --host 0.0.0.0 --port 3000 --reload
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/unit/test_config.py

# Run with verbose output
pytest -v
```

### Code Quality
```bash
# Format code
black src tests

# Lint code
ruff check src tests

# Type checking
mypy src

# All checks
black src tests && ruff check src tests && mypy src
```

### Database
```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

### Logging
```bash
# View logs
tail -f logs/app.log

# View trading logs
tail -f logs/trading.log

# View errors
tail -f logs/errors.log
```

---

## Configuration Hierarchy

1. **Environment Variables** (highest priority)
2. **.env.local** (local overrides)
3. **.env** (default values)
4. **Config Classes** (fallback defaults)

---

## API Endpoints

### Health & Status
- `GET /health` - Health check
- `GET /status` - System status
- `GET /docs` - OpenAPI documentation

### Trading Data
- `GET /diary` - Trading diary entries
- `GET /positions` - Current positions
- `GET /performance` - Performance metrics
- `GET /logs` - Log file contents

### Account Management
- `GET /accounts` - List all accounts
- `GET /accounts/{account_id}` - Account details
- `GET /accounts/{account_id}/status` - Account status

### WebSocket Endpoints
- `WS /ws/trading-events` - Trading decisions and executions
- `WS /ws/market-data` - Market prices and indicators
- `WS /ws/positions` - Position updates

---

## Log Levels

| Level | Usage | Example |
|-------|-------|---------|
| DEBUG | Detailed debugging info | Variable values, function calls |
| INFO | General information | Trade executed, API call made |
| WARNING | Potential issues | Retry attempt, unusual value |
| ERROR | Failures | API error, validation failed |
| CRITICAL | System failures | Database connection lost |

---

## Dependency Groups

### Main (Production)
```
fastapi, uvicorn, websockets, python-dotenv, web3, aiohttp, 
openai, requests, rich, aster-connector-python, TA-Lib, typer,
sqlalchemy, psycopg2-binary, asyncpg, alembic
```

### Dev (Development)
```
black, ruff, mypy, pre-commit, ipython
```

### Test (Testing)
```
pytest, pytest-asyncio, pytest-cov, httpx, faker
```

---

## Configuration Classes

### BaseConfig
Common settings for all environments

### DevelopmentConfig
- Debug mode enabled
- Verbose logging (DEBUG level)
- Hot-reload enabled
- Database: PostgreSQL

### TestingConfig
- Debug mode disabled
- Minimal logging (WARNING level)
- Database: In-memory SQLite or test PostgreSQL

### ProductionConfig
- Debug mode disabled
- Error-only logging (ERROR level)
- Connection pooling enabled
- Database: PostgreSQL with optimizations

---

## Multi-Account Configuration

### Environment Variables
```bash
MULTI_ACCOUNT_MODE=true
ACCOUNT_IDS=account1,account2,account3

ASTERDEX_API_KEY_account1=key1
ASTERDEX_API_SECRET_account1=secret1
OPENROUTER_API_KEY_account1=router_key1
LLM_MODEL_account1=x-ai/grok-4

ASTERDEX_API_KEY_account2=key2
# ... etc
```

### YAML Configuration
```yaml
accounts:
  - id: account1
    asterdex:
      api_key: ${ASTERDEX_KEY_1}
      api_secret: ${ASTERDEX_SECRET_1}
    openrouter:
      api_key: ${OPENROUTER_KEY_1}
    llm_model: x-ai/grok-4
    assets: [BTC, ETH]
    interval: 1h
```

---

## Troubleshooting

### Issue: Podman service won't start
**Solution**: Check logs with `podman-compose logs backend`

### Issue: Database connection failed
**Solution**: Verify DATABASE_URL in .env and PostgreSQL is running

### Issue: TA-Lib import error
**Solution**: Ensure system dependencies installed (see Dockerfile)

### Issue: API not responding
**Solution**: Check if uvicorn is running on port 3000

### Issue: WebSocket connection failed
**Solution**: Verify WebSocket endpoint URL and CORS configuration

---

## Performance Tips

1. **Use connection pooling** for database
2. **Enable caching** for market data
3. **Use async/await** for I/O operations
4. **Batch API requests** when possible
5. **Monitor log file sizes** and rotation

---

## Security Checklist

- [ ] Never commit .env files
- [ ] Use .env.local for local overrides
- [ ] Mask sensitive data in logs
- [ ] Validate all external inputs
- [ ] Use HTTPS in production
- [ ] Rotate API keys regularly
- [ ] Use strong database passwords
- [ ] Enable database backups

---

## Development Workflow

1. Create feature branch
2. Make changes
3. Run tests: `pytest`
4. Format code: `black src tests`
5. Lint code: `ruff check src tests`
6. Type check: `mypy src`
7. Commit changes
8. Push to GitHub
9. Create pull request

---

## Useful Links

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Podman Documentation](https://podman.io/docs/)

---

## Contact & Support

For questions or issues:
1. Check REQUIREMENTS.md for specifications
2. Check IMPLEMENTATION_PLAN.md for architecture
3. Check IMPLEMENTATION_DECISIONS.md for decisions
4. Review code comments and docstrings
5. Check test files for usage examples

---

**Last Updated**: October 23, 2025

