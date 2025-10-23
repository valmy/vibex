"""
Account schemas for request/response validation.
"""

from typing import Optional
from pydantic import Field
from .base import BaseSchema, BaseCreateSchema, BaseUpdateSchema


class AccountCreate(BaseCreateSchema):
    """Schema for creating an account."""

    name: str = Field(..., min_length=1, max_length=255, description="Account name")
    description: Optional[str] = Field(None, max_length=1000, description="Account description")
    api_key: Optional[str] = Field(None, description="API key")
    api_secret: Optional[str] = Field(None, description="API secret")
    api_passphrase: Optional[str] = Field(None, description="API passphrase")
    leverage: float = Field(default=2.0, ge=1.0, le=5.0, description="Trading leverage")
    max_position_size_usd: float = Field(default=10000.0, gt=0, description="Max position size in USD")
    risk_per_trade: float = Field(default=0.02, ge=0.01, le=0.1, description="Risk per trade (0.01-0.1)")
    is_paper_trading: bool = Field(default=False, description="Is paper trading")
    is_multi_account: bool = Field(default=False, description="Is multi-account mode")


class AccountUpdate(BaseUpdateSchema):
    """Schema for updating an account."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    leverage: Optional[float] = Field(None, ge=1.0, le=5.0)
    max_position_size_usd: Optional[float] = Field(None, gt=0)
    risk_per_trade: Optional[float] = Field(None, ge=0.01, le=0.1)
    is_paper_trading: Optional[bool] = None
    is_enabled: Optional[bool] = None


class AccountRead(BaseSchema):
    """Schema for reading an account."""

    name: str
    description: Optional[str] = None
    status: str
    leverage: float
    max_position_size_usd: float
    risk_per_trade: float
    is_paper_trading: bool
    is_multi_account: bool
    is_enabled: bool


class AccountListResponse(BaseSchema):
    """Schema for account list response."""

    total: int
    items: list[AccountRead]

