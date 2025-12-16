"""
API routes for order management.

Provides endpoints for creating, reading, updating, and deleting trading orders.
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
from ...models.order import Order
from ...schemas.order import OrderCreate, OrderListResponse, OrderRead, OrderUpdate

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/orders", tags=["Trading"])


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(
    order_data: OrderCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Create a new order."""
    try:
        order = Order(**order_data.model_dump())
        db.add(order)
        await db.commit()
        await db.refresh(order)
        logger.info(f"Created order for account {order.account_id}")
        return order
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating order: {e}")
        raise HTTPException(status_code=500, detail="Failed to create order") from e


@router.get("", response_model=OrderListResponse)
async def list_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: Annotated[int, Query()] = 0,
    limit: Annotated[int, Query()] = 100,
):
    """List all orders with pagination."""
    try:
        # Get total count
        count_result = await db.execute(select(func.count(Order.id)))
        total = count_result.scalar()

        # Get paginated results
        result = await db.execute(select(Order).offset(skip).limit(limit))
        orders = result.scalars().all()

        return OrderListResponse(items=orders, total=total)
    except Exception as e:
        logger.error(f"Error listing orders: {e}")
        raise HTTPException(status_code=500, detail="Failed to list orders") from e


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(order_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    """Get a specific order by ID."""
    try:
        result = await db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()

        if not order:
            raise ResourceNotFoundError("Order", order_id)

        return order
    except ResourceNotFoundError as e:
        raise to_http_exception(e) from e
    except Exception as e:
        logger.error(f"Error getting order: {e}")
        raise HTTPException(status_code=500, detail="Failed to get order") from e


@router.put("/{order_id}", response_model=OrderRead)
async def update_order(
    order_id: int,
    order_data: OrderUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Update an order."""
    try:
        result = await db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()

        if not order:
            raise ResourceNotFoundError("Order", order_id)

        # Update fields
        update_data = order_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(order, field, value)

        await db.commit()
        await db.refresh(order)
        logger.info(f"Updated order {order_id}")
        return order
    except ResourceNotFoundError as e:
        raise to_http_exception(e) from e
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating order: {e}")
        raise HTTPException(status_code=500, detail="Failed to update order") from e


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order(
    order_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Delete an order."""
    try:
        result = await db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()

        if not order:
            raise ResourceNotFoundError("Order", order_id)

        await db.delete(order)
        await db.commit()
    except ResourceNotFoundError as e:
        raise to_http_exception(e) from e
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting order: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete order") from e
