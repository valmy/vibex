# Technology Stack

## Core Backend
*   **Language**: Python 3.13 (supports 3.12+)
*   **Framework**: FastAPI (Asynchronous REST API and WebSockets)
*   **Task Management**: Built-in asyncio for concurrent market data processing and trade execution.

## Data Persistence & Caching
*   **Primary Database**: PostgreSQL 17
*   **Extensions**: TimescaleDB for optimized time-series market data storage.
*   **Caching & Sessions**: Redis (user session management and data caching).
*   **ORM**: SQLAlchemy 2.0 (Async extension)
*   **Migrations**: Alembic

## AI & Trading
*   **LLM Integration**: OpenAI SDK via OpenRouter (multi-model support).
*   **Trading Platform**: AsterDEX via `aster-connector-python`.
*   **Technical Analysis**: TA-Lib (C-based performance), NumPy.

## Quality & Infrastructure
*   **Package Manager**: uv
*   **Containerization**: Docker / Podman (with podman-compose)
*   **Code Quality**: Ruff (Linting & Formatting), MyPy (Static Type Checking)
*   **Testing**: Pytest (with pytest-asyncio and pytest-cov)
