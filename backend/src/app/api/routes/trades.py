"""
API routes for trade management.

Provides endpoints for reading and managing completed trades.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.exceptions import ResourceNotFoundError, to_http_exception
from ...core.logging import get_logger
from ...db.session import get_db
from ...models.trade import Trade
from ...schemas.trade import TradeListResponse, TradeRead

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/trades", tags=["trades"])


@router.get("", response_model=TradeListResponse)
async def list_trades(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """List all trades with pagination."""
    try:
        # Get total count
        count_result = await db.execute(select(func.count(Trade.id)))
        total = count_result.scalar()

        # Get paginated results
        result = await db.execute(select(Trade).offset(skip).limit(limit))
        trades = result.scalars().all()

        return TradeListResponse(items=trades, total=total)
    except Exception as e:
        logger.error(f"Error listing trades: {e}")
        raise HTTPException(status_code=500, detail="Failed to list trades")


@router.get("/{trade_id}", response_model=TradeRead)
async def get_trade(trade_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific trade by ID."""
    try:
        result = await db.execute(select(Trade).where(Trade.id == trade_id))
        trade = result.scalar_one_or_none()

        if not trade:
            raise ResourceNotFoundError("Trade", trade_id)

        return trade
    except ResourceNotFoundError as e:
        raise to_http_exception(e)
    except Exception as e:
        logger.error(f"Error getting trade: {e}")
        raise HTTPException(status_code=500, detail="Failed to get trade")
