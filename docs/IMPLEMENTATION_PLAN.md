# AI Trading Agent - Implementation Plan

**Document Version**: 1.0
**Created**: October 23, 2025
**Status**: Planning Phase - Ready for Implementation

---

## Executive Summary

This document outlines the detailed implementation plan for setting up the basic skeleton of the AI Trading Agent application. The plan covers five major areas: repository structure, development environment, dependencies, configuration management, and logging system.

**Key Decisions Made**:
- **Web Framework**: FastAPI (specified in REQUIREMENTS.md)
- **Dependency Manager**: `uv` (specified in REQUIREMENTS.md)
- **Database**: PostgreSQL with TimescaleDB extension (recommended in REQUIREMENTS.md)
- **Container Runtime**: Podman with podman-compose (replacing Docker)
- **Logging Framework**: Python's built-in logging module with JSON formatting
- **Architecture**: Monorepo with separate backend and frontend directories

---

## 1. Python Backend Repository Structure

### 1.1 Monorepo Root Structure
```
vibex/
├── backend/                    # Python backend application
├── frontend/                   # TypeScript/React frontend (future)
├── docs/                       # Documentation
├── scripts/                    # Utility scripts
├── .github/                    # GitHub workflows and configs
├── .gitignore
├── README.md
├── LICENSE
└── pyproject.toml             # Root project config (if needed)
```

### 1.2 Backend Directory Structure
```
backend/
├── src/
│   ├── app/                   # Main application code
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI app entry point
│   │   ├── core/             # Core functionality
│   │   │   ├── config.py     # Configuration management
│   │   │   ├── logging.py    # Logging setup
│   │   │   └── constants.py  # Application constants
│   │   ├── services/         # Business logic services
│   │   │   ├── trading/      # Trading operations
│   │   │   ├── market_data/  # Market data handling
│   │   │   ├── decision_engine/  # LLM decision making
│   │   │   └── execution/    # Order execution
│   │   ├── models/           # Data models (SQLAlchemy ORM)
│   │   ├── schemas/          # Pydantic schemas (API validation)
│   │   ├── api/              # API endpoints
│   │   │   ├── routes/       # Route handlers
│   │   │   └── websockets/   # WebSocket handlers
│   │   ├── db/               # Database utilities
│   │   │   ├── database.py   # Connection management
│   │   │   └── migrations/   # Alembic migrations
│   │   └── utils/            # Utility functions
│   ├── tests/                # Test suite
│   │   ├── unit/
│   │   ├── integration/
│   │   └── conftest.py       # Pytest fixtures
│   └── scripts/              # Utility scripts
├── pyproject.toml            # Project metadata and dependencies
├── uv.lock                   # Locked dependencies
├── .env.example              # Example environment variables
├── .env.local               # Local overrides (git-ignored)
├── Dockerfile               # Container image definition
├── podman-compose.yml       # Podman compose configuration
├── logs/                    # Application logs (git-ignored)
├── data/                    # Local data storage (git-ignored)
└── README.md               # Backend-specific documentation
```

### 1.3 Module Organization Details

**Core Module** (`src/app/core/`):
- `config.py`: Pydantic BaseSettings for environment configuration
- `logging.py`: Logging setup and configuration
- `constants.py`: Application-wide constants

**Services Module** (`src/app/services/`):
- `trading/`: Trading operations, position management
- `market_data/`: Market data fetching, technical analysis
- `decision_engine/`: LLM integration, decision making
- `execution/`: Order placement, risk management

**API Module** (`src/app/api/`):
- `routes/`: HTTP endpoint handlers
- `websockets/`: WebSocket connection handlers

