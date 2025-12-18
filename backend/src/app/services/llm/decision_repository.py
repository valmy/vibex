"""
Decision Repository for database persistence operations.

Handles CRUD operations for trading decisions with multi-asset support.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from ...core.logging import get_logger
from ...models.decision import Decision, DecisionResult
from ...schemas.trading_decision import TradingDecision

logger = get_logger(__name__)


class DecisionRepository:
    """Repository for decision database operations."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        """Initialize repository with database session factory.

        Args:
            session_factory: Async session factory for creating database sessions.
        """
        self.session_factory = session_factory

    async def save_decision(
        self,
        account_id: int,
        strategy_id: str,
        trading_decision: TradingDecision,
        model_used: str,
        processing_time_ms: float,
        validation_passed: bool,
        validation_errors: Optional[List[str]] = None,
        validation_warnings: Optional[List[str]] = None,
        market_context: Optional[Dict[str, Any]] = None,
        account_context: Optional[Dict[str, Any]] = None,
        risk_metrics: Optional[Dict[str, Any]] = None,
        api_cost: Optional[float] = None,
    ) -> Decision:
        """
        Save a trading decision to the database.

        Args:
            account_id: Account ID
            strategy_id: Strategy ID
            trading_decision: TradingDecision object
            model_used: LLM model used
            processing_time_ms: Processing time in milliseconds
            validation_passed: Whether validation passed
            validation_errors: List of validation errors
            validation_warnings: List of validation warnings
            market_context: Market context data
            account_context: Account context data
            risk_metrics: Risk metrics data
            api_cost: API cost for this decision

        Returns:
            Saved Decision object
        """
        async with self.session_factory() as session:
            try:
                # Convert timezone-aware timestamp to naive UTC for database storage
                timestamp = trading_decision.timestamp
                if timestamp.tzinfo is not None:
                    timestamp = timestamp.replace(tzinfo=None)

                # Convert TradingDecision to database model
                decision = Decision(
                    account_id=account_id,
                    strategy_id=strategy_id,
                    # Multi-asset fields
                    asset_decisions=[ad.model_dump() for ad in trading_decision.decisions],
                    portfolio_rationale=trading_decision.portfolio_rationale,
                    total_allocation_usd=trading_decision.total_allocation_usd,
                    portfolio_risk_level=trading_decision.portfolio_risk_level,
                    # Legacy fields (set to None for multi-asset decisions)
                    symbol=None,
                    action=None,
                    allocation_usd=None,
                    tp_price=None,
                    sl_price=None,
                    exit_plan=None,
                    rationale=None,
                    confidence=None,
                    risk_level=None,
                    # Metadata
                    timestamp=timestamp,
                    model_used=model_used,
                    api_cost=api_cost,
                    processing_time_ms=processing_time_ms,
                    # Validation
                    validation_passed=validation_passed,
                    validation_errors=validation_errors,
                    validation_warnings=validation_warnings,
                    # Context
                    market_context=market_context or {},
                    account_context=account_context or {},
                    risk_metrics=risk_metrics,
                    # Execution
                    executed=False,
                )

                session.add(decision)
                await session.commit()
                await session.refresh(decision)

                logger.info(
                    f"Saved multi-asset decision {decision.id} for account {account_id} "
                    f"with {len(trading_decision.decisions)} asset decisions"
                )

                return decision

            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to save decision: {e}")
                raise

    async def get_decision_by_id(self, decision_id: int) -> Optional[Decision]:
        """
        Get a decision by ID.

        Args:
            decision_id: Decision ID

        Returns:
            Decision object or None if not found
        """
        async with self.session_factory() as session:
            try:
                result = await session.execute(
                    select(Decision)
                    .where(Decision.id == decision_id)
                    .options(selectinload(Decision.decision_results))
                )
                return result.scalar_one_or_none()
            except Exception as e:
                logger.error(f"Failed to get decision {decision_id}: {e}")
                raise

    async def get_decision_history(
        self,
        account_id: int,
        limit: int = 100,
        symbol: Optional[str] = None,
        offset: int = 0,
    ) -> List[Decision]:
        """
        Get decision history for an account.

        Args:
            account_id: Account ID
            limit: Maximum number of decisions to return
            symbol: Optional symbol filter
            offset: Offset for pagination

        Returns:
            List of Decision objects
        """
        async with self.session_factory() as session:
            try:
                query = (
                    select(Decision)
                    .where(Decision.account_id == account_id)
                    .order_by(Decision.timestamp.desc())
                    .limit(limit)
                    .offset(offset)
                    .options(selectinload(Decision.decision_results))
                )

                # If symbol filter is provided, we need to filter decisions that contain this symbol
                # For multi-asset decisions, check if symbol is in asset_decisions
                # For legacy single-asset decisions, check the symbol field
                if symbol:
                    # Note: This requires PostgreSQL JSON operators
                    # We'll filter in Python for now, but this should be optimized with proper SQL
                    result = await session.execute(query)
                    all_decisions = result.scalars().all()

                    # Filter decisions that contain the symbol
                    filtered_decisions = []
                    for decision in all_decisions:
                        if decision.is_multi_asset:
                            # Check if symbol is in any asset decision
                            if decision.asset_decisions:  # Check if asset_decisions is not None
                                if any(
                                    ad.get("asset") == symbol for ad in decision.asset_decisions
                                ):
                                    filtered_decisions.append(decision)
                        elif decision.symbol == symbol:
                            # Legacy single-asset decision
                            filtered_decisions.append(decision)

                    return filtered_decisions[:limit]
                else:
                    result = await session.execute(query)
                    return list(result.scalars().all())

            except Exception as e:
                logger.error(f"Failed to get decision history for account {account_id}: {e}")
                raise

    async def mark_decision_executed(
        self,
        decision_id: int,
        execution_price: float,
        execution_errors: Optional[List[str]] = None,
    ) -> Decision:
        """
        Mark a decision as executed.

        Args:
            decision_id: Decision ID
            execution_price: Execution price
            execution_errors: Optional execution errors

        Returns:
            Updated Decision object
        """
        async with self.session_factory() as session:
            try:
                # Fetch decision within this session
                result = await session.execute(
                    select(Decision)
                    .where(Decision.id == decision_id)
                    .options(selectinload(Decision.decision_results))
                )
                decision = result.scalar_one_or_none()

                if not decision:
                    raise ValueError(f"Decision {decision_id} not found")

                decision.mark_executed(execution_price, execution_errors)

                await session.commit()
                await session.refresh(decision)

                logger.info(f"Marked decision {decision_id} as executed")

                return decision

            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to mark decision {decision_id} as executed: {e}")
                raise

    async def create_decision_result(
        self,
        decision_id: int,
        entry_price: float,
        position_size: float,
        opened_at: Optional[datetime] = None,
    ) -> DecisionResult:
        """
        Create a decision result for tracking outcomes.

        Args:
            decision_id: Decision ID
            entry_price: Entry price
            position_size: Position size
            opened_at: Position open timestamp

        Returns:
            Created DecisionResult object
        """
        async with self.session_factory() as session:
            try:
                result = DecisionResult(
                    decision_id=decision_id,
                    entry_price=entry_price,
                    position_size=position_size,
                    opened_at=opened_at or datetime.utcnow(),
                    outcome="pending",
                )

                session.add(result)
                await session.commit()
                await session.refresh(result)

                logger.info(f"Created decision result for decision {decision_id}")

                return result

            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to create decision result: {e}")
                raise

    async def get_pending_decisions(self, account_id: int) -> List[Decision]:
        """
        Get pending decisions that require execution.

        Args:
            account_id: Account ID

        Returns:
            List of pending Decision objects
        """
        async with self.session_factory() as session:
            try:
                result = await session.execute(
                    select(Decision)
                    .where(
                        Decision.account_id == account_id,
                        Decision.executed == False,  # noqa: E712
                        Decision.validation_passed == True,  # noqa: E712
                    )
                    .order_by(Decision.timestamp.desc())
                )
                return list(result.scalars().all())

            except Exception as e:
                logger.error(f"Failed to get pending decisions for account {account_id}: {e}")
                raise

    async def get_decisions_by_strategy(
        self,
        strategy_id: str,
        limit: int = 100,
    ) -> List[Decision]:
        """
        Get decisions for a specific strategy.

        Args:
            strategy_id: Strategy ID
            limit: Maximum number of decisions to return

        Returns:
            List of Decision objects
        """
        async with self.session_factory() as session:
            try:
                result = await session.execute(
                    select(Decision)
                    .where(Decision.strategy_id == strategy_id)
                    .order_by(Decision.timestamp.desc())
                    .limit(limit)
                    .options(selectinload(Decision.decision_results))
                )
                return list(result.scalars().all())

            except Exception as e:
                logger.error(f"Failed to get decisions for strategy {strategy_id}: {e}")
                raise
