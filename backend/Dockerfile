# Multi-stage build for AI Trading Agent with LLM Decision Engine

# Stage 1: Builder
FROM python:3.13-slim as builder

# Set working directory
WORKDIR /build

# Install system dependencies for TA-Lib and other packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency resolution
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Copy project files (include source so hatchling can build the editable package)
COPY README.md ./
COPY pyproject.toml uv.lock* ./
COPY src/ ./src/

# Create virtual environment and install dependencies using uv
RUN /root/.local/bin/uv sync
RUN /root/.local/bin/uv pip install --no-cache-dir -e .

# Stage 2: Runtime
FROM python:3.13-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/opt/venv/bin:$PATH \
    VIRTUAL_ENV=/opt/venv \
    # LLM Decision Engine specific settings
    LLM_CACHE_DIR=/app/cache \
    LLM_LOG_LEVEL=INFO \
    DECISION_CACHE_TTL=300 \
    CONTEXT_CACHE_TTL=180

# Set working directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /build/.venv /opt/venv

# Copy application code
COPY src/ ./src/

# Create necessary directories
RUN mkdir -p logs data cache \
    && mkdir -p logs/llm logs/decisions logs/strategies \
    && chmod -R 755 logs cache data

# Create non-root user for security
RUN groupadd -r trading && useradd -r -g trading -d /app -s /bin/bash trading \
    && chown -R trading:trading /app

# Switch to non-root user
USER trading

# Enhanced health check for LLM Decision Engine
HEALTHCHECK --interval=30s --timeout=15s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:3000/api/v1/monitoring/health/system || exit 1

# Expose port
EXPOSE 3000

# Run the application with optimized settings
CMD ["/opt/venv/bin/python", "-m", "uvicorn", "src.app.main:app", \
     "--host", "0.0.0.0", "--port", "3000", \
     "--workers", "1", "--loop", "asyncio", \
     "--access-log", "--log-level", "info"]
