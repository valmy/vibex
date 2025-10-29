# Project Structure

## Repository Layout

```
vibex/
├── backend/                    # Python FastAPI application
├── frontend/                   # Frontend application (placeholder)
├── docs/                       # Documentation and specifications
├── scripts/                    # Utility scripts
└── .kiro/                      # Kiro IDE configuration
```

## Backend Structure (`backend/src/app/`)

### Core Architecture Layers

```
src/app/
├── main.py                     # FastAPI application entry point
├── core/                       # Application core (config, logging, constants)
├── models/                     # SQLAlchemy ORM models
├── schemas/                    # Pydantic data validation schemas
├── services/                   # Business logic layer
├── api/                        # API routes and WebSocket handlers
├── db/                         # Database session and migrations
└── utils/                      # Utility functions
```

### Detailed Structure

#### Core (`core/`)

- `config.py` - Environment-based configuration management
- `config_manager.py` - Dynamic configuration management with hot-reload
- `config_validator.py` - Configuration validation rules
- `config_cache.py` - Configuration caching with TTL
- `config_reloader.py` - File watching and configuration reloading
- `config_exceptions.py` - Configuration-specific exceptions
- `logging.py` - Structured JSON logging setup
- `exceptions.py` - Custom exception classes
- `constants.py` - Application constants

#### Models (`models/`)

- `base.py` - Base model with common fields (id, timestamps)
- Domain models: `account.py`, `position.py`, `order.py`, `trade.py`
- Time-series: `market_data.py`, `performance_metric.py`
- User data: `diary_entry.py`

#### Schemas (`schemas/`)

- `base.py` - Base Pydantic schemas
- Domain schemas matching models
- `trading_decision.py` - LLM decision structures
- `context.py` - Trading context schemas

#### Services (`services/`)

- `llm_service.py` - LLM integration and decision making
- `context_builder.py` - Trading context assembly
- `circuit_breaker.py` - Fault tolerance patterns
- `ab_testing.py` - A/B testing framework
- `llm_metrics.py` - LLM performance tracking
- `market_data_service.py` - Market data collection with Aster integration
- `trading/` - Trading operations and execution
- `market_data/` - Market data collection and processing
- `decision_engine/` - LLM decision making
- `execution/` - Order execution
- `account/` - Account management
- `reconciliation/` - State reconciliation
- `technical_analysis/` - Technical indicators and analysis

#### API (`api/`)

- `routes/` - REST API endpoints organized by domain
- `websockets/` - WebSocket handlers for real-time data

## Configuration Structure

### Environment Files

- `.env.example` - Template for environment variables
- `.env` - Local environment configuration (not in git)

### Multi-Environment Support

- `DevelopmentConfig` - Debug enabled, verbose logging
- `TestingConfig` - In-memory database, minimal logging
- `ProductionConfig` - Optimized for performance and security

## Database Organization

### TimescaleDB Hypertables

- `market_data` - Time-series market data with automatic partitioning
- Regular tables for trading entities and user data

### Migration Management

- `backend/src/app/db/migrations/` - Alembic migration files
- `init-db.sql` - Initial database setup script

## Testing Structure

```
tests/
├── unit/                       # Unit tests for individual components
├── integration/                # Integration tests for service interactions
└── __init__.py
```

## Logging Structure

```
logs/
├── app.log                     # General application logs
├── trading.log                 # Trading-specific logs
├── market_data.log             # Market data collection logs
├── llm.log                     # LLM interaction logs
└── errors.log                  # Error-only logs
```

## Naming Conventions

### Files and Directories

- Snake_case for Python files: `market_data_service.py`
- Lowercase for directories: `market_data/`
- Descriptive names reflecting purpose

### Code Conventions

- Classes: PascalCase (`MarketDataService`)
- Functions/variables: snake_case (`get_market_data`)
- Constants: UPPER_SNAKE_CASE (`MAX_POSITION_SIZE`)
- Private methods: leading underscore (`_validate_data`)

### Database Conventions

- Table names: snake_case (`market_data`, `trading_decisions`)
- Column names: snake_case (`created_at`, `symbol_name`)
- Foreign keys: `{table}_id` (`account_id`, `position_id`)

## Import Organization

### Import Order (enforced by Ruff)

1. Standard library imports
2. Third-party imports
3. Local application imports

### Relative Imports

- Use relative imports within the same package
- Absolute imports from `src.app` for cross-package references

## Error Handling Patterns

### Service Layer

- Custom exceptions in `core/exceptions.py`
- Service-specific exceptions (e.g., `llm_exceptions.py`)
- Structured error responses with context

### API Layer

- FastAPI exception handlers in `main.py`
- Consistent error response format
- Proper HTTP status codes##
Development Workflow (CRUSH)

### File Organization Principles

- **Domain-Driven**: Organize by business domain (trading, market_data, account)
- **Layer Separation**: Clear separation between API, services, models, and core
- **Single Responsibility**: Each file has a clear, single purpose
- **Dependency Direction**: Dependencies flow inward (API → Services → Models → Core)

### Configuration Management

- **Environment-Based**: Different configs for development/testing/production
- **Hot-Reloadable**: Configuration changes without restart (development mode)
- **Validated**: All configuration validated at startup and reload
- **Cached**: Frequently accessed config values cached with TTL
- **Multi-Account**: Support for multiple trading accounts with separate configs

### Service Architecture Patterns

- **Dependency Injection**: Services injected via constructor or factory functions
- **Circuit Breaker**: Fault tolerance for external API calls
- **A/B Testing**: Built-in experimentation framework
- **Metrics Tracking**: Performance and usage metrics for all services
- **Async-First**: All I/O operations use async/await patterns

### Testing Organization

```
tests/
├── unit/                       # Unit tests for individual components
│   ├── test_config_manager.py  # Configuration system tests
│   ├── test_llm_service.py     # LLM service tests
│   └── test_market_data.py     # Market data tests
├── integration/                # Integration tests for service interactions
│   ├── test_trading_flow.py    # End-to-end trading tests
│   └── test_config_integration.py # Configuration integration tests
└── fixtures/                   # Test data and fixtures
```

### Error Handling Strategy

- **Layered Exceptions**: Domain-specific exceptions inherit from base classes
- **Context Preservation**: Exceptions include relevant context and error codes
- **Graceful Degradation**: Services handle failures gracefully with fallbacks
- **Audit Trail**: All errors logged with structured context for debugging

### API Design Patterns

- **RESTful Endpoints**: Standard HTTP methods and status codes
- **WebSocket Streams**: Real-time data via WebSocket connections
- **Consistent Responses**: Standardized response format across all endpoints
- **Error Responses**: Consistent error response structure with error codes
- **OpenAPI Documentation**: Auto-generated API documentation via FastAPI

### Database Design Patterns

- **TimescaleDB Hypertables**: Time-series data automatically partitioned
- **Audit Trails**: Track changes to critical entities (positions, orders)
- **Soft Deletes**: Mark records as deleted rather than physical deletion
- **Connection Pooling**: Efficient database connection management
- **Migration Management**: Version-controlled schema changes via Alembic
