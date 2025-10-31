# general.md

General guidelines

## Guidelines

Based on the AGENTS.md file, here are the workspace rules for KiloCode to follow when working in this project:

### Development Setup and Dependencies
- Always use `uv` for dependency management to ensure better performance.
- Install dependencies with: `uv pip install -e backend/` and `uv pip install -e backend/[dev,test]`.

### Testing
- Use pytest for all testing.
- Run all tests: `cd backend && uv run pytest`.
- Run specific tests: `cd backend && uv run pytest tests/unit/test_config_manager.py` or `cd backend && uv run pytest tests/unit/test_config_manager.py::test_manager_singleton`.
- Run with coverage: `cd backend && uv run pytest --cov=src/app`.
- Run integration tests: `cd backend && uv run pytest tests/integration/`.
- Write both unit and integration tests, using fixtures for setup, mocking external dependencies, testing edge cases and error conditions, and `@pytest.mark.asyncio` for async code.

### Linting and Formatting
- Use Ruff for linting: `cd backend && uv run ruff check .`.
- Auto-fix linting issues: `cd backend && uv run ruff check . --fix`.
- Use Black for formatting: `cd backend && uv run black .`.
- Perform type checking with mypy: `cd backend && uv run mypy src/`.
- Enforce line length of 100 characters, 4-space indentation (no tabs).

### Running the Application
- For Docker/Podman: Build with `cd backend && podman build -t trading-agent:latest .`, run with `cd backend && podman run -p 3000:3000 --env-file .env trading-agent:latest`.
- For Podman Compose: Use `cd backend && uv run podman-compose up -d` to start, `cd backend && uv run podman-compose logs -f backend` to view logs, `cd backend && uv run podman-compose down` to stop, and `cd backend && uv run podman-compose down -v` to remove volumes.
- For Python venv: Start server with `cd backend && uv run python -m app.main`, or with environment: `cd backend && ENVIRONMENT=production uv run python -m app.main`.

### Code Style Guidelines
- **Imports**: Use absolute imports when possible, group in order (standard library, third-party, local), explicit imports only, placed at top of file.
- **Types and Naming**: Use type hints for all parameters and returns, descriptive snake_case variables, PascalCase classes, UPPER_SNAKE_CASE constants, underscore-prefixed private methods.
- **Error Handling**: Create custom exceptions inheriting from appropriate bases, include meaningful messages, log errors without exposing sensitive info, handle at appropriate levels.
- **Documentation**: Use Google-style docstrings for public classes/functions with Args/Returns, include type info, focus comments on "why" not "what".