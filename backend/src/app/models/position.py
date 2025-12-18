"""
Position model for open trading positions.

Represents an open position in a trading pair.
"""

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .account import Account
    from .order import Order
    from .trade import Trade


class Position(BaseModel):
    """Trading position model."""

    __tablename__ = "positions"
    __table_args__ = (
        Index("idx_position_account_id", "account_id"),
        Index("idx_position_symbol", "symbol"),
        Index("idx_position_status", "status"),
        {"schema": "trading"},
    )

    # Foreign key
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("trading.accounts.id"), nullable=False, index=True
    )

    # Position identification
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., BTCUSDT
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # long or short
    status: Mapped[str] = mapped_column(
        String(50), default="open", nullable=False
    )  # open, closed, liquidated

    # Position details
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    current_price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    leverage: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    # Position metrics
    entry_value: Mapped[float] = mapped_column(Float, nullable=False)
    current_value: Mapped[float] = mapped_column(Float, nullable=False)
    unrealized_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    unrealized_pnl_percent: Mapped[float] = mapped_column(Float, nullable=False)

    # Risk management
    stop_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    take_profit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="positions")
    orders: Mapped[List["Order"]] = relationship(
        "Order", back_populates="position", cascade="all, delete-orphan"
    )
    trades: Mapped[List["Trade"]] = relationship(
        "Trade", back_populates="position", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Position(id={self.id}, symbol={self.symbol}, side={self.side}, status={self.status})>"
