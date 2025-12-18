"""
API routes for performance metrics management.

Provides endpoints for reading and managing performance metrics.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.exceptions import ResourceNotFoundError, to_http_exception
from ...core.logging import get_logger
from ...db.session import get_db
from ...models.performance_metric import PerformanceMetric
from ...schemas.performance_metric import PerformanceMetricListResponse, PerformanceMetricRead

from ...services import data_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/performance", tags=["Performance"])


@router.get("", response_model=PerformanceMetricListResponse)
async def list_performance_metrics(
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: Annotated[int, Query()] = 0,
    limit: Annotated[int, Query()] = 100,
) -> PerformanceMetricListResponse:
    """List all performance metrics with pagination."""
    try:
        metrics, total = await data_service.list_with_count(db, PerformanceMetric, skip, limit)

        return PerformanceMetricListResponse(
            items=[PerformanceMetricRead.model_validate(m) for m in metrics],
            total=total,
        )
    except Exception as e:
        logger.error(f"Error listing performance metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to list performance metrics") from e


@router.get("/{metric_id}", response_model=PerformanceMetricRead)
async def get_performance_metric(
    metric_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> PerformanceMetricRead:
    """Get a specific performance metric by ID."""
    try:
        result = await db.execute(
            select(PerformanceMetric).where(PerformanceMetric.id == metric_id)
        )
        metric = result.scalar_one_or_none()

        if not metric:
            raise ResourceNotFoundError("PerformanceMetric", metric_id)

        return PerformanceMetricRead.model_validate(metric)
    except ResourceNotFoundError as e:
        raise to_http_exception(e) from e
    except Exception as e:
        logger.error(f"Error getting performance metric: {e}")
        raise HTTPException(status_code=500, detail="Failed to get performance metric") from e
