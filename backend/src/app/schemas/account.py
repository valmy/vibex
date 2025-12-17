"""
Account schemas for request/response validation.
"""

from typing import Optional

from pydantic import Field

from .base import BaseCreateSchema, BaseSchema, BaseUpdateSchema

# ============================================================================
# USER SCHEMAS
# ============================================================================


class UserCreate(BaseCreateSchema):
    address: str = Field(..., min_length=42, max_length=42, description="Ethereum address")
    is_admin: bool = Field(default=False, description="Is user an admin")


class UserUpdate(BaseUpdateSchema):
    is_admin: Optional[bool] = None


class UserRead(BaseSchema):
    address: str
    is_admin: bool


class User(UserRead):
    pass


# ============================================================================
# ACCOUNT SCHEMAS
# ============================================================================


class AccountCreate(BaseCreateSchema):
    """Schema for creating an account."""

    name: str = Field(..., min_length=1, max_length=255, description="Account name")
    description: Optional[str] = Field(None, max_length=1000, description="Account description")
    api_key: Optional[str] = Field(None, description="API key")
    api_secret: Optional[str] = Field(None, description="API secret")
    api_passphrase: Optional[str] = Field(None, description="API passphrase")
    leverage: float = Field(default=2.0, ge=1.0, le=20.0, description="Trading leverage")
    max_position_size_usd: float = Field(
        default=10000.0, gt=0, description="Max position size in USD"
    )
    risk_per_trade: float = Field(
        default=0.02, ge=0.01, le=0.1, description="Risk per trade (0.01-0.1)"
    )
    is_paper_trading: bool = Field(default=True, description="Is paper trading")
    is_multi_account: bool = Field(default=False, description="Is multi-account mode")
    balance_usd: Optional[float] = Field(
        None, ge=0, description="Initial balance for paper trading"
    )


class AccountUpdate(BaseUpdateSchema):
    """Schema for updating an account."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    status: Optional[str] = Field(None, pattern="^(active|paused|stopped)$")
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    leverage: Optional[float] = Field(None, ge=1.0, le=20.0)
    max_position_size_usd: Optional[float] = Field(None, gt=0)
    risk_per_trade: Optional[float] = Field(None, ge=0.01, le=0.1)
    is_paper_trading: Optional[bool] = None
    is_enabled: Optional[bool] = None
    balance_usd: Optional[float] = Field(None, ge=0)


class AccountRead(BaseSchema):
    """Schema for reading an account with masked credentials."""

    name: str
    description: Optional[str] = None
    status: str
    user_id: int
    has_api_credentials: bool = Field(
        description="True if API credentials are set (actual credentials are masked)"
    )
    leverage: float
    max_position_size_usd: float
    risk_per_trade: float
    maker_fee_bps: float
    taker_fee_bps: float
    balance_usd: float
    is_paper_trading: bool
    is_multi_account: bool
    is_enabled: bool

    @classmethod
    def from_account(cls, account: object) -> "AccountRead":
        """Create AccountRead from Account model with credential masking."""
        # Using getattr to safely access attributes since account is typed as object
        # but is expected to be an Account SQLAlchemy model
        return cls(
            id=getattr(account, "id"),
            name=getattr(account, "name"),
            description=getattr(account, "description"),
            status=getattr(account, "status"),
            user_id=getattr(account, "user_id"),
            has_api_credentials=bool(getattr(account, "api_key")),
            leverage=getattr(account, "leverage"),
            max_position_size_usd=getattr(account, "max_position_size_usd"),
            risk_per_trade=getattr(account, "risk_per_trade"),
            maker_fee_bps=getattr(account, "maker_fee_bps"),
            taker_fee_bps=getattr(account, "taker_fee_bps"),
            balance_usd=getattr(account, "balance_usd"),
            is_paper_trading=getattr(account, "is_paper_trading"),
            is_multi_account=getattr(account, "is_multi_account"),
            is_enabled=getattr(account, "is_enabled"),
            created_at=getattr(account, "created_at"),
            updated_at=getattr(account, "updated_at"),
        )


class AccountListResponse(BaseSchema):
    """Schema for account list response."""

    total: int
    items: list[AccountRead]
