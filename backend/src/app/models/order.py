"""
Order model for trading orders.

Represents a trading order (pending, filled, cancelled, etc.).
"""

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .account import Account
    from .position import Position
    from .trade import Trade


class Order(BaseModel):
    """Trading order model."""

    __tablename__ = "orders"
    __table_args__ = (
        Index("idx_order_account_id", "account_id"),
        Index("idx_order_position_id", "position_id"),
        Index("idx_order_symbol", "symbol"),
        Index("idx_order_status", "status"),
        {"schema": "trading"},
    )

    # Foreign keys
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("trading.accounts.id"), nullable=False, index=True
    )
    position_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("trading.positions.id"), nullable=True, index=True
    )

    # Order identification
    exchange_order_id: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True
    )
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    order_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # market, limit, stop, stop-limit
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # buy or sell
    status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False
    )  # pending, filled, cancelled, rejected

    # Order details
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stop_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    time_in_force: Mapped[str] = mapped_column(
        String(20), default="GTC", nullable=False
    )  # GTC, IOC, FOK

    # Execution details
    filled_quantity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    average_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    commission: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="orders")
    position: Mapped[Optional["Position"]] = relationship("Position", back_populates="orders")
    trades: Mapped[List["Trade"]] = relationship(
        "Trade", back_populates="order", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<Order(id={self.id}, symbol={self.symbol}, side={self.side}, status={self.status})>"
        )
