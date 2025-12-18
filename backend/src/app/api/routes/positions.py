"""
API routes for position management.

Provides endpoints for creating, reading, updating, and deleting trading positions.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.exceptions import ResourceNotFoundError, to_http_exception
from ...core.logging import get_logger
from ...core.security import get_current_user
from ...db.session import get_db
from ...models import User
from ...models.position import Position
from ...schemas.position import PositionCreate, PositionListResponse, PositionRead, PositionUpdate

from ...services import data_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/positions", tags=["Trading"])


@router.post("", response_model=PositionRead, status_code=status.HTTP_201_CREATED)
async def create_position(
    position_data: PositionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PositionRead:
    """Create a new position."""
    try:
        position = Position(**position_data.model_dump())
        db.add(position)
        await db.commit()
        await db.refresh(position)
        logger.info(f"Created position for account {position.account_id}")
        return PositionRead.model_validate(position)
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating position: {e}")
        raise HTTPException(status_code=500, detail="Failed to create position") from e


@router.get("", response_model=PositionListResponse)
async def list_positions(
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: Annotated[int, Query()] = 0,
    limit: Annotated[int, Query()] = 100,
) -> PositionListResponse:
    """List all positions with pagination."""
    try:
        positions, total = await data_service.list_with_count(db, Position, skip, limit)

        return PositionListResponse(
            items=[PositionRead.model_validate(p) for p in positions],
            total=total,
        )
    except Exception as e:
        logger.error(f"Error listing positions: {e}")
        raise HTTPException(status_code=500, detail="Failed to list positions") from e


@router.get("/{position_id}", response_model=PositionRead)
async def get_position(
    position_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> PositionRead:
    """Get a specific position by ID."""
    try:
        result = await db.execute(select(Position).where(Position.id == position_id))
        position = result.scalar_one_or_none()

        if not position:
            raise ResourceNotFoundError("Position", position_id)

        return PositionRead.model_validate(position)
    except ResourceNotFoundError as e:
        raise to_http_exception(e) from e
    except Exception as e:
        logger.error(f"Error getting position: {e}")
        raise HTTPException(status_code=500, detail="Failed to get position") from e


@router.put("/{position_id}", response_model=PositionRead)
async def update_position(
    position_id: int,
    position_data: PositionUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PositionRead:
    """Update a position."""
    try:
        result = await db.execute(select(Position).where(Position.id == position_id))
        position = result.scalar_one_or_none()

        if not position:
            raise ResourceNotFoundError("Position", position_id)

        # Update fields
        update_data = position_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(position, field, value)

        await db.commit()
        await db.refresh(position)
        logger.info(f"Updated position {position_id}")
        return PositionRead.model_validate(position)
    except ResourceNotFoundError as e:
        raise to_http_exception(e) from e
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating position: {e}")
        raise HTTPException(status_code=500, detail="Failed to update position") from e


@router.delete("/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_position(
    position_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete a position."""
    try:
        result = await db.execute(select(Position).where(Position.id == position_id))
        position = result.scalar_one_or_none()

        if not position:
            raise ResourceNotFoundError("Position", position_id)

        await db.delete(position)
        await db.commit()
        logger.info(f"Deleted position {position_id}")
    except ResourceNotFoundError as e:
        raise to_http_exception(e) from e
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting position: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete position") from e
