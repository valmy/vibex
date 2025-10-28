# CRUSH Development Guidelines

## Build/Lint/Test Commands

### Development Setup
```bash
# Install dependencies (always use uv for better performance)
uv pip install -e backend/
uv pip install -e backend/[dev,test]
```

### Running Tests
```bash
# Run all tests
cd backend && uv run pytest

# Run a single test file
cd backend && uv run pytest tests/unit/test_config_manager.py

# Run a specific test function
cd backend && uv run pytest tests/unit/test_config_manager.py::test_manager_singleton

# Run with coverage
cd backend && uv run pytest --cov=src/app

# Run integration tests
cd backend && uv run pytest tests/integration/
```

### Linting and Formatting
```bash
# Run linter
cd backend && uv run ruff check .

# Auto-fix linting issues
cd backend && uv run ruff check . --fix

# Format code
cd backend && uv run black .

# Type checking
cd backend && uv run mypy src/
```

### Running the Application

### Docker/Podman

#### Build Image

```bash
cd backend && podman build -t trading-agent:latest .
```

#### Run Container

```bash
cd backend && podman run -p 3000:3000 --env-file .env trading-agent:latest
```

#### Using Podman Compose

This is to run the database and backend app

```bash
# Start services
cd backend && uv run podman-compose up -d

# View logs
cd backend && uv run podman-compose logs -f backend

# Stop services
cd backend && uv run podman-compose down

# Remove volumes
cd backend && uv run podman-compose down -v

### With python venv

```bash
# Start the development server
cd backend && uv run python -m app.main

# Run with specific environment
cd backend && ENVIRONMENT=production uv run python -m app.main
```

## Code Style Guidelines

### Imports
- Use absolute imports when possible
- Group imports in order: standard library, third-party, local
- Use explicit imports (no `from module import *`)
- Place imports at the top of the file

### Formatting
- Line length: 100 characters (Black + Ruff)
- Indentation: 4 spaces (no tabs)
- Use Black for automatic formatting
- Use Ruff for linting

### Types and Naming
- Use type hints for all function parameters and return values
- Use descriptive variable names in snake_case
- Class names in PascalCase
- Constants in UPPER_SNAKE_CASE
- Private methods prefixed with underscore

### Error Handling
- Create custom exception classes for specific error scenarios
- Inherit from appropriate base exception classes
- Always include meaningful error messages
- Log errors appropriately but don't expose sensitive information
- Handle exceptions at the appropriate level

### Documentation
- Use docstrings for all public classes and functions
- Follow Google-style docstrings with Args/Returns sections
- Include type information in docstrings
- Keep comments focused on why, not what

### Testing
- Use pytest for testing
- Write both unit and integration tests
- Use fixtures for test setup
- Mock external dependencies
- Test edge cases and error conditions
- Use async tests for async code (`@pytest.mark.asyncio`)
