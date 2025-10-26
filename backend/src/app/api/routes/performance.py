"""
API routes for performance metrics management.

Provides endpoints for reading and managing performance metrics.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.exceptions import ResourceNotFoundError, to_http_exception
from ...core.logging import get_logger
from ...db.session import get_db
from ...models.performance_metric import PerformanceMetric
from ...schemas.performance_metric import PerformanceMetricListResponse, PerformanceMetricRead

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/performance", tags=["performance"])


@router.get("", response_model=PerformanceMetricListResponse)
async def list_performance_metrics(
    skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)
):
    """List all performance metrics with pagination."""
    try:
        # Get total count
        count_result = await db.execute(select(func.count(PerformanceMetric.id)))
        total = count_result.scalar()

        # Get paginated results
        result = await db.execute(select(PerformanceMetric).offset(skip).limit(limit))
        metrics = result.scalars().all()

        return PerformanceMetricListResponse(items=metrics, total=total)
    except Exception as e:
        logger.error(f"Error listing performance metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to list performance metrics")


@router.get("/{metric_id}", response_model=PerformanceMetricRead)
async def get_performance_metric(metric_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific performance metric by ID."""
    try:
        result = await db.execute(
            select(PerformanceMetric).where(PerformanceMetric.id == metric_id)
        )
        metric = result.scalar_one_or_none()

        if not metric:
            raise ResourceNotFoundError("PerformanceMetric", metric_id)

        return metric
    except ResourceNotFoundError as e:
        raise to_http_exception(e)
    except Exception as e:
        logger.error(f"Error getting performance metric: {e}")
        raise HTTPException(status_code=500, detail="Failed to get performance metric")
