"""
Database session management for SQLAlchemy.

Provides engine creation, session factory, and async session support.
"""

from typing import AsyncGenerator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..core.config import config
from ..core.logging import get_logger

logger = get_logger(__name__)


# Synchronous engine (for migrations and sync operations)
def get_sync_engine() -> Engine:
    """Create synchronous SQLAlchemy engine."""
    # Convert async URL to sync URL for migrations
    database_url = config.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

    engine = create_engine(
        database_url,
        echo=config.DATABASE_ECHO,
        pool_size=config.DATABASE_POOL_SIZE,
        max_overflow=config.DATABASE_MAX_OVERFLOW,
        pool_pre_ping=True,  # Test connections before using
    )

    logger.info(f"Created sync engine: {database_url}")
    return engine


# Async session factory - global state
async_engine = None
AsyncSessionLocal = None


def get_async_engine() -> AsyncEngine:
    """
    Get the global async engine instance.

    Returns the cached engine if available, otherwise raises RuntimeError.
    Use init_db() to initialize the engine first.
    """
    global async_engine

    if async_engine is None:
        raise RuntimeError("Database engine not initialized. Call init_db() first.")

    return async_engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """
    Get the global session factory.

    Returns the cached AsyncSessionLocal if available, otherwise raises RuntimeError.
    Use init_db() to initialize the session factory first.
    """
    global AsyncSessionLocal

    if AsyncSessionLocal is None:
        raise RuntimeError("Database session factory not initialized. Call init_db() first.")

    return AsyncSessionLocal


async def _create_async_engine() -> AsyncEngine:
    """Create asynchronous SQLAlchemy engine (internal use only)."""
    # Use asyncpg for async operations
    database_url = config.DATABASE_URL
    if not database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(
        database_url,
        echo=config.DATABASE_ECHO,
        pool_size=config.DATABASE_POOL_SIZE,
        max_overflow=config.DATABASE_MAX_OVERFLOW,
        pool_pre_ping=True,
        pool_recycle=3600,  # Recycle connections after 1 hour
    )

    logger.info(f"Created async engine: {database_url}")
    return engine


async def init_db() -> None:
    """Initialize database engine and session factory."""
    global async_engine, AsyncSessionLocal

    try:
        # Only create engine if not already initialized
        if async_engine is None:
            async_engine = await _create_async_engine()
            AsyncSessionLocal = async_sessionmaker(
                async_engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )
            logger.info("Database engine and session factory initialized")
        else:
            logger.info("Database already initialized, skipping")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        async_engine = None
        AsyncSessionLocal = None
        raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for dependency injection."""
    session_factory = get_session_factory()

    async with session_factory() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def close_db() -> None:
    """Close database engine."""
    global async_engine, AsyncSessionLocal

    if async_engine:
        try:
            await async_engine.dispose()
        except Exception as e:
            logger.warning(f"Error disposing database engine: {e}")
        finally:
            async_engine = None
            AsyncSessionLocal = None
            logger.info("Database engine closed")


# Health check
async def check_db_health() -> bool:
    """Check database connection health."""
    try:
        engine = get_async_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

        return True
    except RuntimeError:
        # Engine not initialized
        return False
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
