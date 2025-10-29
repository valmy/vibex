# Technology Stack

## Backend Framework
- **FastAPI**: Modern Python web framework with automatic OpenAPI documentation
- **Uvicorn**: ASGI server for production deployment
- **WebSockets**: Real-time communication support
- **Pydantic**: Data validation and serialization with type hints

## Database
- **PostgreSQL 17**: Primary database with ACID compliance
- **TimescaleDB**: Extension for optimized time-series data storage
- **SQLAlchemy 2.0**: Modern async ORM with declarative models
- **Alembic**: Database migration management
- **AsyncPG**: High-performance async PostgreSQL driver

## Python Environment
- **Python 3.13+**: Required minimum version
- **uv**: Fast Python package manager and dependency resolver
- **Pydantic Settings**: Environment-based configuration management

## External Integrations
- **OpenRouter API**: LLM model access (Grok-4 default, supports multiple models)
- **AsterDEX API**: Cryptocurrency futures trading platform via aster-connector-python
- **TA-Lib**: Technical analysis indicators library
- **Aster Connector**: Official Python library for AsterDEX REST and WebSocket APIs

## Development Tools
- **Black**: Code formatting (100 char line length)
- **Ruff**: Fast Python linter and formatter
- **MyPy**: Static type checking
- **Pytest**: Testing framework with async support
- **Pre-commit**: Git hooks for code quality

## Containerization
- **Podman/Docker**: Container runtime
- **Podman Compose**: Multi-container orchestration
- **TimescaleDB Image**: `timescale/timescaledb:latest-pg17`

## Common Commands

### Development Setup (CRUSH Workflow)
```bash
# Install dependencies (always use uv for better performance)
uv pip install -e backend/
uv pip install -e backend/[dev,test]

# Alternative: Install with sync
uv sync

# Start development environment
cd backend && uv run podman-compose up -d

# Run database migrations
cd backend && uv run alembic upgrade head

# Start development server
cd backend && uv run uvicorn src.app.main:app --reload --host 0.0.0.0 --port 3000

# Alternative: Run with Python module
cd backend && uv run python -m app.main
```

### Code Quality (CRUSH Standards)
```bash
# Format code (100 char line length)
cd backend && uv run black .

# Lint code with auto-fix
cd backend && uv run ruff check . --fix

# Type checking
cd backend && uv run mypy src/

# Run all quality checks
cd backend && uv run pre-commit run --all-files

# Complete quality pipeline
cd backend && uv run black . && uv run ruff check . --fix && uv run mypy src/
```

### Testing (Comprehensive)
```bash
# Run all tests
cd backend && uv run pytest

# Run with coverage
cd backend && uv run pytest --cov=src/app

# Run specific test file
cd backend && uv run pytest tests/unit/test_config_manager.py

# Run specific test function
cd backend && uv run pytest tests/unit/test_config_manager.py::test_manager_singleton

# Run integration tests
cd backend && uv run pytest tests/integration/

# Run with verbose output
cd backend && uv run pytest -v
```

### Database Operations
```bash
# Create new migration
cd backend && uv run alembic revision --autogenerate -m "Description"

# Apply migrations
cd backend && uv run alembic upgrade head

# Rollback migration
cd backend && uv run alembic downgrade -1
```

### Container Management
```bash
# Build image
cd backend && podman build -t trading-agent:latest .

# Run container
cd backend && podman run -p 3000:3000 --env-file .env trading-agent:latest

# Using Podman Compose
cd backend && uv run podman-compose up -d
cd backend && uv run podman-compose logs -f backend
cd backend && uv run podman-compose down
cd backend && uv run podman-compose down -v
```

### Environment Management
```bash
# Copy environment template
cp backend/.env.example backend/.env

# Run with specific environment
cd backend && ENVIRONMENT=production uv run python -m app.main
```
## Co
nfiguration System

### Environment Variables (Required)
```bash
ASTERDEX_API_KEY=your_key
ASTERDEX_API_SECRET=your_secret
OPENROUTER_API_KEY=your_key
DATABASE_URL=postgresql://user:password@postgres:5432/trading_db
```

### Environment Variables (Optional)
```bash
API_HOST=0.0.0.0
API_PORT=3000
LLM_MODEL=x-ai/grok-4
ASSETS=BTC,ETH,SOL
INTERVAL=1h
LONG_INTERVAL=1h
LEVERAGE=2.0
MAX_POSITION_SIZE_USD=10000.0
LOG_LEVEL=INFO
ENVIRONMENT=development
MULTI_ACCOUNT_MODE=false
CONFIG_WATCH_ENABLED=true
CONFIG_CACHE_TTL=3600
```

### Multi-Account Configuration
```bash
MULTI_ACCOUNT_MODE=true
ACCOUNT_IDS=account1,account2,account3

# Per-account settings
ASTERDEX_API_KEY_account1=key1
ASTERDEX_API_SECRET_account1=secret1
OPENROUTER_API_KEY_account1=router_key1
LLM_MODEL_account1=x-ai/grok-4
```

## Development Standards (CRUSH)

### Code Style
- **Line Length**: 100 characters (Black + Ruff)
- **Indentation**: 4 spaces (no tabs)
- **Imports**: Absolute imports preferred, grouped by standard/third-party/local
- **Type Hints**: Required for all function parameters and return values
- **Naming**: snake_case for functions/variables, PascalCase for classes, UPPER_SNAKE_CASE for constants
- **Private Methods**: Leading underscore prefix

### Documentation
- **Docstrings**: Google-style with Args/Returns sections
- **Type Information**: Include in docstrings
- **Comments**: Focus on why, not what

### Error Handling
- **Custom Exceptions**: Create specific exception classes
- **Meaningful Messages**: Always include context
- **Appropriate Level**: Handle exceptions at the right abstraction level
- **Logging**: Log errors without exposing sensitive information