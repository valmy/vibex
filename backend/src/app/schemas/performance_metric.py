"""
Performance metric schemas for request/response validation.
"""

from typing import Optional
from pydantic import Field
from .base import BaseSchema, BaseCreateSchema


class PerformanceMetricCreate(BaseCreateSchema):
    """Schema for creating a performance metric."""

    account_id: int = Field(..., description="Account ID")
    period: str = Field(..., description="Period: daily, weekly, monthly, yearly")
    period_start: str = Field(..., description="Period start date (ISO format)")
    period_end: str = Field(..., description="Period end date (ISO format)")
    total_trades: int = Field(default=0, ge=0, description="Total trades")
    winning_trades: int = Field(default=0, ge=0, description="Winning trades")
    losing_trades: int = Field(default=0, ge=0, description="Losing trades")
    total_pnl: float = Field(default=0.0, description="Total P&L")
    total_pnl_percent: float = Field(default=0.0, description="Total P&L percent")
    average_win: Optional[float] = Field(None, description="Average win")
    average_loss: Optional[float] = Field(None, description="Average loss")
    profit_factor: Optional[float] = Field(None, description="Profit factor")
    max_drawdown: Optional[float] = Field(None, description="Max drawdown")
    max_drawdown_percent: Optional[float] = Field(None, description="Max drawdown percent")
    sharpe_ratio: Optional[float] = Field(None, description="Sharpe ratio")
    sortino_ratio: Optional[float] = Field(None, description="Sortino ratio")


class PerformanceMetricRead(BaseSchema):
    """Schema for reading a performance metric."""

    account_id: int
    period: str
    period_start: str
    period_end: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    total_pnl_percent: float
    average_win: Optional[float] = None
    average_loss: Optional[float] = None
    profit_factor: Optional[float] = None
    max_drawdown: Optional[float] = None
    max_drawdown_percent: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None


class PerformanceMetricListResponse(BaseSchema):
    """Schema for performance metric list response."""

    total: int
    items: list[PerformanceMetricRead]

