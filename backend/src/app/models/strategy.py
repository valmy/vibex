"""
Strategy model for trading strategy configurations.

Stores trading strategies and their assignments to accounts.
"""

from datetime import datetime

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
from sqlalchemy.orm import relationship

from .base import BaseModel


class Strategy(BaseModel):
    """Trading strategy configuration model."""

    __tablename__ = "strategies"
    __table_args__ = (
        Index("idx_strategy_type", "strategy_type"),
        Index("idx_strategy_active", "is_active"),
        Index("idx_strategy_id_unique", "strategy_id", unique=True),
        {"schema": "trading"},
    )

    strategy_id = Column(String(100), nullable=False, unique=True, index=True)
    strategy_name = Column(String(255), nullable=False)
    strategy_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    prompt_template = Column(Text, nullable=False)
    timeframe_preference = Column(JSON, nullable=False)
    max_positions = Column(Integer, nullable=False, default=3)
    position_sizing = Column(String(50), nullable=False, default="percentage")
    risk_parameters = Column(JSON, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    is_default = Column(Boolean, nullable=False, default=False)
    created_by = Column(String(100), nullable=True)
    version = Column(String(20), nullable=False, default="1.0")

    strategy_assignments = relationship(
        "StrategyAssignment",
        back_populates="strategy",
        foreign_keys="StrategyAssignment.strategy_id",
        cascade="all, delete-orphan",
    )
    strategy_performances = relationship(
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

    account_id = Column(Integer, ForeignKey("trading.accounts.id"), nullable=False)
    strategy_id = Column(Integer, ForeignKey("trading.strategies.id"), nullable=False)
    assigned_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    assigned_by = Column(String(100), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    previous_strategy_id = Column(Integer, ForeignKey("trading.strategies.id"), nullable=True)
    switch_reason = Column(Text, nullable=True)
    total_trades = Column(Integer, nullable=False, default=0)
    total_pnl = Column(Float, nullable=False, default=0.0)
    win_rate = Column(Float, nullable=True)
    deactivated_at = Column(DateTime, nullable=True)
    deactivated_by = Column(String(100), nullable=True)
    deactivation_reason = Column(Text, nullable=True)

    account = relationship("Account", foreign_keys=[account_id])
    strategy = relationship(
        "Strategy", foreign_keys=[strategy_id], back_populates="strategy_assignments"
    )
    previous_strategy = relationship("Strategy", foreign_keys=[previous_strategy_id])


class StrategyPerformance(BaseModel):
    """Model for tracking detailed strategy performance metrics."""

    __tablename__ = "strategy_performances"
    __table_args__ = (
        Index("idx_strategy_performance_strategy", "strategy_id"),
        Index("idx_strategy_performance_account", "account_id"),
        Index("idx_strategy_performance_period", "period_start", "period_end"),
        {"schema": "trading"},
    )

    strategy_id = Column(Integer, ForeignKey("trading.strategies.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("trading.accounts.id"), nullable=True)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    period_days = Column(Integer, nullable=False)
    total_trades = Column(Integer, nullable=False, default=0)
    winning_trades = Column(Integer, nullable=False, default=0)
    losing_trades = Column(Integer, nullable=False, default=0)
    win_rate = Column(Float, nullable=False, default=0.0)
    total_pnl = Column(Float, nullable=False, default=0.0)
    avg_win = Column(Float, nullable=False, default=0.0)
    avg_loss = Column(Float, nullable=False, default=0.0)
    max_win = Column(Float, nullable=False, default=0.0)
    max_loss = Column(Float, nullable=False, default=0.0)
    max_drawdown = Column(Float, nullable=False, default=0.0)
    sharpe_ratio = Column(Float, nullable=True)
    sortino_ratio = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=False, default=0.0)
    avg_trade_duration_hours = Column(Float, nullable=False, default=0.0)
    total_volume_traded = Column(Float, nullable=False, default=0.0)
    var_95 = Column(Float, nullable=True)
    max_consecutive_losses = Column(Integer, nullable=False, default=0)
    max_consecutive_wins = Column(Integer, nullable=False, default=0)
    additional_metrics = Column(JSON, nullable=True)

    strategy = relationship("Strategy", back_populates="strategy_performances")
    account = relationship("Account")
