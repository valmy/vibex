"""
API routes for trading diary management.

Provides endpoints for creating, reading, updating, and deleting diary entries.
"""

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_db
from ...models.diary_entry import DiaryEntry
from ...schemas.diary_entry import DiaryEntryCreate, DiaryEntryUpdate, DiaryEntryRead, DiaryEntryListResponse
from ...core.logging import get_logger
from ...core.exceptions import ResourceNotFoundError, to_http_exception

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/diary", tags=["diary"])


@router.post("", response_model=DiaryEntryRead, status_code=status.HTTP_201_CREATED)
async def create_diary_entry(entry_data: DiaryEntryCreate, db: AsyncSession = Depends(get_db)):
    """Create a new diary entry."""
    try:
        entry = DiaryEntry(**entry_data.model_dump())
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        logger.info(f"Created diary entry for account {entry.account_id}")
        return entry
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating diary entry: {e}")
        raise HTTPException(status_code=500, detail="Failed to create diary entry")


@router.get("", response_model=DiaryEntryListResponse)
async def list_diary_entries(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """List all diary entries with pagination."""
    try:
        # Get total count
        count_result = await db.execute(select(func.count(DiaryEntry.id)))
        total = count_result.scalar()
        
        # Get paginated results
        result = await db.execute(
            select(DiaryEntry).offset(skip).limit(limit)
        )
        entries = result.scalars().all()
        
        return DiaryEntryListResponse(items=entries, total=total)
    except Exception as e:
        logger.error(f"Error listing diary entries: {e}")
        raise HTTPException(status_code=500, detail="Failed to list diary entries")


@router.get("/{entry_id}", response_model=DiaryEntryRead)
async def get_diary_entry(entry_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific diary entry by ID."""
    try:
        result = await db.execute(select(DiaryEntry).where(DiaryEntry.id == entry_id))
        entry = result.scalar_one_or_none()
        
        if not entry:
            raise ResourceNotFoundError("DiaryEntry", entry_id)
        
        return entry
    except ResourceNotFoundError as e:
        raise to_http_exception(e)
    except Exception as e:
        logger.error(f"Error getting diary entry: {e}")
        raise HTTPException(status_code=500, detail="Failed to get diary entry")


@router.put("/{entry_id}", response_model=DiaryEntryRead)
async def update_diary_entry(
    entry_id: int,
    entry_data: DiaryEntryUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a diary entry."""
    try:
        result = await db.execute(select(DiaryEntry).where(DiaryEntry.id == entry_id))
        entry = result.scalar_one_or_none()
        
        if not entry:
            raise ResourceNotFoundError("DiaryEntry", entry_id)
        
        # Update fields
        update_data = entry_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(entry, field, value)
        
        await db.commit()
        await db.refresh(entry)
        logger.info(f"Updated diary entry {entry_id}")
        return entry
    except ResourceNotFoundError as e:
        raise to_http_exception(e)
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating diary entry: {e}")
        raise HTTPException(status_code=500, detail="Failed to update diary entry")


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_diary_entry(entry_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a diary entry."""
    try:
        result = await db.execute(select(DiaryEntry).where(DiaryEntry.id == entry_id))
        entry = result.scalar_one_or_none()
        
        if not entry:
            raise ResourceNotFoundError("DiaryEntry", entry_id)
        
        await db.delete(entry)
        await db.commit()
        logger.info(f"Deleted diary entry {entry_id}")
    except ResourceNotFoundError as e:
        raise to_http_exception(e)
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting diary entry: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete diary entry")

