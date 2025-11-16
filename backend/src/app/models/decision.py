"""
Decision model for storing LLM-generated trading decisions.

Stores trading decisions with their context and validation results.
"""

from datetime import datetime, timezone
from typing import Optional

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


class Decision(BaseModel):
    """Trading decision model for storing LLM-generated decisions.

    Supports both single-asset (legacy) and multi-asset decision structures.
    For multi-asset decisions, asset_decisions contains the list of per-asset decisions.
    """

    __tablename__ = "decisions"
    __table_args__ = (
        Index("idx_decision_account_symbol", "account_id", "symbol"),
        Index("idx_decision_timestamp", "timestamp"),
        Index("idx_decision_action", "action"),
        Index("idx_decision_strategy", "strategy_id"),
        {"schema": "trading"},
    )

    # Foreign key relationships
    account_id = Column(Integer, ForeignKey("trading.accounts.id"), nullable=False)
    strategy_id = Column(String(100), nullable=False, index=True)

    # Multi-asset decision fields
    asset_decisions = Column(JSON, nullable=True)  # List of AssetDecision objects
    portfolio_rationale = Column(Text, nullable=True)  # Overall portfolio strategy
    total_allocation_usd = Column(Float, nullable=True)  # Total allocation across all assets
    portfolio_risk_level = Column(String(10), nullable=True)  # Portfolio-wide risk level

    # Legacy single-asset decision fields (kept for backward compatibility)
    symbol = Column(String(20), nullable=True, index=True)  # Nullable for multi-asset decisions
    action = Column(
        String(20), nullable=True
    )  # buy, sell, hold, adjust_position, close_position, adjust_orders
    allocation_usd = Column(Float, nullable=True, default=0.0)

    # Price levels (legacy single-asset)
    tp_price = Column(Float, nullable=True)
    sl_price = Column(Float, nullable=True)

    # Decision metadata (legacy single-asset)
    exit_plan = Column(Text, nullable=True)
    rationale = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)  # 0-100
    risk_level = Column(String(10), nullable=True)  # low, medium, high
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Position and order adjustments (stored as JSON)
    position_adjustment = Column(JSON, nullable=True)
    order_adjustment = Column(JSON, nullable=True)

    # LLM metadata
    model_used = Column(String(100), nullable=False)
    api_cost = Column(Float, nullable=True)
    processing_time_ms = Column(Float, nullable=False)

    # Validation results
    validation_passed = Column(Boolean, nullable=False, default=False)
    validation_errors = Column(JSON, nullable=True)  # List of error messages
    validation_warnings = Column(JSON, nullable=True)  # List of warning messages

    # Context data (stored as JSON for flexibility)
    market_context = Column(JSON, nullable=False)
    account_context = Column(JSON, nullable=False)
    risk_metrics = Column(JSON, nullable=True)

    # Execution tracking
    executed = Column(Boolean, nullable=False, default=False)
    executed_at = Column(DateTime, nullable=True)
    execution_price = Column(Float, nullable=True)
    execution_errors = Column(JSON, nullable=True)

    # Relationships
    account = relationship("Account", back_populates="decisions")
    decision_results = relationship(
        "DecisionResult", back_populates="decision", cascade="all, delete-orphan"
    )

    def __repr__(self):
        """String representation."""
        return (
            f"<Decision(id={self.id}, account_id={self.account_id}, "
            f"symbol={self.symbol}, action={self.action}, "
            f"confidence={self.confidence})>"
        )

    @property
    def is_multi_asset(self) -> bool:
        """Check if this is a multi-asset decision."""
        return self.asset_decisions is not None and len(self.asset_decisions) > 0

    @property
    def is_trade_action(self) -> bool:
        """Check if decision involves actual trading."""
        if self.is_multi_asset:
            # Check if any asset decision involves trading
            return any(
                ad.get("action")
                in ["buy", "sell", "adjust_position", "close_position", "adjust_orders"]
                for ad in self.asset_decisions
            )
        return self.action in ["buy", "sell", "adjust_position", "close_position", "adjust_orders"]

    @property
    def requires_execution(self) -> bool:
        """Check if decision requires execution."""
        return self.is_trade_action and not self.executed and self.validation_passed

    def get_symbols(self) -> list[str]:
        """Get list of symbols in this decision."""
        if self.is_multi_asset:
            return [ad.get("asset") for ad in self.asset_decisions if ad.get("asset")]
        return [self.symbol] if self.symbol else []

    def get_allocation_percentage(self, account_balance: float) -> Optional[float]:
        """Calculate allocation as percentage of account balance."""
        if account_balance <= 0:
            return None
        return (self.allocation_usd / account_balance) * 100

    def get_risk_reward_ratio(self) -> Optional[float]:
        """Calculate risk/reward ratio if TP and SL are set."""
        if not (self.tp_price and self.sl_price and self.market_context):
            return None

        current_price = self.market_context.get("current_price")
        if not current_price:
            return None

        if self.action == "buy":
            potential_profit = self.tp_price - current_price
            potential_loss = current_price - self.sl_price
        elif self.action == "sell":
            potential_profit = current_price - self.tp_price
            potential_loss = self.sl_price - current_price
        else:
            return None

        if potential_loss <= 0:
            return None

        return potential_profit / potential_loss

    def mark_executed(self, execution_price: float, execution_errors: Optional[list] = None):
        """Mark decision as executed."""
        self.executed = True
        self.executed_at = datetime.now(timezone.utc)
        self.execution_price = execution_price
        if execution_errors:
            self.execution_errors = execution_errors


