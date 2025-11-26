"""
Position schemas for request/response validation.
"""

from typing import Optional

from pydantic import Field

from .base import BaseCreateSchema, BaseSchema, BaseUpdateSchema


class PositionCreate(BaseCreateSchema):
    """Schema for creating a position."""

    account_id: int = Field(..., description="Account ID")
    symbol: str = Field(..., min_length=1, max_length=50, description="Trading pair symbol")
    side: str = Field(..., description="Position side: long or short")
    entry_price: float = Field(..., gt=0, description="Entry price")
    quantity: float = Field(..., gt=0, description="Position quantity")
    leverage: float = Field(default=1.0, ge=1.0, le=20.0, description="Position leverage")
    stop_loss: Optional[float] = Field(None, gt=0, description="Stop loss price")
    take_profit: Optional[float] = Field(None, gt=0, description="Take profit price")


class PositionUpdate(BaseUpdateSchema):
    """Schema for updating a position."""

    current_price: Optional[float] = Field(None, gt=0)
    stop_loss: Optional[float] = Field(None, gt=0)
    take_profit: Optional[float] = Field(None, gt=0)
    status: Optional[str] = None


class PositionRead(BaseSchema):
    """Schema for reading a position."""

    account_id: int
    symbol: str
    side: str
    status: str
    entry_price: float
    current_price: float
    quantity: float
    leverage: float
    entry_value: float
    current_value: float
    unrealized_pnl: float
    unrealized_pnl_percent: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class PositionListResponse(BaseSchema):
    """Schema for position list response."""

    total: int
    items: list[PositionRead]
