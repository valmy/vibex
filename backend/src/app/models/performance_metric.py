"""
Performance metric model for tracking trading performance.

Represents performance metrics and statistics.
"""

from sqlalchemy import Column, String, Float, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship
from .base import BaseModel


class PerformanceMetric(BaseModel):
    """Performance metric model."""

    __tablename__ = "performance_metrics"
    __table_args__ = (
        Index("idx_performance_account_id", "account_id"),
        Index("idx_performance_period", "period"),
        {"schema": "trading"}
    )

    # Foreign key
    account_id = Column(Integer, ForeignKey("trading.accounts.id"), nullable=False, index=True)

    # Period identification
    period = Column(String(50), nullable=False)  # daily, weekly, monthly, yearly
    period_start = Column(String(50), nullable=False)  # ISO format date
    period_end = Column(String(50), nullable=False)  # ISO format date

    # Performance metrics
    total_trades = Column(Integer, default=0, nullable=False)
    winning_trades = Column(Integer, default=0, nullable=False)
    losing_trades = Column(Integer, default=0, nullable=False)
    win_rate = Column(Float, default=0.0, nullable=False)

    # Profit/Loss metrics
    total_pnl = Column(Float, default=0.0, nullable=False)
    total_pnl_percent = Column(Float, default=0.0, nullable=False)
    average_win = Column(Float, nullable=True)
    average_loss = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)

    # Risk metrics
    max_drawdown = Column(Float, nullable=True)
    max_drawdown_percent = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    sortino_ratio = Column(Float, nullable=True)

    # Relationships
    account = relationship("Account", back_populates="performance_metrics")

    def __repr__(self):
        """String representation."""
        return f"<PerformanceMetric(id={self.id}, period={self.period}, win_rate={self.win_rate})>"

