"""
Trade schemas for request/response validation.
"""

from typing import Optional

from pydantic import Field

from .base import BaseCreateSchema, BaseSchema


class TradeCreate(BaseCreateSchema):
    """Schema for creating a trade."""

    account_id: int = Field(..., description="Account ID")
    position_id: Optional[int] = Field(None, description="Position ID")
    order_id: Optional[int] = Field(None, description="Order ID")
    symbol: str = Field(..., min_length=1, max_length=50, description="Trading pair symbol")
    side: str = Field(..., description="Trade side: buy or sell")
    quantity: float = Field(..., gt=0, description="Trade quantity")
    price: float = Field(..., gt=0, description="Trade price")
    commission: float = Field(default=0.0, ge=0, description="Commission")
    commission_asset: Optional[str] = Field(None, description="Commission asset")


class TradeRead(BaseSchema):
    """Schema for reading a trade."""

    account_id: int
    position_id: Optional[int] = None
    order_id: Optional[int] = None
    symbol: str
    side: str
    quantity: float
    price: float
    total_cost: float
    commission: float
    commission_asset: Optional[str] = None
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    roi: Optional[float] = None


class TradeListResponse(BaseSchema):
    """Schema for trade list response."""

    total: int
    items: list[TradeRead]
