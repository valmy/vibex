"""
Decision analytics service for performance tracking and insights.

Provides analytics and insights for trading decisions and their outcomes.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import and_, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..models.decision import Decision, DecisionResult
from .decision_repository import DecisionRepository


@dataclass
class DecisionMetrics:
    """Metrics for decision performance."""

    total_decisions: int
    validation_rate: float
    execution_rate: float
    avg_confidence: float
    avg_processing_time: float
    total_api_cost: float
    action_breakdown: Dict[str, int]
    error_rate: float


@dataclass
class StrategyMetrics:
    """Metrics for strategy performance."""

    strategy_id: str
    total_decisions: int
    executed_decisions: int
    closed_positions: int
    total_pnl: float
    win_rate: float
    avg_confidence: float
    avg_processing_time: float
    best_performing_symbol: Optional[str]
    worst_performing_symbol: Optional[str]


@dataclass
class TradingInsights:
    """Trading insights and recommendations."""

    most_profitable_action: str
    most_confident_decisions: List[str]
    common_validation_errors: List[str]
    performance_trend: str  # improving, declining, stable
    recommendations: List[str]


class DecisionAnalyticsService:
    """Service for decision analytics and performance tracking."""

    def __init__(self, db_session: AsyncSession):
        """Initialize analytics service."""
        self.db = db_session
        self.decision_repo = DecisionRepository(db_session)

    async def get_decision_metrics(
        self,
        account_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        strategy_id: Optional[str] = None,
    ) -> DecisionMetrics:
        """Get comprehensive decision metrics."""

        analytics = await self.decision_repo.get_decision_analytics(
            account_id=account_id, start_date=start_date, end_date=end_date, strategy_id=strategy_id
        )

        # Calculate error rate
        error_summary = await self.decision_repo.get_validation_errors_summary(
            account_id=account_id, start_date=start_date, end_date=end_date
        )

        total_errors = sum(error_summary.values())
        error_rate = (
            (total_errors / analytics["total_decisions"] * 100)
            if analytics["total_decisions"] > 0
            else 0
        )

        return DecisionMetrics(
            total_decisions=analytics["total_decisions"],
            validation_rate=analytics["validation_rate"],
            execution_rate=analytics["execution_rate"],
            avg_confidence=analytics["avg_confidence"],
            avg_processing_time=analytics["avg_processing_time"],
            total_api_cost=analytics["total_api_cost"],
            action_breakdown=analytics["action_breakdown"],
            error_rate=error_rate,
        )

    async def get_strategy_metrics(
        self,
        account_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[StrategyMetrics]:
        """Get metrics for all strategies used by an account."""

        performance_data = await self.decision_repo.get_performance_by_strategy(
            account_id=account_id, start_date=start_date, end_date=end_date
        )

        strategy_metrics = []

        for strategy_id, perf in performance_data.items():
            # Get symbol performance for this strategy
            symbol_performance = await self._get_symbol_performance_for_strategy(
                account_id, strategy_id, start_date, end_date
            )

            best_symbol = max(symbol_performance.items(), key=lambda x: x[1], default=(None, 0))[0]
            worst_symbol = min(symbol_performance.items(), key=lambda x: x[1], default=(None, 0))[0]

            metrics = StrategyMetrics(
                strategy_id=strategy_id,
                total_decisions=perf["total_decisions"],
                executed_decisions=perf["executed_decisions"],
                closed_positions=perf["closed_positions"],
                total_pnl=perf["total_pnl"],
                win_rate=perf["win_rate"],
                avg_confidence=perf["avg_confidence"],
                avg_processing_time=0.0,  # Would need to calculate from decisions
                best_performing_symbol=best_symbol,
                worst_performing_symbol=worst_symbol,
            )

            strategy_metrics.append(metrics)

        return strategy_metrics

    async def get_trading_insights(
        self, account_id: int, lookback_days: int = 30
    ) -> TradingInsights:
        """Generate trading insights and recommendations."""

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=lookback_days)

        # Get recent decisions
        decisions = await self.decision_repo.get_decisions_by_account(
            account_id=account_id, start_date=start_date, end_date=end_date, limit=1000
        )

        if not decisions:
            return TradingInsights(
                most_profitable_action="insufficient_data",
                most_confident_decisions=[],
                common_validation_errors=[],
                performance_trend="insufficient_data",
                recommendations=["Insufficient data for analysis"],
            )

        # Analyze most profitable action
        action_pnl = await self._calculate_action_pnl(account_id, start_date, end_date)
        most_profitable_action = max(action_pnl.items(), key=lambda x: x[1], default=("hold", 0))[0]

        # Find most confident decisions
        high_confidence_decisions = [
            f"{d.symbol} {d.action}"
            for d in decisions
            if d.confidence >= 80 and d.validation_passed
        ][:5]

        # Get common validation errors
        error_summary = await self.decision_repo.get_validation_errors_summary(
            account_id=account_id, start_date=start_date, end_date=end_date
        )
        common_errors = sorted(error_summary.items(), key=lambda x: x[1], reverse=True)[:3]
        common_error_messages = [error[0] for error in common_errors]

        # Determine performance trend
        performance_trend = await self._calculate_performance_trend(account_id, lookback_days)

        # Generate recommendations
        recommendations = await self._generate_recommendations(
            decisions, action_pnl, error_summary, performance_trend
        )

        return TradingInsights(
            most_profitable_action=most_profitable_action,
            most_confident_decisions=high_confidence_decisions,
            common_validation_errors=common_error_messages,
            performance_trend=performance_trend,
            recommendations=recommendations,
        )

    async def get_decision_heatmap(
        self, account_id: int, days: int = 30
    ) -> Dict[str, Dict[str, int]]:
        """Get decision heatmap by hour and day of week."""

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        result = await self.db.execute(
            text(
                """
                SELECT
                    EXTRACT(DOW FROM timestamp) as day_of_week,
                    EXTRACT(HOUR FROM timestamp) as hour_of_day,
                    COUNT(*) as decision_count
                FROM trading.decisions
                WHERE account_id = :account_id
                    AND timestamp >= :start_date
                    AND timestamp <= :end_date
                GROUP BY EXTRACT(DOW FROM timestamp), EXTRACT(HOUR FROM timestamp)
                ORDER BY day_of_week, hour_of_day
            """
            ),
            {"account_id": account_id, "start_date": start_date, "end_date": end_date},
        )

        heatmap = {}
        for row in result:
            day = int(row.day_of_week)
            hour = int(row.hour_of_day)
            count = int(row.decision_count)

            day_name = [
                "Sunday",
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
            ][day]

            if day_name not in heatmap:
                heatmap[day_name] = {}
            heatmap[day_name][f"{hour:02d}:00"] = count

        return heatmap

    async def get_model_performance_comparison(
        self,
        account_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Dict]:
        """Compare performance of different LLM models."""

        query = select(Decision).where(Decision.account_id == account_id)

        if start_date:
            query = query.where(Decision.timestamp >= start_date)
        if end_date:
            query = query.where(Decision.timestamp <= end_date)

        result = await self.db.execute(query)
        decisions = result.scalars().all()

        model_stats = {}

        for decision in decisions:
            model = decision.model_used

            if model not in model_stats:
                model_stats[model] = {
                    "total_decisions": 0,
                    "validation_rate": 0,
                    "avg_confidence": 0,
                    "avg_processing_time": 0,
                    "total_cost": 0,
                    "confidences": [],
                    "processing_times": [],
                    "validated_count": 0,
                }

            stats = model_stats[model]
            stats["total_decisions"] += 1
            stats["confidences"].append(decision.confidence)
            stats["processing_times"].append(decision.processing_time_ms)
            stats["total_cost"] += decision.api_cost or 0

            if decision.validation_passed:
                stats["validated_count"] += 1

        # Calculate averages
        for model, stats in model_stats.items():
            if stats["confidences"]:
                stats["avg_confidence"] = sum(stats["confidences"]) / len(stats["confidences"])
                stats["avg_processing_time"] = sum(stats["processing_times"]) / len(
                    stats["processing_times"]
                )
                stats["validation_rate"] = (
                    stats["validated_count"] / stats["total_decisions"]
                ) * 100

            # Clean up raw data
            del stats["confidences"]
            del stats["processing_times"]
            del stats["validated_count"]

        return model_stats

    async def _get_symbol_performance_for_strategy(
        self,
        account_id: int,
        strategy_id: str,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
    ) -> Dict[str, float]:
        """Get PnL by symbol for a specific strategy."""

        query = (
            select(Decision.symbol, func.sum(DecisionResult.realized_pnl))
            .join(DecisionResult, Decision.id == DecisionResult.decision_id)
            .where(
                and_(
                    Decision.account_id == account_id,
                    Decision.strategy_id == strategy_id,
                    DecisionResult.realized_pnl.isnot(None),
                )
            )
            .group_by(Decision.symbol)
        )

        if start_date:
            query = query.where(Decision.timestamp >= start_date)
        if end_date:
            query = query.where(Decision.timestamp <= end_date)

        result = await self.db.execute(query)

        return {symbol: float(pnl or 0) for symbol, pnl in result}

    async def _calculate_action_pnl(
        self, account_id: int, start_date: datetime, end_date: datetime
    ) -> Dict[str, float]:
        """Calculate PnL by action type."""

        query = (
            select(Decision.action, func.sum(DecisionResult.realized_pnl))
            .join(DecisionResult, Decision.id == DecisionResult.decision_id)
            .where(
                and_(
                    Decision.account_id == account_id,
                    Decision.timestamp >= start_date,
                    Decision.timestamp <= end_date,
                    DecisionResult.realized_pnl.isnot(None),
                )
            )
            .group_by(Decision.action)
        )

        result = await self.db.execute(query)
        return {action: float(pnl or 0) for action, pnl in result}

    async def _calculate_performance_trend(self, account_id: int, lookback_days: int) -> str:
        """Calculate performance trend over time."""

        # Split period into two halves
        end_date = datetime.now(timezone.utc)
        mid_date = end_date - timedelta(days=lookback_days // 2)
        start_date = end_date - timedelta(days=lookback_days)

        # Get PnL for each half
        first_half_pnl = await self._get_period_pnl(account_id, start_date, mid_date)
        second_half_pnl = await self._get_period_pnl(account_id, mid_date, end_date)

        if first_half_pnl == 0 and second_half_pnl == 0:
            return "stable"
        elif second_half_pnl > first_half_pnl * 1.1:  # 10% improvement
            return "improving"
        elif second_half_pnl < first_half_pnl * 0.9:  # 10% decline
            return "declining"
        else:
            return "stable"

    async def _get_period_pnl(
        self, account_id: int, start_date: datetime, end_date: datetime
    ) -> float:
        """Get total PnL for a period."""

        result = await self.db.execute(
            select(func.sum(DecisionResult.realized_pnl))
            .join(Decision, Decision.id == DecisionResult.decision_id)
            .where(
                and_(
                    Decision.account_id == account_id,
                    Decision.timestamp >= start_date,
                    Decision.timestamp <= end_date,
                    DecisionResult.realized_pnl.isnot(None),
                )
            )
        )

        return float(result.scalar() or 0)

    async def _generate_recommendations(
        self,
        decisions: List[Decision],
        action_pnl: Dict[str, float],
        error_summary: Dict[str, int],
        performance_trend: str,
    ) -> List[str]:
        """Generate trading recommendations based on analysis."""

        recommendations = []

        # Performance-based recommendations
        if performance_trend == "declining":
            recommendations.append(
                "Consider reviewing strategy parameters - performance is declining"
            )
        elif performance_trend == "improving":
            recommendations.append(
                "Current strategy is performing well - maintain current approach"
            )

        # Action-based recommendations
        if action_pnl:
            best_action = max(action_pnl.items(), key=lambda x: x[1])[0]
            worst_action = min(action_pnl.items(), key=lambda x: x[1])[0]

            if action_pnl[best_action] > 0:
                recommendations.append(f"Focus on {best_action} actions - they're most profitable")

            if action_pnl[worst_action] < -100:  # Significant losses
                recommendations.append(
                    f"Review {worst_action} strategy - causing significant losses"
                )

        # Error-based recommendations
        if error_summary:
            most_common_error = max(error_summary.items(), key=lambda x: x[1])[0]
            recommendations.append(f"Address validation issue: {most_common_error}")

        # Confidence-based recommendations
        avg_confidence = sum(d.confidence for d in decisions) / len(decisions) if decisions else 0
        if avg_confidence < 60:
            recommendations.append(
                "Low average confidence - consider adjusting strategy parameters"
            )
        elif avg_confidence > 85:
            recommendations.append("High confidence decisions - consider increasing position sizes")

        # Volume-based recommendations
        if len(decisions) < 10:
            recommendations.append("Low decision volume - consider more active strategy")
        elif len(decisions) > 100:
            recommendations.append("High decision volume - ensure quality over quantity")

        return recommendations[:5]  # Limit to top 5 recommendations
