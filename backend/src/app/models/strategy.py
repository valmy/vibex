"""
Strategy model for trading strategy configurations.

Stores trading strategies and their assignments to accounts.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .account import Account


class Strategy(BaseModel):
    """Trading strategy configuration model."""

    __tablename__ = "strategies"
    __table_args__ = (
        Index("idx_strategy_type", "strategy_type"),
        Index("idx_strategy_active", "is_active"),
        Index("idx_strategy_id_unique", "strategy_id", unique=True),
        {"schema": "trading"},
    )

    strategy_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    strategy_name: Mapped[str] = mapped_column(String(255), nullable=False)
    strategy_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    timeframe_preference: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    max_positions: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    position_sizing: Mapped[str] = mapped_column(String(50), nullable=False, default="percentage")
    order_preference: Mapped[str] = mapped_column(
        String(50), nullable=False, default="any"
    )  # "maker_only", "taker_accepted", "maker_preferred", "any"
    funding_rate_threshold: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )  # In percentage (e.g., 0.05 for 0.05%)
    risk_parameters: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")

    strategy_assignments: Mapped[List["StrategyAssignment"]] = relationship(
        "StrategyAssignment",
        back_populates="strategy",
        foreign_keys="StrategyAssignment.strategy_id",
        cascade="all, delete-orphan",
    )
    strategy_performances: Mapped[List["StrategyPerformance"]] = relationship(
        "StrategyPerformance", back_populates="strategy", cascade="all, delete-orphan"
    )


class StrategyAssignment(BaseModel):
    """Model for tracking strategy assignments to accounts."""

    __tablename__ = "strategy_assignments"
    __table_args__ = (
        Index("idx_strategy_assignment_account", "account_id"),
        Index("idx_strategy_assignment_strategy", "strategy_id"),
        Index("idx_strategy_assignment_active", "is_active"),
        {"schema": "trading"},
    )

    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("trading.accounts.id"), nullable=False)
    strategy_id: Mapped[int] = mapped_column(Integer, ForeignKey("trading.strategies.id"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    assigned_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    previous_strategy_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("trading.strategies.id"), nullable=True)
    switch_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    win_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    deactivated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deactivated_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    deactivation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    account: Mapped["Account"] = relationship("Account", foreign_keys=[account_id])
    strategy: Mapped["Strategy"] = relationship(
        "Strategy", foreign_keys=[strategy_id], back_populates="strategy_assignments"
    )
    previous_strategy: Mapped[Optional["Strategy"]] = relationship("Strategy", foreign_keys=[previous_strategy_id])


class StrategyPerformance(BaseModel):
    """Model for tracking detailed strategy performance metrics."""

    __tablename__ = "strategy_performances"
    __table_args__ = (
        Index("idx_strategy_performance_strategy", "strategy_id"),
        Index("idx_strategy_performance_account", "account_id"),
        Index("idx_strategy_performance_period", "period_start", "period_end"),
        {"schema": "trading"},
    )

    strategy_id: Mapped[int] = mapped_column(Integer, ForeignKey("trading.strategies.id"), nullable=False)
    account_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("trading.accounts.id"), nullable=True)
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_days: Mapped[int] = mapped_column(Integer, nullable=False)
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    winning_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    losing_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    win_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_win: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_loss: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_win: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_loss: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_drawdown: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sharpe_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sortino_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    profit_factor: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_trade_duration_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_volume_traded: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_fees_paid: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_funding_paid: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_liquidations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    var_95: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_consecutive_losses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_consecutive_wins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    additional_metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    strategy: Mapped["Strategy"] = relationship("Strategy", back_populates="strategy_performances")
    account: Mapped[Optional["Account"]] = relationship("Account")
