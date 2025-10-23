"""
Order schemas for request/response validation.
"""

from typing import Optional
from pydantic import Field
from .base import BaseSchema, BaseCreateSchema, BaseUpdateSchema


class OrderCreate(BaseCreateSchema):
    """Schema for creating an order."""

    account_id: int = Field(..., description="Account ID")
    position_id: Optional[int] = Field(None, description="Position ID")
    symbol: str = Field(..., min_length=1, max_length=50, description="Trading pair symbol")
    order_type: str = Field(..., description="Order type: market, limit, stop, stop-limit")
    side: str = Field(..., description="Order side: buy or sell")
    quantity: float = Field(..., gt=0, description="Order quantity")
    price: Optional[float] = Field(None, gt=0, description="Order price (for limit orders)")
    stop_price: Optional[float] = Field(None, gt=0, description="Stop price (for stop orders)")
    time_in_force: str = Field(default="GTC", description="Time in force: GTC, IOC, FOK")


class OrderUpdate(BaseUpdateSchema):
    """Schema for updating an order."""

    status: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    stop_price: Optional[float] = Field(None, gt=0)


class OrderRead(BaseSchema):
    """Schema for reading an order."""

    account_id: int
    position_id: Optional[int] = None
    symbol: str
    order_type: str
    side: str
    status: str
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    filled_quantity: float
    average_price: Optional[float] = None
    total_cost: Optional[float] = None
    commission: float
    time_in_force: str


class OrderListResponse(BaseSchema):
    """Schema for order list response."""

    total: int
    items: list[OrderRead]

