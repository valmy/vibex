"""
Account model for trading accounts.

Represents a trading account with configuration and status.
"""

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .base import BaseModel


class User(BaseModel):
    __tablename__ = "users"
    __table_args__ = ({"schema": "trading", "extend_existing": True},)

    address = Column(String(42), unique=True, nullable=False, index=True)
    is_admin = Column(Boolean, default=False, nullable=False)

    accounts = relationship("Account", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(address={self.address}, is_admin={self.is_admin})>"


class Account(BaseModel):
    """Trading account model."""

    __tablename__ = "accounts"
    __table_args__ = ({"schema": "trading", "extend_existing": True},)

    # Account identification
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="active", nullable=False)  # active, inactive, suspended

    # User relationship
    user_id = Column(Integer, ForeignKey("trading.users.id"), nullable=False)
    user = relationship("User", back_populates="accounts")

    # Account configuration
    api_key = Column(String(255), nullable=True)
    api_secret = Column(String(255), nullable=True)
    api_passphrase = Column(String(255), nullable=True)

    # Trading parameters
    leverage = Column(Float, default=2.0, nullable=False)
    max_position_size_usd = Column(Float, default=10000.0, nullable=False)
    risk_per_trade = Column(Float, default=0.02, nullable=False)  # 2% risk per trade
    maker_fee_bps = Column(Float, default=5.0, nullable=False)  # 5 bps (0.05%)
    taker_fee_bps = Column(Float, default=20.0, nullable=False)  # 20 bps (0.20%)
    balance_usd = Column(Float, default=0.0, nullable=False)

    # Account settings
    is_paper_trading = Column(Boolean, default=False, nullable=False)
    is_multi_account = Column(Boolean, default=False, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)

    # Relationships
    positions = relationship("Position", back_populates="account", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="account", cascade="all, delete-orphan")
    trades = relationship("Trade", back_populates="account", cascade="all, delete-orphan")
    diary_entries = relationship(
        "DiaryEntry", back_populates="account", cascade="all, delete-orphan"
    )
    performance_metrics = relationship(
        "PerformanceMetric", back_populates="account", cascade="all, delete-orphan"
    )
    decisions = relationship("Decision", back_populates="account", cascade="all, delete-orphan")
    strategy_assignments = relationship("StrategyAssignment", back_populates="account", cascade="all, delete-orphan")

    def __repr__(self):
        """String representation."""
        return f"<Account(id={self.id}, name={self.name}, status={self.status})>"
