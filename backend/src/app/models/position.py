"""
Position model for open trading positions.

Represents an open position in a trading pair.
"""

from sqlalchemy import Column, String, Float, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship
from .base import BaseModel


class Position(BaseModel):
    """Trading position model."""

    __tablename__ = "positions"
    __table_args__ = (
        Index("idx_position_account_id", "account_id"),
        Index("idx_position_symbol", "symbol"),
        Index("idx_position_status", "status"),
    )

    # Foreign key
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)

    # Position identification
    symbol = Column(String(50), nullable=False)  # e.g., BTC/USDT
    side = Column(String(10), nullable=False)  # long or short
    status = Column(String(50), default="open", nullable=False)  # open, closed, liquidated

    # Position details
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    leverage = Column(Float, default=1.0, nullable=False)

    # Position metrics
    entry_value = Column(Float, nullable=False)
    current_value = Column(Float, nullable=False)
    unrealized_pnl = Column(Float, nullable=False)
    unrealized_pnl_percent = Column(Float, nullable=False)

    # Risk management
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)

    # Relationships
    account = relationship("Account", back_populates="positions")
    orders = relationship("Order", back_populates="position", cascade="all, delete-orphan")
    trades = relationship("Trade", back_populates="position", cascade="all, delete-orphan")

    def __repr__(self):
        """String representation."""
        return f"<Position(id={self.id}, symbol={self.symbol}, side={self.side}, status={self.status})>"