class DecisionResult(BaseModel):
    """Model for tracking decision outcomes and performance."""

    __tablename__ = "decision_results"
    __table_args__ = (
        Index("idx_decision_result_decision", "decision_id"),
        Index("idx_decision_result_outcome", "outcome"),
        Index("idx_decision_result_closed_at", "closed_at"),
        {"schema": "trading"},
    )

    # Foreign key relationships
    decision_id = Column(Integer, ForeignKey("trading.decisions.id"), nullable=False)

    # Outcome tracking
    outcome = Column(String(20), nullable=True)  # win, loss, breakeven, pending
    realized_pnl = Column(Float, nullable=True)
    unrealized_pnl = Column(Float, nullable=True)
    percentage_return = Column(Float, nullable=True)

    # Position tracking
    entry_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    position_size = Column(Float, nullable=True)

    # Timing
    opened_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    duration_hours = Column(Float, nullable=True)

    # Performance metrics
    max_favorable_excursion = Column(Float, nullable=True)  # Best unrealized profit
    max_adverse_excursion = Column(Float, nullable=True)  # Worst unrealized loss

    # Execution details
    slippage = Column(Float, nullable=True)
    fees_paid = Column(Float, nullable=True)

    # Analysis
    hit_tp = Column(Boolean, nullable=True)  # Hit take profit
    hit_sl = Column(Boolean, nullable=True)  # Hit stop loss
    manual_close = Column(Boolean, nullable=False, default=False)

    # Additional context
    market_conditions = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    decision = relationship("Decision", back_populates="decision_results")

    def __repr__(self):
        """String representation."""
        return (
            f"<DecisionResult(id={self.id}, decision_id={self.decision_id}, "
            f"outcome={self.outcome}, realized_pnl={self.realized_pnl})>"
        )

    @property
    def is_closed(self) -> bool:
        """Check if position is closed."""
        return self.closed_at is not None

    @property
    def is_profitable(self) -> bool:
        """Check if result is profitable."""
        if self.realized_pnl is not None:
            return self.realized_pnl > 0
        if self.unrealized_pnl is not None:
            return self.unrealized_pnl > 0
        return False

    def calculate_duration(self):
        """Calculate and update duration if both timestamps are available."""
        if self.opened_at and self.closed_at:
            duration = self.closed_at - self.opened_at
            self.duration_hours = duration.total_seconds() / 3600

    def update_unrealized_pnl(self, current_price: float):
        """Update unrealized PnL based on current price."""
        if not (self.entry_price and self.position_size):
            return

        if self.decision.action == "buy":
            self.unrealized_pnl = (current_price - self.entry_price) * self.position_size
        elif self.decision.action == "sell":
            self.unrealized_pnl = (self.entry_price - current_price) * self.position_size

        # Update max favorable/adverse excursion
        if self.unrealized_pnl > 0:
            if (
                self.max_favorable_excursion is None
                or self.unrealized_pnl > self.max_favorable_excursion
            ):
                self.max_favorable_excursion = self.unrealized_pnl
        else:
            if (
                self.max_adverse_excursion is None
                or self.unrealized_pnl < self.max_adverse_excursion
            ):
                self.max_adverse_excursion = self.unrealized_pnl

    def close_position(self, exit_price: float, fees: float = 0.0, manual: bool = False):
        """Close the position and calculate final results."""
        self.exit_price = exit_price
        self.closed_at = datetime.now(timezone.utc)
        self.fees_paid = fees
        self.manual_close = manual

        if self.entry_price and self.position_size:
            if self.decision.action == "buy":
                gross_pnl = (exit_price - self.entry_price) * self.position_size
            elif self.decision.action == "sell":
                gross_pnl = (self.entry_price - exit_price) * self.position_size
            else:
                gross_pnl = 0

            self.realized_pnl = gross_pnl - fees
            self.percentage_return = (
                self.realized_pnl / (self.entry_price * self.position_size)
            ) * 100

            # Determine outcome
            if self.realized_pnl > 0:
                self.outcome = "win"
            elif self.realized_pnl < 0:
                self.outcome = "loss"
            else:
                self.outcome = "breakeven"

            # Check if TP or SL was hit
            if self.decision.tp_price:
                if self.decision.action == "buy" and exit_price >= self.decision.tp_price:
                    self.hit_tp = True
                elif self.decision.action == "sell" and exit_price <= self.decision.tp_price:
                    self.hit_tp = True

            if self.decision.sl_price:
                if self.decision.action == "buy" and exit_price <= self.decision.sl_price:
                    self.hit_sl = True
                elif self.decision.action == "sell" and exit_price >= self.decision.sl_price:
                    self.hit_sl = True

        self.calculate_duration()
        self.unrealized_pnl = None  # Clear unrealized PnL as position is closed
