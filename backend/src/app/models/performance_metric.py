"""
Performance metric model for tracking trading performance.

Represents performance metrics and statistics.
"""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .account import Account


class PerformanceMetric(BaseModel):
    """Performance metric model."""

    __tablename__ = "performance_metrics"
    __table_args__ = (
        Index("idx_performance_account_id", "account_id"),
        Index("idx_performance_period", "period"),
        {"schema": "trading"},
    )

    # Foreign key
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("trading.accounts.id"), nullable=False, index=True
    )

    # Period identification
    period: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # daily, weekly, monthly, yearly
    period_start: Mapped[str] = mapped_column(String(50), nullable=False)  # ISO format date
    period_end: Mapped[str] = mapped_column(String(50), nullable=False)  # ISO format date

    # Performance metrics
    total_trades: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    winning_trades: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    losing_trades: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Profit/Loss metrics
    total_pnl: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_pnl_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    average_win: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    average_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    profit_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Risk metrics
    max_drawdown: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_drawdown_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sharpe_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sortino_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="performance_metrics")

    def __repr__(self) -> str:
        """String representation."""
        return f"<PerformanceMetric(id={self.id}, period={self.period}, win_rate={self.win_rate})>"
