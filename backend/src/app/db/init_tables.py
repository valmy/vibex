"""
Initialize database tables using SQLAlchemy models.

This script creates all tables defined in the models.
"""

import asyncio

from sqlalchemy.ext.asyncio import create_async_engine

from ..core.config import config
from ..core.logging import get_logger
from ..models import Base

logger = get_logger(__name__)


async def init_tables():
    """Create all tables in the database."""
    # Convert async URL to sync URL for table creation
    database_url = config.DATABASE_URL
    if not database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(database_url, echo=False)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_tables())
