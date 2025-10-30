"""
API routes for market data management.

Provides endpoints for reading and managing market data (OHLCV).
Integrates with MarketDataService for real-time data fetching and storage.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.exceptions import ResourceNotFoundError, to_http_exception
from ...core.logging import get_logger
from ...db.session import get_db
from ...models.market_data import MarketData
from ...schemas.market_data import MarketDataListResponse, MarketDataRead
from ...services import get_market_data_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/market-data", tags=["Market Data"])


@router.get("", response_model=MarketDataListResponse)
async def list_market_data(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """List all market data with pagination."""
    try:
        # Get total count
        count_result = await db.execute(select(func.count(MarketData.id)))
        total = count_result.scalar()

        # Get paginated results
        result = await db.execute(select(MarketData).offset(skip).limit(limit))
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


@router.get("/symbol/{symbol}", response_model=MarketDataListResponse)
async def get_market_data_by_symbol(
    symbol: str,
    interval: str = Query("1h", description="Candlestick interval"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records"),
    db: AsyncSession = Depends(get_db),
):
    """Get market data for a specific symbol."""
    try:
        result = await db.execute(
            select(MarketData)
            .where(and_(MarketData.symbol == symbol, MarketData.interval == interval))
            .order_by(MarketData.time.desc())
            .limit(limit)
        )
        data = result.scalars().all()

        return MarketDataListResponse(items=list(reversed(data)), total=len(data))
    except Exception as e:
        logger.error(f"Error getting market data for {symbol}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get market data")


@router.post("/sync/{symbol}")
async def sync_market_data(symbol: str, db: AsyncSession = Depends(get_db)):
    """Sync market data from Aster DEX for a specific symbol."""
    try:
        service = get_market_data_service()
        results = await service.sync_market_data(db, symbol=symbol)

        return {
            "status": "success",
            "message": f"Synced market data for {symbol}",
            "results": results,
        }
    except Exception as e:
        logger.error(f"Error syncing market data for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to sync market data: {str(e)}")


@router.post("/sync-all")
async def sync_all_market_data(db: AsyncSession = Depends(get_db)):
    """Sync market data from Aster DEX for all configured assets."""
    try:
        service = get_market_data_service()
        results = await service.sync_market_data(db)

        return {
            "status": "success",
            "message": "Synced market data for all assets",
            "results": results,
        }
    except Exception as e:
        logger.error(f"Error syncing all market data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to sync market data: {str(e)}")


@router.get("/range/{symbol}")
async def get_market_data_range(
    symbol: str,
    start_time: datetime = Query(..., description="Start time (ISO format)"),
    end_time: datetime = Query(..., description="End time (ISO format)"),
    interval: str = Query("1h", description="Candlestick interval"),
    db: AsyncSession = Depends(get_db),
):
    """Get market data within a time range."""
    try:
        service = get_market_data_service()
        data = await service.get_market_data_range(db, symbol, interval, start_time, end_time)

        return MarketDataListResponse(items=data, total=len(data))
    except Exception as e:
        logger.error(f"Error getting market data range for {symbol}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get market data range")
