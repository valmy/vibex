"""
Decision repository for database operations.

Handles persistence and retrieval of trading decisions and results.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from ..models.decision import Decision, DecisionResult
from ..schemas.trading_decision import TradingDecision


class DecisionRepository:
    """Repository for decision-related database operations."""

    def __init__(self, db_session: AsyncSession):
        """Initialize repository with database session."""
        self.db = db_session

    async def save_decision(
        self,
        decision: TradingDecision,
        account_id: int,
        strategy_id: str,
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
        """Save a trading decision to the database."""

        # Handle multi-asset decisions by storing the list of asset decisions
        asset_decisions_list = (
            [ad.dict() for ad in decision.decisions]
            if hasattr(decision, "decisions") and decision.decisions
            else None
        )

        # For backward compatibility, extract first asset decision for single-asset fields
        first_asset_decision = (
            decision.decisions[0] if hasattr(decision, "decisions") and decision.decisions else None
        )

        # For multi-asset decisions, we'll use the first asset's adjustments as the primary ones
        # or use the first non-None adjustment we find
        position_adjustment_dict = None
        order_adjustment_dict = None

        if hasattr(decision, "decisions") and decision.decisions:
            # Find first asset with position adjustment
            for asset_dec in decision.decisions:
                if asset_dec.position_adjustment:
                    position_adjustment_dict = asset_dec.position_adjustment.dict()
                    break
            # Find first asset with order adjustment
            for asset_dec in decision.decisions:
                if asset_dec.order_adjustment:
                    order_adjustment_dict = asset_dec.order_adjustment.dict()
                    break

        db_decision = Decision(
            account_id=account_id,
            strategy_id=strategy_id,
            asset_decisions=asset_decisions_list,
            portfolio_rationale=decision.portfolio_rationale
            if hasattr(decision, "portfolio_rationale")
            else None,
            total_allocation_usd=decision.total_allocation_usd
            if hasattr(decision, "total_allocation_usd")
            else 0.0,
            portfolio_risk_level=decision.portfolio_risk_level
            if hasattr(decision, "portfolio_risk_level")
            else None,
            # Legacy single-asset fields (from first decision if available)
            symbol=first_asset_decision.asset if first_asset_decision else None,
            action=first_asset_decision.action if first_asset_decision else None,
            allocation_usd=first_asset_decision.allocation_usd if first_asset_decision else 0.0,
            tp_price=first_asset_decision.tp_price if first_asset_decision else None,
            sl_price=first_asset_decision.sl_price if first_asset_decision else None,
            exit_plan=first_asset_decision.exit_plan if first_asset_decision else None,
            rationale=first_asset_decision.rationale if first_asset_decision else None,
            confidence=first_asset_decision.confidence if first_asset_decision else None,
            risk_level=first_asset_decision.risk_level if first_asset_decision else None,
            timestamp=decision.timestamp if hasattr(decision, "timestamp") else datetime.utcnow(),
            position_adjustment=position_adjustment_dict,
            order_adjustment=order_adjustment_dict,
            model_used=model_used,
            api_cost=api_cost,
            processing_time_ms=processing_time_ms,
            validation_passed=validation_passed,
            validation_errors=validation_errors,
            validation_warnings=validation_warnings,
            market_context=market_context or {},
            account_context=account_context or {},
            risk_metrics=risk_metrics or {},
        )

        self.db.add(db_decision)
        await self.db.commit()
        await self.db.refresh(db_decision)

        return db_decision

    async def get_decision_by_id(self, decision_id: int) -> Optional[Decision]:
        """Get a decision by its ID."""
        result = await self.db.execute(
            select(Decision)
            .options(selectinload(Decision.decision_results))
            .where(Decision.id == decision_id)
        )
        return result.scalar_one_or_none()

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
        """Get decisions for an account with optional filters."""

        query = select(Decision).where(Decision.account_id == account_id)

        # Apply filters
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

        # Order by timestamp descending and apply pagination
        query = query.order_by(desc(Decision.timestamp)).offset(offset).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_recent_decisions(
        self, account_id: int, hours: int = 24, limit: int = 50
    ) -> List[Decision]:
        """Get recent decisions for an account."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        result = await self.db.execute(
            select(Decision)
            .where(and_(Decision.account_id == account_id, Decision.timestamp >= cutoff_time))
            .order_by(desc(Decision.timestamp))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_pending_executions(self, account_id: Optional[int] = None) -> List[Decision]:
        """Get decisions that require execution."""
        query = select(Decision).where(
            and_(
                Decision.validation_passed,
                ~Decision.executed,
                Decision.action.in_(
                    ["buy", "sell", "adjust_position", "close_position", "adjust_orders"]
                ),
            )
        )

        if account_id:
            query = query.where(Decision.account_id == account_id)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def mark_decision_executed(
        self, decision_id: int, execution_price: float, execution_errors: Optional[List[str]] = None
    ) -> bool:
        """Mark a decision as executed."""
        result = await self.db.execute(select(Decision).where(Decision.id == decision_id))
        decision = result.scalar_one_or_none()

        if not decision:
            return False

        decision.mark_executed(execution_price, execution_errors)
        await self.db.commit()
        return True

    async def save_decision_result(
        self,
        decision_id: int,
        entry_price: Optional[float] = None,
        position_size: Optional[float] = None,
        opened_at: Optional[datetime] = None,
    ) -> DecisionResult:
        """Save a decision result (position opening)."""

        decision_result = DecisionResult(
            decision_id=decision_id,
            entry_price=entry_price,
            position_size=position_size,
            opened_at=opened_at or datetime.now(timezone.utc),
            outcome="pending",
        )

        self.db.add(decision_result)
        await self.db.commit()
        await self.db.refresh(decision_result)

        return decision_result

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
        """Update a decision result with new information."""

        result = await self.db.execute(select(DecisionResult).where(DecisionResult.id == result_id))
        decision_result = result.scalar_one_or_none()

        if not decision_result:
            return None

        # Update unrealized PnL if current price provided
        if current_price and not decision_result.is_closed:
            decision_result.update_unrealized_pnl(current_price)

        # Close position if exit price provided
        if exit_price and not decision_result.is_closed:
            decision_result.close_position(exit_price, fees_paid or 0.0, manual_close)

        # Update other fields
        if realized_pnl is not None:
            decision_result.realized_pnl = realized_pnl
        if hit_tp is not None:
            decision_result.hit_tp = hit_tp
        if hit_sl is not None:
            decision_result.hit_sl = hit_sl
        if notes:
            decision_result.notes = notes

        await self.db.commit()
        await self.db.refresh(decision_result)

        return decision_result

    async def get_decision_analytics(
        self,
        account_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        strategy_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get analytics for decisions in a time period."""

        # Base query
        query = select(Decision).where(Decision.account_id == account_id)

        if start_date:
            query = query.where(Decision.timestamp >= start_date)
        if end_date:
            query = query.where(Decision.timestamp <= end_date)
        if strategy_id:
            query = query.where(Decision.strategy_id == strategy_id)

        result = await self.db.execute(query)
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

        # Calculate analytics
        total_decisions = len(decisions)
        validated_decisions = sum(1 for d in decisions if d.validation_passed)
        executed_decisions = sum(1 for d in decisions if d.executed)

        # Action breakdown
        action_counts: Dict[str, int] = {}
        for decision in decisions:
            action = decision.action
            if action is not None:
                action_counts[action] = action_counts.get(action, 0) + 1

        # Averages
        avg_confidence = (
            sum(d.confidence for d in decisions if d.confidence is not None) / total_decisions
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

    async def get_performance_by_strategy(
        self,
        account_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        rows = await self._fetch_decision_results(account_id, start_date, end_date)
        strategy_performance = self._group_results_by_strategy(rows)
        self._calculate_strategy_averages(strategy_performance)
        return strategy_performance

    async def _fetch_decision_results(
        self, account_id: int, start_date: Optional[datetime], end_date: Optional[datetime]
    ) -> List[Any]:
        query = (
            select(Decision, DecisionResult)
            .outerjoin(DecisionResult, Decision.id == DecisionResult.decision_id)
            .where(Decision.account_id == account_id)
        )
        if start_date:
            query = query.where(Decision.timestamp >= start_date)
        if end_date:
            query = query.where(Decision.timestamp <= end_date)
        result = await self.db.execute(query)
        return list(result.all())

    def _group_results_by_strategy(self, rows: List[Any]) -> Dict[str, Any]:
        strategy_performance = {}
        for decision, decision_result in rows:
            strategy_id = decision.strategy_id
            if strategy_id not in strategy_performance:
                strategy_performance[strategy_id] = self._initialize_performance_dict()
            perf = strategy_performance[strategy_id]
            perf["total_decisions"] += 1
            perf["confidences"].append(decision.confidence)
            if decision.executed:
                perf["executed_decisions"] += 1
            if decision_result and decision_result.is_closed:
                self._update_performance_from_result(perf, decision_result)
        return strategy_performance

    def _initialize_performance_dict(self) -> Dict[str, Any]:
        return {
            "total_decisions": 0,
            "executed_decisions": 0,
            "closed_positions": 0,
            "total_pnl": 0.0,
            "winning_trades": 0,
            "losing_trades": 0,
            "avg_confidence": 0.0,
            "confidences": [],
        }

    def _update_performance_from_result(self, perf: Dict[str, Any], decision_result: Any) -> None:
        perf["closed_positions"] += 1
        if decision_result.realized_pnl:
            perf["total_pnl"] += decision_result.realized_pnl
            if decision_result.realized_pnl > 0:
                perf["winning_trades"] += 1
            else:
                perf["losing_trades"] += 1

    def _calculate_strategy_averages(self, strategy_performance: Dict[str, Any]) -> None:
        for perf in strategy_performance.values():
            if perf["confidences"]:
                perf["avg_confidence"] = sum(perf["confidences"]) / len(perf["confidences"])
            del perf["confidences"]
            total_trades = perf["winning_trades"] + perf["losing_trades"]
            perf["win_rate"] = (
                (perf["winning_trades"] / total_trades * 100) if total_trades > 0 else 0
            )

    async def cleanup_old_decisions(self, days_to_keep: int = 90) -> int:
        """Clean up old decisions beyond retention period."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

        # First, delete associated decision results
        query_result = await self.db.execute(
            select(DecisionResult).join(Decision).where(Decision.timestamp < cutoff_date)
        )
        old_results = query_result.scalars().all()

        for result in old_results:
            await self.db.delete(result)

        # Then delete old decisions
        query_result = await self.db.execute(
            select(Decision).where(Decision.timestamp < cutoff_date)
        )
        old_decisions = query_result.scalars().all()

        deleted_count = len(old_decisions)

        for decision in old_decisions:
            await self.db.delete(decision)

        await self.db.commit()
        return deleted_count

    async def get_decision_count_by_period(self, account_id: int, period_hours: int = 24) -> int:
        """Get count of decisions in the last N hours."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=period_hours)

        result = await self.db.execute(
            select(func.count(Decision.id)).where(
                and_(Decision.account_id == account_id, Decision.timestamp >= cutoff_time)
            )
        )
        return result.scalar() or 0

    async def get_validation_errors_summary(
        self,
        account_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """Get summary of validation errors."""

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

        result = await self.db.execute(query)
        failed_decisions = list(result.scalars().all())

        error_counts: Dict[str, int] = {}
        for decision in failed_decisions:
            if decision.validation_errors:
                for error in decision.validation_errors:
                    error_counts[error] = error_counts.get(error, 0) + 1

        return error_counts
