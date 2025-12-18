"""
Decision Repository for database persistence operations.

Handles CRUD operations for trading decisions with multi-asset support.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, func, select
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
                        ~Decision.executed,
                        Decision.validation_passed,
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

    async def get_decisions_by_account(
        self,
        account_id: int,
        limit: int = 100,
        offset: int = 0,
        symbol: Optional[str] = None,
        action: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        strategy_id: Optional[str] = None,
    ) -> List[Decision]:
        """
        Get decisions for an account with optional filters.

        Args:
            account_id: Account ID
            limit: Maximum number of decisions to return
            offset: Offset for pagination
            symbol: Optional symbol filter
            action: Optional action filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            strategy_id: Optional strategy filter

        Returns:
            List of Decision objects
        """
        async with self.session_factory() as session:
            try:
                query = select(Decision).where(Decision.account_id == account_id)

                if symbol:
                    query = query.where(Decision.symbol == symbol)
                if action:
                    query = query.where(Decision.action == action)
                if start_date:
                    query = query.where(Decision.timestamp >= start_date)
                if end_date:
                    query = query.where(Decision.timestamp <= end_date)
                if strategy_id:
                    query = query.where(Decision.strategy_id == strategy_id)

                query = query.order_by(desc(Decision.timestamp)).offset(offset).limit(limit)

                result = await session.execute(query)
                return list(result.scalars().all())

            except Exception as e:
                logger.error(f"Failed to get decisions for account {account_id}: {e}")
                raise

    async def get_recent_decisions(
        self, account_id: int, hours: int = 24, limit: int = 50
    ) -> List[Decision]:
        """
        Get recent decisions for an account.

        Args:
            account_id: Account ID
            hours: Number of hours to look back
            limit: Maximum number of decisions

        Returns:
            List of Decision objects
        """
        async with self.session_factory() as session:
            try:
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
                result = await session.execute(
                    select(Decision)
                    .where(
                        and_(Decision.account_id == account_id, Decision.timestamp >= cutoff_time)
                    )
                    .order_by(desc(Decision.timestamp))
                    .limit(limit)
                )
                return list(result.scalars().all())

            except Exception as e:
                logger.error(f"Failed to get recent decisions for account {account_id}: {e}")
                raise

    async def get_decision_analytics(
        self,
        account_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        strategy_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get analytics for decisions in a time period.

        Args:
            account_id: Account ID
            start_date: Optional start date
            end_date: Optional end date
            strategy_id: Optional strategy filter

        Returns:
            Dictionary with analytics data
        """
        async with self.session_factory() as session:
            try:
                query = select(Decision).where(Decision.account_id == account_id)

                if start_date:
                    query = query.where(Decision.timestamp >= start_date)
                if end_date:
                    query = query.where(Decision.timestamp <= end_date)
                if strategy_id:
                    query = query.where(Decision.strategy_id == strategy_id)

                result = await session.execute(query)
                decisions = result.scalars().all()

                if not decisions:
                    return {
                        "total_decisions": 0,
                        "validation_rate": 0.0,
                        "execution_rate": 0.0,
                        "action_breakdown": {},
                        "avg_confidence": 0.0,
                        "avg_processing_time": 0.0,
                        "total_api_cost": 0.0,
                    }

                total_decisions = len(decisions)
                validated_decisions = sum(1 for d in decisions if d.validation_passed)
                executed_decisions = sum(1 for d in decisions if d.executed)

                action_counts: Dict[str, int] = {}
                for decision in decisions:
                    action = decision.action
                    if action is not None:
                        action_counts[action] = action_counts.get(action, 0) + 1

                avg_confidence = (
                    sum(d.confidence for d in decisions if d.confidence is not None)
                    / total_decisions
                    if total_decisions > 0
                    else 0.0
                )
                avg_processing_time = (
                    sum(d.processing_time_ms for d in decisions if d.processing_time_ms is not None)
                    / total_decisions
                    if total_decisions > 0
                    else 0.0
                )
                total_api_cost = sum(d.api_cost or 0 for d in decisions)

                return {
                    "total_decisions": total_decisions,
                    "validation_rate": (validated_decisions / total_decisions) * 100,
                    "execution_rate": (
                        (executed_decisions / total_decisions) * 100 if total_decisions > 0 else 0
                    ),
                    "action_breakdown": action_counts,
                    "avg_confidence": avg_confidence,
                    "avg_processing_time": avg_processing_time,
                    "total_api_cost": total_api_cost,
                }

            except Exception as e:
                logger.error(f"Failed to get decision analytics for account {account_id}: {e}")
                raise

    async def get_performance_by_strategy(
        self,
        account_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get performance metrics grouped by strategy.

        Args:
            account_id: Account ID
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            Dictionary with strategy performance data
        """
        try:
            rows = await self._fetch_performance_rows(account_id, start_date, end_date)
            strategy_performance = self._aggregate_performance_data(rows)
            return self._calculate_final_metrics(strategy_performance)

        except Exception as e:
            logger.error(f"Failed to get performance by strategy for account {account_id}: {e}")
            raise

    async def _fetch_performance_rows(
        self,
        account_id: int,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
    ) -> List[Any]:
        """Fetch performance rows from database."""
        async with self.session_factory() as session:
            query = (
                select(Decision, DecisionResult)
                .outerjoin(DecisionResult, Decision.id == DecisionResult.decision_id)
                .where(Decision.account_id == account_id)
            )
            if start_date:
                query = query.where(Decision.timestamp >= start_date)
            if end_date:
                query = query.where(Decision.timestamp <= end_date)

            result = await session.execute(query)
            return list(result.all())

    def _aggregate_performance_data(self, rows: List[Any]) -> Dict[str, Any]:
        """Aggregate performance data from database rows."""
        strategy_performance: Dict[str, Any] = {}
        for decision, decision_result in rows:
            sid = decision.strategy_id
            if sid not in strategy_performance:
                strategy_performance[sid] = {
                    "total_decisions": 0,
                    "executed_decisions": 0,
                    "closed_positions": 0,
                    "total_pnl": 0.0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "avg_confidence": 0.0,
                    "confidences": [],
                }

            perf = strategy_performance[sid]
            perf["total_decisions"] += 1
            if decision.confidence is not None:
                perf["confidences"].append(decision.confidence)

            if decision.executed:
                perf["executed_decisions"] += 1

            if decision_result and decision_result.is_closed:
                self._update_closed_position_metrics(perf, decision_result)

        return strategy_performance

    def _update_closed_position_metrics(self, perf: Dict[str, Any], result: DecisionResult) -> None:
        """Update metrics for a closed position."""
        perf["closed_positions"] += 1
        if result.realized_pnl:
            perf["total_pnl"] += result.realized_pnl
            if result.realized_pnl > 0:
                perf["winning_trades"] += 1
            else:
                perf["losing_trades"] += 1

    def _calculate_final_metrics(self, strategy_performance: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate final metrics for each strategy."""
        for perf in strategy_performance.values():
            if perf["confidences"]:
                perf["avg_confidence"] = sum(perf["confidences"]) / len(perf["confidences"])
            del perf["confidences"]

            total_trades = perf["winning_trades"] + perf["losing_trades"]
            perf["win_rate"] = (
                (perf["winning_trades"] / total_trades * 100) if total_trades > 0 else 0
            )

        return strategy_performance

    async def get_validation_errors_summary(
        self,
        account_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """
        Get summary of validation errors.

        Args:
            account_id: Account ID
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            Dictionary mapping error messages to counts
        """
        async with self.session_factory() as session:
            try:
                query = select(Decision).where(
                    and_(
                        Decision.account_id == account_id,
                        ~Decision.validation_passed,
                        Decision.validation_errors.isnot(None),
                    )
                )

                if start_date:
                    query = query.where(Decision.timestamp >= start_date)
                if end_date:
                    query = query.where(Decision.timestamp <= end_date)

                result = await session.execute(query)
                failed_decisions = list(result.scalars().all())

                error_counts: Dict[str, int] = {}
                for decision in failed_decisions:
                    if decision.validation_errors:
                        for error in decision.validation_errors:
                            error_counts[error] = error_counts.get(error, 0) + 1

                return error_counts

            except Exception as e:
                logger.error(
                    f"Failed to get validation errors summary for account {account_id}: {e}"
                )
                raise

    async def save_decision_result(
        self,
        decision_id: int,
        entry_price: Optional[float] = None,
        position_size: Optional[float] = None,
        opened_at: Optional[datetime] = None,
    ) -> DecisionResult:
        """
        Save a decision result (position opening).

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
                decision_result = DecisionResult(
                    decision_id=decision_id,
                    entry_price=entry_price,
                    position_size=position_size,
                    opened_at=opened_at or datetime.now(timezone.utc),
                    outcome="pending",
                )

                session.add(decision_result)
                await session.commit()
                await session.refresh(decision_result)

                logger.info(f"Saved decision result for decision {decision_id}")
                return decision_result

            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to save decision result: {e}")
                raise

    async def update_decision_result(
        self,
        result_id: int,
        current_price: Optional[float] = None,
        exit_price: Optional[float] = None,
        realized_pnl: Optional[float] = None,
        fees_paid: Optional[float] = None,
        hit_tp: Optional[bool] = None,
        hit_sl: Optional[bool] = None,
        manual_close: bool = False,
        notes: Optional[str] = None,
    ) -> Optional[DecisionResult]:
        """
        Update a decision result with new information.

        Args:
            result_id: Result ID
            current_price: Current price for unrealized PnL
            exit_price: Exit price to close position
            realized_pnl: Realized PnL value
            fees_paid: Fees paid
            hit_tp: Whether take profit was hit
            hit_sl: Whether stop loss was hit
            manual_close: Whether manually closed
            notes: Notes

        Returns:
            Updated DecisionResult object or None if not found
        """
        async with self.session_factory() as session:
            try:
                result = await session.execute(
                    select(DecisionResult).where(DecisionResult.id == result_id)
                )
                decision_result = result.scalar_one_or_none()

                if not decision_result:
                    return None

                if current_price and not decision_result.is_closed:
                    decision_result.update_unrealized_pnl(current_price)

                if exit_price and not decision_result.is_closed:
                    decision_result.close_position(exit_price, fees_paid or 0.0, manual_close)

                if realized_pnl is not None:
                    decision_result.realized_pnl = realized_pnl
                if hit_tp is not None:
                    decision_result.hit_tp = hit_tp
                if hit_sl is not None:
                    decision_result.hit_sl = hit_sl
                if notes:
                    decision_result.notes = notes

                await session.commit()
                await session.refresh(decision_result)

                return decision_result

            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to update decision result {result_id}: {e}")
                raise

    async def cleanup_old_decisions(self, days_to_keep: int = 90) -> int:
        """
        Clean up old decisions beyond retention period.

        Args:
            days_to_keep: Number of days to retain

        Returns:
            Number of deleted decisions
        """
        async with self.session_factory() as session:
            try:
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

                # First delete associated decision results
                query_result = await session.execute(
                    select(DecisionResult).join(Decision).where(Decision.timestamp < cutoff_date)
                )
                old_results = query_result.scalars().all()

                for res in old_results:
                    await session.delete(res)

                # Then delete old decisions
                query_result = await session.execute(
                    select(Decision).where(Decision.timestamp < cutoff_date)
                )
                old_decisions = query_result.scalars().all()

                deleted_count = len(old_decisions)

                for decision in old_decisions:
                    await session.delete(decision)

                await session.commit()
                logger.info(f"Cleaned up {deleted_count} old decisions")
                return deleted_count

            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to cleanup old decisions: {e}")
                raise

    async def get_decision_count_by_period(self, account_id: int, period_hours: int = 24) -> int:
        """
        Get count of decisions in the last N hours.

        Args:
            account_id: Account ID
            period_hours: Number of hours to look back

        Returns:
            Count of decisions
        """
        async with self.session_factory() as session:
            try:
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=period_hours)
                result = await session.execute(
                    select(func.count(Decision.id)).where(
                        and_(
                            Decision.account_id == account_id,
                            Decision.timestamp >= cutoff_time,
                        )
                    )
                )
                return result.scalar() or 0

            except Exception as e:
                logger.error(f"Failed to get decision count for account {account_id}: {e}")
                raise