### 1.4 Configuration and Artifact Locations
- **pyproject.toml**: Root of backend/ directory
- **uv.lock**: Root of backend/ directory (locked dependencies)
- **.env files**: Root of backend/ directory
- **logs/**: `backend/logs/` (git-ignored)
- **data/**: `backend/data/` (git-ignored)
- **Migrations**: `backend/src/app/db/migrations/`

### 1.5 Future TypeScript Frontend Integration
```
frontend/
├── src/
│   ├── components/          # React components
│   ├── pages/              # Page components
│   ├── services/           # API client services
│   ├── hooks/              # Custom React hooks
│   ├── types/              # TypeScript type definitions
│   └── App.tsx
├── public/                 # Static assets
├── package.json
├── tsconfig.json
├── vite.config.ts         # Vite build config
└── README.md
```

---

## 2. Development Environment with Podman

### 2.1 podman-compose.yml Structure

**Services**:
1. **Python Backend Service**
   - Image: Python 3.13-slim with FastAPI
   - Port: 3000 (exposed)
   - Volumes: code (hot-reload), logs (persistent)
   - Environment: Development configuration

2. **PostgreSQL Service**
   - Image: postgres:16-alpine
   - Port: 5432 (internal only)
   - Volumes: data (persistent)
   - Environment: Database credentials

### 2.2 Python Backend Service Configuration
- **Build**: Dockerfile with multi-stage build
- **Ports**: `3000:3000` (FastAPI)
- **Volumes**:
  - `./backend/src:/app/src` (code hot-reload)
  - `./backend/logs:/app/logs` (persistent logs)
- **Environment Variables**: Loaded from .env file
- **Command**: `uvicorn src.app.main:app --host 0.0.0.0 --port 3000 --reload`

### 2.3 PostgreSQL Service Configuration
- **Image**: `postgres:16-alpine`
- **Ports**: `5432:5432` (internal network)
- **Volumes**: `postgres_data:/var/lib/postgresql/data`
- **Environment**:
  - `POSTGRES_USER=trading_user`
  - `POSTGRES_PASSWORD=<from .env>`
  - `POSTGRES_DB=trading_db`

### 2.4 Volume Mounts for Development
- **Code Volume**: `./backend/src:/app/src` - enables hot-reload
- **Data Volume**: `postgres_data` - persistent PostgreSQL data
- **Logs Volume**: `./backend/logs:/app/logs` - persistent application logs

### 2.5 Networking Between Services
- **Network**: `trading-network` (bridge network)
- **Service Discovery**: Backend connects to PostgreSQL via `postgres:5432`
- **Connection String**: `postgresql://trading_user:password@postgres:5432/trading_db`

### 2.6 Environment-Specific Configurations
- **Development**: `podman-compose.yml` (default)
- **Testing**: `podman-compose.test.yml` (in-memory DB or test DB)
- **Production**: `podman-compose.prod.yml` (optimized, no hot-reload)

---

## 3. Python Dependencies and Server Setup

### 3.1 Web Framework Confirmation
**FastAPI** is confirmed as the web framework based on REQUIREMENTS.md Section 3.4.1

### 3.2 Core Backend Dependencies
```
fastapi>=0.115.0              # Web framework
uvicorn>=0.32.0               # ASGI server
websockets>=13.0              # WebSocket support
python-dotenv>=1.1.1          # Environment variables
web3>=7.14.0                  # Web3 utilities
aiohttp>=3.13.1               # Async HTTP client
openai>=2.5.0                 # OpenRouter API client
requests>=2.32.5              # HTTP client
rich>=14.2.0                  # Terminal formatting
aster-connector-python>=1.0.0 # AsterDEX API
TA-Lib>=0.4.28                # Technical analysis
typer>=0.12.0                 # CLI framework
```

### 3.3 Database Dependencies
```
sqlalchemy>=2.0.0             # ORM
psycopg2-binary>=2.9.0        # PostgreSQL driver
asyncpg>=0.29.0               # Async PostgreSQL driver
alembic>=1.13.0               # Database migrations
```

### 3.4 Testing Dependencies
```
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
httpx>=0.25.0                 # Async HTTP client for testing
faker>=20.0.0                 # Test data generation
```

### 3.5 Development Dependencies
```
black>=23.0.0                 # Code formatter
ruff>=0.1.0                   # Linter
mypy>=1.7.0                   # Type checker
pre-commit>=3.5.0             # Git hooks
ipython>=8.18.0               # Interactive shell
```

### 3.6 Dependency Management with uv
- **pyproject.toml**: Project metadata, dependencies organized by groups
- **Dependency Groups**:
  - `main`: Core dependencies
  - `dev`: Development tools
  - `test`: Testing tools
- **uv.lock**: Locked versions for reproducible builds

### 3.7 Development Server Startup
```bash
# Development with hot-reload
uvicorn src.app.main:app --host 0.0.0.0 --port 3000 --reload

# Production
uvicorn src.app.main:app --host 0.0.0.0 --port 3000 --workers 4
```

---

## 4. Configuration and Environment Management

### 4.1 .env File Structure
```bash
# Required - AsterDEX
ASTERDEX_API_KEY=your_key
ASTERDEX_API_SECRET=your_secret

# Required - OpenRouter
OPENROUTER_API_KEY=your_key

# Required - Database
DATABASE_URL=postgresql://user:password@postgres:5432/trading_db

# Optional - API Server
API_HOST=0.0.0.0
API_PORT=3000

# Optional - Trading
LLM_MODEL=x-ai/grok-4
ASSETS=BTC,ETH,SOL
INTERVAL=1h
```

### 4.2 Configuration Class Hierarchy
Using Pydantic v2 BaseSettings:
- `BaseConfig`: Common settings
- `DevelopmentConfig`: Debug enabled, verbose logging
- `TestingConfig`: In-memory DB, minimal logging
- `ProductionConfig`: Optimized, error logging only

### 4.3 Environment-Specific Configurations
- **Development**: Hot-reload, debug logs, verbose output
- **Testing**: In-memory SQLite or test PostgreSQL, minimal logs
- **Production**: Optimized, error-only logs, connection pooling

### 4.4 Configurable Parameters
- Database URLs and credentials
- API keys (AsterDEX, OpenRouter)
- Feature flags
- Trading intervals (5m, 1h, 4h, 1d)
- Asset lists
- Leverage limits
- Position size limits

### 4.5 Secrets Management Approach
- All secrets in environment variables
- `.env.local` for local overrides (git-ignored)
- No secrets in code or version control
- Use `.env.example` as template

### 4.6 Multi-Account Configuration
- Account-specific environment variables: `ASTERDEX_API_KEY_account1`
- YAML/JSON config file support for complex setups
- Account isolation at configuration level

---

## 5. Logging System

### 5.1 Logging Framework Selection
**Recommendation**: Python's built-in `logging` module with JSON formatter
- Standard library (no extra dependencies)
- Mature and well-documented
- JSON formatting for structured logs
- Integrates well with container logging

### 5.2 Log Levels and Usage
- **DEBUG**: Detailed information for debugging
- **INFO**: General informational messages
- **WARNING**: Warning messages for potential issues
- **ERROR**: Error messages for failures
- **CRITICAL**: Critical system failures

### 5.3 Log Formatting
```json
{
  "timestamp": "2025-10-23T10:30:00Z",
  "level": "INFO",
  "logger": "app.services.trading",
  "message": "Trade executed",
  "context": {
    "asset": "BTC",
    "action": "buy",
    "amount": 0.5
  }
}
```

### 5.4 Log Output Destinations
- **stdout**: Container logs (for `podman logs`)
- **File**: `logs/app.log` (persistent)
- **Separate Files**:
  - `logs/trading.log` (trading operations)
  - `logs/market_data.log` (market data)
  - `logs/llm.log` (LLM interactions)
  - `logs/errors.log` (errors only)

### 5.5 Log Rotation and Retention
- **Max File Size**: 100MB
- **Backup Count**: 10 files
- **Retention**: 30 days for app logs, 90 days for trading logs
- **Rotation**: Daily or size-based

### 5.6 Logging Configuration Management
- **Config File**: `src/app/core/logging_config.yaml`
- **Environment-Based**: Log levels configurable via env vars
- **Per-Module**: Different log levels for different modules

### 5.7 Sensitive Data Masking
- Mask API keys in logs
- Mask private keys and mnemonics
- Mask passwords and secrets
- Implement sanitization functions in logging module

---

## Implementation Dependencies and Order

### Phase 1: Foundation (No Dependencies)
1. Repository structure setup
2. Configuration management
3. Logging system

### Phase 2: Infrastructure (Depends on Phase 1)
4. Podman development environment
5. Python dependencies and pyproject.toml

### Phase 3: Application (Depends on Phase 1-2)
6. FastAPI application skeleton
7. Database models and migrations
8. API endpoints
9. WebSocket handlers

### Phase 4: Services (Depends on Phase 3)
10. Market data service
11. Decision engine service
12. Trading execution service

### Phase 5: Testing and Deployment (Depends on Phase 4)
13. Unit tests
14. Integration tests
15. Docker/Podman deployment

---

## Key Decisions Requiring Clarification

1. **Frontend Framework**: React, Vue, or Svelte? (Currently planned for future)
2. **Database Backup Strategy**: Cloud storage or local backups?
3. **Monitoring and Alerting**: Prometheus/Grafana or cloud provider?
4. **Log Aggregation**: ELK stack or cloud provider?
5. **CI/CD Pipeline**: GitHub Actions or other?

---

## Success Criteria

- [ ] Repository structure created and documented
- [ ] podman-compose.yml configured and tested
- [ ] pyproject.toml with all dependencies defined
- [ ] Configuration system working with environment variables
- [ ] Logging system configured and tested
- [ ] FastAPI application starts successfully
- [ ] Database connection established
- [ ] All endpoints documented in OpenAPI/Swagger

---

**Next Steps**: Begin Phase 1 implementation with repository structure setup.

