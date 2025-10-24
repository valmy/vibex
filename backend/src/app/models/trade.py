"""
Trade model for executed trades.

Represents a completed trade execution.
"""

from sqlalchemy import Column, String, Float, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship
from .base import BaseModel


class Trade(BaseModel):
    """Executed trade model."""

    __tablename__ = "trades"
    __table_args__ = (
        Index("idx_trade_account_id", "account_id"),
        Index("idx_trade_position_id", "position_id"),
        Index("idx_trade_order_id", "order_id"),
        Index("idx_trade_symbol", "symbol"),
        {"schema": "trading"}
    )

    # Foreign keys
    account_id = Column(Integer, ForeignKey("trading.accounts.id"), nullable=False, index=True)
    position_id = Column(Integer, ForeignKey("trading.positions.id"), nullable=True, index=True)
    order_id = Column(Integer, ForeignKey("trading.orders.id"), nullable=True, index=True)

    # Trade identification
    exchange_trade_id = Column(String(255), unique=True, nullable=True)
    symbol = Column(String(50), nullable=False)
    side = Column(String(10), nullable=False)  # buy or sell

    # Trade details
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    total_cost = Column(Float, nullable=False)
    commission = Column(Float, default=0.0, nullable=False)
    commission_asset = Column(String(50), nullable=True)

    # Trade metrics
    pnl = Column(Float, nullable=True)
    pnl_percent = Column(Float, nullable=True)
    roi = Column(Float, nullable=True)

    # Relationships
    account = relationship("Account", back_populates="trades")
    position = relationship("Position", back_populates="trades")
    order = relationship("Order", back_populates="trades")

    def __repr__(self):
        """String representation."""
        return f"<Trade(id={self.id}, symbol={self.symbol}, side={self.side}, quantity={self.quantity})>"

