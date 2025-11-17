# Development Guidelines

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
# Format code
cd backend && uv run ruff format .

# Run linter
cd backend && uv run ruff check .

# Auto-fix linting issues
cd backend && uv run ruff check . --fix

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
cd backend && podman-compose up -d

# View logs
cd backend && podman-compose logs backend

# Stop services
cd backend && podman-compose down

# Remove volumes
cd backend && podman-compose down -v

# Initial database will be set by backend/init-db.sql
# Run migrations
cd backend && ENVINRONMENT=testing uv run alembic upgrade head

### With podman-compose (Recommended for Development)

This method uses the `compose.override.yml` to provide a hot-reloading development server while managing all services (backend, database, cache) in containers.

```bash
# Copy the example override file for local development
cd backend && cp compose.override.yml.example compose.override.yml

# Start all services in the background (--build is required if there are package changes)
cd backend && podman-compose up -d --build

# or for normal code changes:
cd backend && podman-compose up -d

# View logs
cd backend && podman-compose logs -f backend

# Stop services
cd backend && podman-compose down
```

## Code Style Guidelines

### Imports
- Use absolute imports when possible
- Group imports in order: standard library, third-party, local
- Use explicit imports (no `from module import *`)
- Place imports at the top of the file

### Formatting
- Line length: 100 characters (Ruff)
- Indentation: 4 spaces (no tabs)
- Use Ruff for automatic formatting
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

### ast-grep vs ripgrep (quick guidance)

**Use `ast-grep` when structure matters.** It parses code and matches AST nodes, so results ignore comments/strings, understand syntax, and can **safely rewrite** code.

- Refactors/codemods: rename APIs, change import forms, rewrite call sites or variable kinds.
- Policy checks: enforce patterns across a repo (`scan` with rules + `test`).
- Editor/automation: LSP mode; `--json` output for tooling.

**Use `ripgrep` when text is enough.** It's the fastest way to grep literals/regex across files.

- Recon: find strings, TODOs, log lines, config values, or non‑code assets.
- Pre-filter: narrow candidate files before a precise pass.

#### Rule of thumb

- Need correctness over speed, or you'll **apply changes** → start with `ast-grep`.
- Need raw speed or you're just **hunting text** → start with `rg`.
- Often combine: `rg` to shortlist files, then `ast-grep` to match/modify with precision.

#### Snippets

Find structured code (ignores comments/strings):

```bash
ast-grep run -l TypeScript -p 'import $X from "$P"'
```

Codemod (only real `var` declarations become `let`):

```bash
ast-grep run -l JavaScript -p 'var $A = $B' -r 'let $A = $B' -U
```

Quick textual hunt:

```bash
rg -n 'console\.log\(' -t js
```

Combine speed + precision:

```bash
rg -l -t ts 'useQuery\(' | xargs ast-grep run -l TypeScript -p 'useQuery($A)' -r 'useSuspenseQuery($A)' -U
```

#### Mental model

- Unit of match: `ast-grep` = node; `rg` = line.

- False positives: `ast-grep` low; `rg` depends on your regex.
- Rewrites: `ast-grep` first-class; `rg` requires ad‑hoc sed/awk and risks collateral edits.
