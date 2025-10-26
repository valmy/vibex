"""
Account model for trading accounts.

Represents a trading account with configuration and status.
"""

from sqlalchemy import Boolean, Column, Float, Index, String, Text
from sqlalchemy.orm import relationship

from .base import BaseModel


class Account(BaseModel):
    """Trading account model."""

    __tablename__ = "accounts"
    __table_args__ = (
        Index("idx_account_name", "name"),
        Index("idx_account_status", "status"),
        {"schema": "trading"},
    )

    # Account identification
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="active", nullable=False)  # active, inactive, suspended

    # Account configuration
    api_key = Column(String(255), nullable=True)
    api_secret = Column(String(255), nullable=True)
    api_passphrase = Column(String(255), nullable=True)

    # Trading parameters
    leverage = Column(Float, default=2.0, nullable=False)
    max_position_size_usd = Column(Float, default=10000.0, nullable=False)
    risk_per_trade = Column(Float, default=0.02, nullable=False)  # 2% risk per trade

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

    def __repr__(self):
        """String representation."""
        return f"<Account(id={self.id}, name={self.name}, status={self.status})>"
