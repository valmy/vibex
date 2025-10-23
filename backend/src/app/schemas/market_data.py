"""
Market data schemas for request/response validation.
"""

from typing import Optional
from pydantic import Field
from .base import BaseSchema


class MarketDataRead(BaseSchema):
    """Schema for reading market data."""

    symbol: str
    timeframe: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    timestamp: Optional[str] = None


class MarketDataListResponse(BaseSchema):
    """Schema for market data list response."""

    total: int
    items: list[MarketDataRead]

