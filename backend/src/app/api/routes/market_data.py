"""
API routes for market data management.

Provides endpoints for reading and managing market data (OHLCV).
"""

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_db
from ...models.market_data import MarketData
from ...schemas.market_data import MarketDataRead, MarketDataListResponse
from ...core.logging import get_logger
from ...core.exceptions import ResourceNotFoundError, to_http_exception

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/market-data", tags=["market-data"])


@router.get("", response_model=MarketDataListResponse)
async def list_market_data(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """List all market data with pagination."""
    try:
        # Get total count
        count_result = await db.execute(select(func.count(MarketData.id)))
        total = count_result.scalar()
        
        # Get paginated results
        result = await db.execute(
            select(MarketData).offset(skip).limit(limit)
        )
        data = result.scalars().all()
        
        return MarketDataListResponse(items=data, total=total)
    except Exception as e:
        logger.error(f"Error listing market data: {e}")
        raise HTTPException(status_code=500, detail="Failed to list market data")


@router.get("/{data_id}", response_model=MarketDataRead)
async def get_market_data(data_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific market data entry by ID."""
    try:
        result = await db.execute(select(MarketData).where(MarketData.id == data_id))
        data = result.scalar_one_or_none()
        
        if not data:
            raise ResourceNotFoundError("MarketData", data_id)
        
        return data
    except ResourceNotFoundError as e:
        raise to_http_exception(e)
    except Exception as e:
        logger.error(f"Error getting market data: {e}")
        raise HTTPException(status_code=500, detail="Failed to get market data")

