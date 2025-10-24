"""
Order model for trading orders.

Represents a trading order (pending, filled, cancelled, etc.).
"""

from sqlalchemy import Column, String, Float, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship
from .base import BaseModel


class Order(BaseModel):
    """Trading order model."""

    __tablename__ = "orders"
    __table_args__ = (
        Index("idx_order_account_id", "account_id"),
        Index("idx_order_position_id", "position_id"),
        Index("idx_order_symbol", "symbol"),
        Index("idx_order_status", "status"),
        {"schema": "trading"}
    )

    # Foreign keys
    account_id = Column(Integer, ForeignKey("trading.accounts.id"), nullable=False, index=True)
    position_id = Column(Integer, ForeignKey("trading.positions.id"), nullable=True, index=True)

    # Order identification
    exchange_order_id = Column(String(255), unique=True, nullable=True)
    symbol = Column(String(50), nullable=False)
    order_type = Column(String(50), nullable=False)  # market, limit, stop, stop-limit
    side = Column(String(10), nullable=False)  # buy or sell
    status = Column(String(50), default="pending", nullable=False)  # pending, filled, cancelled, rejected

    # Order details
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=True)
    stop_price = Column(Float, nullable=True)
    time_in_force = Column(String(20), default="GTC", nullable=False)  # GTC, IOC, FOK

    # Execution details
    filled_quantity = Column(Float, default=0.0, nullable=False)
    average_price = Column(Float, nullable=True)
    total_cost = Column(Float, nullable=True)
    commission = Column(Float, default=0.0, nullable=False)

    # Relationships
    account = relationship("Account", back_populates="orders")
    position = relationship("Position", back_populates="orders")
    trades = relationship("Trade", back_populates="order", cascade="all, delete-orphan")

    def __repr__(self):
        """String representation."""
        return f"<Order(id={self.id}, symbol={self.symbol}, side={self.side}, status={self.status})>"

