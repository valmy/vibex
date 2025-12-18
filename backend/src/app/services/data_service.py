from typing import Any, List, Optional, Tuple, Type, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.base import BaseModel

T = TypeVar("T", bound=BaseModel)


class DataService:
    """Generic service for data access operations."""

    async def list_with_count(
        self,
        db: AsyncSession,
        model: Type[T],
        skip: int = 0,
        limit: int = 100,
        filters: Optional[dict[str, Any]] = None,
    ) -> Tuple[List[T], int]:
        """
        List items with pagination and total count.

        Args:
            db: Database session
            model: SQLAlchemy model class
            skip: Number of items to skip
            limit: Number of items to return
            filters: Dictionary of filters (field_name: value)

        Returns:
            Tuple of (List of items, total count)
        """
        query = select(model)
        count_query = select(func.count(model.id))

        if filters:
            for key, value in filters.items():
                if hasattr(model, key):
                    query = query.where(getattr(model, key) == value)
                    count_query = count_query.where(getattr(model, key) == value)

        # Get total count
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        # Get items
        result = await db.execute(query.offset(skip).limit(limit))
        items = result.scalars().all()

        return list(items), total


# Singleton instance
data_service = DataService()
