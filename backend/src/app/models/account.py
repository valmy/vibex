"""
Account model for trading accounts.

Represents a trading account with configuration and status.
"""

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .decision import Decision
    from .diary_entry import DiaryEntry
    from .order import Order
    from .performance_metric import PerformanceMetric
    from .position import Position
    from .strategy import StrategyAssignment, StrategyPerformance
    from .trade import Trade


class User(BaseModel):
    __tablename__ = "users"
    __table_args__ = ({"schema": "trading", "extend_existing": True},)

    address: Mapped[str] = mapped_column(String(42), unique=True, nullable=False, index=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    accounts: Mapped[List["Account"]] = relationship("Account", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(address={self.address}, is_admin={self.is_admin})>"


class Account(BaseModel):
    """Trading account model."""

    __tablename__ = "accounts"
    __table_args__ = ({"schema": "trading", "extend_existing": True},)

    # Account identification
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)  # active, inactive, suspended

    # User relationship
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("trading.users.id"), nullable=False)
    user: Mapped["User"] = relationship("User", back_populates="accounts")

    # Account configuration
    api_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    api_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    api_passphrase: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Trading parameters
    leverage: Mapped[float] = mapped_column(Float, default=2.0, nullable=False)
    max_position_size_usd: Mapped[float] = mapped_column(Float, default=10000.0, nullable=False)
    risk_per_trade: Mapped[float] = mapped_column(Float, default=0.02, nullable=False)  # 2% risk per trade
    maker_fee_bps: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)  # 5 bps (0.05%)
    taker_fee_bps: Mapped[float] = mapped_column(Float, default=20.0, nullable=False)  # 20 bps (0.20%)
    balance_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Account settings
    is_paper_trading: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_multi_account: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    positions: Mapped[List["Position"]] = relationship("Position", back_populates="account", cascade="all, delete-orphan")
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="account", cascade="all, delete-orphan")
    trades: Mapped[List["Trade"]] = relationship("Trade", back_populates="account", cascade="all, delete-orphan")
    diary_entries: Mapped[List["DiaryEntry"]] = relationship(
        "DiaryEntry", back_populates="account", cascade="all, delete-orphan"
    )
    performance_metrics: Mapped[List["PerformanceMetric"]] = relationship(
        "PerformanceMetric", back_populates="account", cascade="all, delete-orphan"
    )
    decisions: Mapped[List["Decision"]] = relationship("Decision", back_populates="account", cascade="all, delete-orphan")
    strategy_assignments: Mapped[List["StrategyAssignment"]] = relationship(
        "StrategyAssignment", back_populates="account", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Account(id={self.id}, name={self.name}, status={self.status})>"
