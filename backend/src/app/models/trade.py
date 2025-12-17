"""
Trade model for executed trades.

Represents a completed trade execution.
"""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .account import Account
    from .order import Order
    from .position import Position


class Trade(BaseModel):
    """Executed trade model."""

    __tablename__ = "trades"
    __table_args__ = (
        Index("idx_trade_account_id", "account_id"),
        Index("idx_trade_position_id", "position_id"),
        Index("idx_trade_order_id", "order_id"),
        Index("idx_trade_symbol", "symbol"),
        {"schema": "trading"},
    )

    # Foreign keys
    account_id: Mapped[int] = mapped_column(
        ForeignKey("trading.accounts.id"), nullable=False, index=True
    )
    position_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("trading.positions.id"), nullable=True, index=True
    )
    order_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("trading.orders.id"), nullable=True, index=True
    )

    # Trade identification
    exchange_trade_id: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True
    )
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # buy or sell

    # Trade details
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    total_cost: Mapped[float] = mapped_column(Float, nullable=False)
    commission: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    commission_asset: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Trade metrics
    pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pnl_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    roi: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="trades")
    position: Mapped[Optional["Position"]] = relationship("Position", back_populates="trades")
    order: Mapped[Optional["Order"]] = relationship("Order", back_populates="trades")

    def __repr__(self) -> str:
        """String representation."""
        return f"<Trade(id={self.id}, symbol={self.symbol}, side={self.side}, quantity={self.quantity})>"
