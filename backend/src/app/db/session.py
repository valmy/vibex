"""
Database session management for SQLAlchemy.

Provides engine creation, session factory, and async session support.
"""

from typing import AsyncGenerator

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..core.config import config
from ..core.logging import get_logger

logger = get_logger(__name__)


# Synchronous engine (for migrations and sync operations)
def get_sync_engine():
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


# Asynchronous engine (for FastAPI)
async def get_async_engine():
    """Create asynchronous SQLAlchemy engine."""
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


# Async session factory
async_engine = None
AsyncSessionLocal = None


async def init_db():
    """Initialize database engine and session factory."""
    global async_engine, AsyncSessionLocal

    async_engine = await get_async_engine()
    AsyncSessionLocal = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    logger.info("Database engine and session factory initialized")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for dependency injection."""
    if AsyncSessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def close_db():
    """Close database engine."""
    global async_engine

    if async_engine:
        await async_engine.dispose()
        logger.info("Database engine closed")


# Health check
async def check_db_health() -> bool:
    """Check database connection health."""
    try:
        if async_engine is None:
            return False

        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
