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

# Remove volumes (destroys all data - use for fresh start)
cd backend && podman-compose down -v
```

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

## Database Schema Management

### Overview

The database schema is managed using two components:

1. **`backend/init-db.sql`** - Single source of truth for initial schema. Executed automatically on first container start via PostgreSQL's entrypoint.
2. **Alembic migrations** - Used for tracking schema versions and applying incremental changes.

The current baseline migration is `bfb15195438f`.

### Fresh Installation Setup

After starting containers for the first time (or after `podman-compose down -v`):

```bash
# Wait for database to initialize
sleep 15

# Stamp the database with the baseline Alembic revision
# This marks the database as current without running migrations
# (init-db.sql already created the schema)
cd backend && ENVIRONMENT=testing uv run alembic stamp head
```

**Important**: Use `ENVIRONMENT=testing` when running Alembic commands from the host machine (uses `localhost` instead of container hostname `postgres`).

### Common Alembic Commands

```bash
# Check current migration version
cd backend && ENVIRONMENT=testing uv run alembic current

# View migration history
cd backend && ENVIRONMENT=testing uv run alembic history

# Apply pending migrations (for existing databases)
cd backend && ENVIRONMENT=testing uv run alembic upgrade head

# Rollback one migration
cd backend && ENVIRONMENT=testing uv run alembic downgrade -1
```

### Making Schema Changes

Follow this workflow for all schema modifications:

1. **Modify SQLAlchemy models** in `backend/src/app/models/`

2. **Generate migration**:

   ```bash
   cd backend && ENVIRONMENT=testing uv run alembic revision -m "description" --autogenerate
   ```

3. **Review the generated migration** in `backend/alembic/versions/`

4. **Apply the migration**:

   ```bash
   cd backend && ENVIRONMENT=testing uv run alembic upgrade head
   ```

5. **Update `backend/init-db.sql`** to include the new columns/tables (keeps fresh installations in sync)

### Important Notes

- **TimescaleDB hypertable** for `market_data` is managed in `init-db.sql`, not Alembic
- **Never manually edit** the `alembic_version` table
- See `docs/database-baseline-reset.md` for detailed troubleshooting

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

## Code Quality & Maintenance Rules

### 1. Test Fidelity & Refactoring

- **Signature Sync**: When modifying function/method signatures (renaming arguments, changing order, adding async), you **MUST** grep the entire `tests/` directory to update all call sites immediately. Do not rely on CI to catch this.
- **Mocking Pydantic**: When mocking dependencies that return data used in Pydantic models, ensure the Mock object returns correct primitive types (int, float, datetime), not other Mocks. Pydantic validation is strict and will fail on MagicMocks.

### 2. SQLAlchemy Best Practices

- **Boolean Expressions**: Avoid `column == True` or `column == False` in queries. Ruff and proper SQL generation prefer using the column directly (e.g., `.where(Model.is_active)`) or `.is_(True)`.

### 3. Database Session Patterns (Dual Pattern Architecture)

The codebase uses **two distinct patterns** for database session management. Use the correct pattern based on context:

#### Pattern A: Direct Session Injection (API/CRUD Operations)

Use when serving HTTP requests via FastAPI. Session is injected via `Depends(get_db)`.

```python
# In API routes
async def create_account(
    db: Annotated[AsyncSession, Depends(get_db)],
    data: AccountCreate,
) -> Account:
    ...

# In services that receive session as parameter
class AccountService:
    async def create_account(self, db: AsyncSession, user_id: int, data: AccountCreate):
        db.add(account)
        await db.commit()
```

**When to use:**

- API route handlers
- CRUD services called from API routes
- When multiple service calls need to share a transaction

**Characteristics:**

- Session scoped to HTTP request lifecycle
- Caller controls transaction boundaries
- Multiple operations can share one session/transaction

---

#### Pattern B: Session Factory Injection (Background/Scheduler Processes)

Use for background jobs, schedulers, and LLM decision pipelines. Service receives factory and creates sessions internally.

```python
class DecisionRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    async def save_decision(self, ...) -> Decision:
        async with self.session_factory() as session:
            session.add(decision)
            await session.commit()
            return decision
```

**When to use:**

- Scheduler/cron jobs
- Background tasks
- LLM decision engine pipeline
- Long-running processes

**Characteristics:**

- Each operation creates its own session
- Self-contained transaction per method
- No external request context needed
- Better retry resilience (fresh session on retry)

---

#### Quick Reference

| Context | Pattern | Session Source |
|---------|---------|----------------|
| API routes | Direct injection | `Depends(get_db)` |
| CRUD services | Direct injection | Passed from route |
| Scheduler jobs | Factory | `get_session_factory()` |
| LLM services | Factory | Constructor injection |
| Background tasks | Factory | `get_session_factory()` |

### 4. Regex in Python

- **Raw Strings vs. F-Strings**: Be extremely careful with braces `{}`.
  - In `r"pattern"` (raw string): `{` is a literal brace (unless part of a quantifier `{n,m}`).
  - In `f"pattern"` (f-string): `{` starts an interpolation. You must use `{{` for a literal brace.
  - **Rule**: Prefer raw strings `r""` for regex. Do not mix f-strings with regex unless strictly necessary for dynamic patterns. Verify regex logic in isolation if complex nesting is involved.

### 5. Verification Standard

Before considering a task complete, you must run the full verification chain:

1. `uv run mypy src/` (Type Safety)
2. `uv run ruff format .` (Formatting)
3. `uv run ruff check .` (Linting)
4. `uv run pytest tests/unit` (Logic)
5. `uv run pytest tests/integration` (Component Interaction)
6. `uv run pytest tests/e2e` (End-to-End)

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
