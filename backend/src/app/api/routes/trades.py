"""
API routes for trade management.

Provides endpoints for reading and managing completed trades.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.exceptions import ResourceNotFoundError, to_http_exception
from ...core.logging import get_logger
from ...db.session import get_db
from ...models.trade import Trade
from ...schemas.trade import TradeListResponse, TradeRead

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/trades", tags=["Trading"])


@router.get("", response_model=TradeListResponse)
async def list_trades(
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: Annotated[int, Query()] = 0,
    limit: Annotated[int, Query()] = 100,
) -> TradeListResponse:
    """List all trades with pagination."""
    try:
        # Get total count
        count_result = await db.execute(select(func.count(Trade.id)))
        total = count_result.scalar() or 0

        # Get paginated results
        result = await db.execute(select(Trade).offset(skip).limit(limit))
        trades = result.scalars().all()

        return TradeListResponse(
            items=[TradeRead.model_validate(t) for t in trades],
            total=total,
        )
    except Exception as e:
        logger.error(f"Error listing trades: {e}")
        raise HTTPException(status_code=500, detail="Failed to list trades") from e


@router.get("/{trade_id}", response_model=TradeRead)
async def get_trade(trade_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> TradeRead:
    """Get a specific trade by ID."""
    try:
        result = await db.execute(select(Trade).where(Trade.id == trade_id))
        trade = result.scalar_one_or_none()

        if not trade:
            raise ResourceNotFoundError("Trade", trade_id)

        return TradeRead.model_validate(trade)
    except ResourceNotFoundError as e:
        raise to_http_exception(e) from e
    except Exception as e:
        logger.error(f"Error getting trade: {e}")
        raise HTTPException(status_code=500, detail="Failed to get trade") from e
