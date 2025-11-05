# AI Trading Agent - Backend

LLM-powered cryptocurrency trading agent for AsterDEX.

## Quick Start

### Prerequisites

- Python 3.13+
- Podman or Docker
- uv (Python package manager)

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd backend
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

3. **Install dependencies**
   ```bash
   uv sync
   ```

4. **Start development environment**
   ```bash
   # Copy the example override file for local development
   cp podman-compose.override.yml.example podman-compose.override.yml
   # This single command starts the database, cache, and the backend service with hot-reloading.
   podman-compose up -d --build
   ```

5. **Run migrations**
   ```bash
   uv run alembic upgrade head
   ```

The API will be available at `http://localhost:3000`

## Project Structure

```
backend/
├── src/
│   └── app/
│       ├── core/              # Configuration, logging, constants
│       ├── services/          # Business logic services
│       ├── models/            # Database models
│       ├── schemas/           # Pydantic schemas
│       ├── api/
│       │   ├── routes/        # API endpoints
│       │   └── websockets/    # WebSocket handlers
│       ├── db/                # Database setup and migrations
│       ├── utils/             # Utility functions
│       └── main.py            # FastAPI app entry point
├── tests/
│   ├── unit/                  # Unit tests
│   └── integration/           # Integration tests
├── logs/                      # Application logs
├── data/                      # Data storage
├── pyproject.toml             # Project configuration
├── Dockerfile                 # Container image
├── podman-compose.yml         # Container orchestration
└── README.md                  # This file
```

## Configuration

### Environment Variables

See `.env.example` for all available configuration options.

**Required:**
- `ASTERDEX_API_KEY` - AsterDEX API key
- `ASTERDEX_API_SECRET` - AsterDEX API secret
- `OPENROUTER_API_KEY` - OpenRouter API key

**Optional:**
- `ENVIRONMENT` - Environment (development, testing, production)
- `DEBUG` - Debug mode (true/false)
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `LLM_MODEL` - LLM model to use

### Configuration Classes

Configuration is managed through Pydantic settings classes:

- `BaseConfig` - Base configuration for all environments
- `DevelopmentConfig` - Development-specific settings
- `TestingConfig` - Testing-specific settings
- `ProductionConfig` - Production-specific settings

## Development

### Install Development Dependencies

```bash
uv sync --all-extras
```

### Code Quality

```bash
# Format code
uv run black src tests

# Lint code
uv run ruff check src tests

# Type checking
uv run mypy src

# Run all checks
uv run pre-commit run --all-files
```

### Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_config.py

# Run with verbose output
uv run pytest -v
```

## API Documentation

Once the server is running, visit:

- **Swagger UI**: http://localhost:3000/docs
- **ReDoc**: http://localhost:3000/redoc
- **OpenAPI JSON**: http://localhost:3000/openapi.json

## Logging

Logs are written to:

- **Console**: stdout (all levels)
- **Files**: `logs/` directory
  - `app.log` - General application logs
  - `trading.log` - Trading-specific logs
  - `market_data.log` - Market data logs
  - `llm.log` - LLM interaction logs
  - `errors.log` - Error logs

Log format is JSON by default for structured logging.

## Database

### PostgreSQL with TimescaleDB

The application uses **PostgreSQL 16 with TimescaleDB extension** for optimized time-series data storage and querying.

**Features:**
- **Hypertables**: Market data is stored in a TimescaleDB hypertable for automatic partitioning and compression
- **Time-series Optimization**: Automatic chunking and compression of historical data
- **Fast Queries**: Optimized queries for time-range selections and aggregations
- **Continuous Aggregates**: Pre-computed aggregations for performance (future enhancement)

**Connection:**
```
postgresql://trading_user:trading_password@postgres:5432/trading_db
```

**Docker Image:**
```
docker.io/timescale/timescaledb:latest-pg17
```

**Hypertable Configuration:**
- `market_data` table is automatically converted to a hypertable on initialization
- Time column: `time` (TIMESTAMP)
- Space column: `symbol` (VARCHAR)

### Migrations

```bash
# Create new migration
uv run alembic revision --autogenerate -m "Description"

# Apply migrations
uv run alembic upgrade head

# Rollback migration
uv run alembic downgrade -1
```

## Docker/Podman

### Build Image

```bash
podman build -t trading-agent:latest .
```

### Run Container

```bash
podman run -p 3000:3000 --env-file .env trading-agent:latest
```

### Using Podman Compose

```bash
# Start services
podman-compose up -d

# View logs
podman-compose logs -f backend

# Stop services
podman-compose down

# Remove volumes
podman-compose down -v
```

## Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL is running
podman-compose ps

# Check logs
podman-compose logs postgres

# Restart PostgreSQL
podman-compose restart postgres
```

### Port Already in Use

```bash
# Find process using port 3000
lsof -i :3000

# Kill process
kill -9 <PID>
```

### Module Import Errors

```bash
# Reinstall dependencies
uv sync --force

# Clear Python cache
find . -type d -name __pycache__ -exec rm -r {} +
find . -type f -name "*.pyc" -delete
```

## Performance Optimization

- Connection pooling is configured in `core/config.py`
- Database queries use async/await for non-blocking I/O
- WebSocket connections for real-time updates
- Caching strategies for market data

## Security

- API keys are stored in environment variables only
- Sensitive data is masked in logs
- CORS is configured for allowed origins
- Database credentials are not hardcoded

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests and code quality checks
4. Submit a pull request

## License

MIT License - See LICENSE file for details

## Support

For issues and questions, please open an issue on GitHub.

