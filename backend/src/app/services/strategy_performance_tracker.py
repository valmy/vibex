"""
Strategy performance tracking service.

Tracks and analyzes strategy performance metrics, comparisons, and alerts.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..models.decision import Decision, DecisionResult
from ..models.strategy import (
    Strategy,
    StrategyAssignment,
)
from ..models.strategy import (
    StrategyPerformance as StrategyPerformanceModel,
)
from ..schemas.trading_decision import (
    StrategyComparison,
)
from ..schemas.trading_decision import (
    StrategyPerformance as StrategyPerformanceSchema,
)


@dataclass
class PerformanceAlert:
    """Performance alert data."""

    strategy_id: str
    account_id: int
    alert_type: str
    severity: str
    message: str
    threshold_value: Optional[float]
    current_value: Optional[float]


@dataclass
class StrategyRanking:
    """Strategy ranking data."""

    strategy_id: str
    strategy_name: str
    rank: int
    score: float
    total_pnl: float
    win_rate: float
    sharpe_ratio: Optional[float]
    max_drawdown: float


class StrategyPerformanceModelTracker:
    """Service for tracking and analyzing strategy performance."""

    def __init__(self, db_session: AsyncSession):
        """Initialize performance tracker."""
        self.db = db_session

    async def update_strategy_performance(
        self, strategy_id: int, account_id: Optional[int] = None, period_days: int = 30
    ) -> StrategyPerformanceModel:
        """Update strategy performance metrics for a given period."""

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=period_days)

        # Get all decisions for this strategy in the period
        query = (
            select(Decision, DecisionResult)
            .outerjoin(DecisionResult, Decision.id == DecisionResult.decision_id)
            .where(
                and_(
                    Decision.strategy_id == str(strategy_id),
                    Decision.timestamp >= start_date,
                    Decision.timestamp <= end_date,
                )
            )
        )

        if account_id:
            query = query.where(Decision.account_id == account_id)

        result = await self.db.execute(query)
        decision_results = result.all()

        if not decision_results:
            # Create empty performance record
            return await self._create_empty_performance_record(
                strategy_id, account_id, start_date, end_date, period_days
            )

        # Calculate performance metrics
        metrics = self._calculate_performance_metrics([tuple(row) for row in decision_results])

        # Check if performance record exists
        existing_perf = await self._get_existing_performance_record(
            strategy_id, account_id, start_date, end_date
        )

        if existing_perf:
            # Update existing record
            await self._update_performance_record(
                existing_perf, metrics, [tuple(row) for row in decision_results]
            )
            performance = existing_perf
        else:
            # Create new record
            performance = await self._create_performance_record(
                strategy_id,
                account_id,
                start_date,
                end_date,
                period_days,
                metrics,
                [tuple(row) for row in decision_results],
            )

        await self.db.commit()
        await self.db.refresh(performance)

        return performance

    async def get_strategy_performance(
        self, strategy_id: int, account_id: Optional[int] = None, period_days: int = 30
    ) -> Optional[StrategyPerformanceModel]:
        """Get strategy performance for a specific period."""

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=period_days)

        query = select(StrategyPerformanceModel).where(
            and_(
                StrategyPerformanceModel.strategy_id == strategy_id,
                StrategyPerformanceModel.period_start >= start_date,
                StrategyPerformanceModel.period_end <= end_date,
            )
        )

        if account_id:
            query = query.where(StrategyPerformanceModel.account_id == account_id)
        else:
            query = query.where(StrategyPerformanceModel.account_id.is_(None))

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def compare_strategies(
        self,
        strategy_ids: List[int],
        account_id: Optional[int] = None,
        period_days: int = 30,
        ranking_criteria: str = "sharpe_ratio",
    ) -> StrategyComparison:
        """Compare multiple strategies and rank them."""

        strategy_performances = []

        for strategy_id in strategy_ids:
            # Update performance first
            perf = await self.update_strategy_performance(int(strategy_id), account_id, period_days)
            strategy_performances.append(perf)

        # Convert model performance objects to schema objects for comparison
        # Convert model performance objects to schema objects for comparison
        schema_performances: list[StrategyPerformanceSchema] = []
        for perf in strategy_performances:
            # Convert to schema object (note: schema expects different field names)
            schema_perf = StrategyPerformanceSchema(
                strategy_id=str(perf.strategy_id),
                total_trades=perf.total_trades,
                winning_trades=perf.winning_trades,
                losing_trades=perf.losing_trades,
                win_rate=perf.win_rate,
                total_pnl=perf.total_pnl,
                avg_win=perf.avg_win,
                avg_loss=perf.avg_loss,
                max_win=perf.max_win,
                max_loss=perf.max_loss,
                max_drawdown=perf.max_drawdown,
                sharpe_ratio=perf.sharpe_ratio,
                sortino_ratio=perf.sortino_ratio,
                profit_factor=perf.profit_factor,
                avg_trade_duration_hours=perf.avg_trade_duration_hours,
                total_volume_traded=perf.total_volume_traded,
                total_fees_paid=perf.total_fees_paid,
                total_funding_paid=perf.total_funding_paid,
                total_liquidations=perf.total_liquidations,
                start_date=perf.period_start,
                end_date=perf.period_end,
                period_days=perf.period_days,
            )
            schema_performances.append(schema_perf)

        # Rank strategies based on criteria
        rankings = self._rank_strategies(strategy_performances, ranking_criteria)

        # Get best performing strategy
        best_strategy = rankings[0] if rankings else None
        best_strategy_id = str(best_strategy.strategy_id) if best_strategy else ""

        return StrategyComparison(
            strategies=schema_performances,
            comparison_period_days=period_days,
            best_performing_strategy=best_strategy_id,
            ranking_criteria=ranking_criteria,  # type: ignore
            timestamp=datetime.now(timezone.utc),
        )

    async def get_strategy_rankings(
        self,
        account_id: Optional[int] = None,
        period_days: int = 30,
        ranking_criteria: str = "total_pnl",
    ) -> List[StrategyRanking]:
        """Get ranked list of all strategies."""

        # Get all active strategies
        result = await self.db.execute(select(Strategy).where(Strategy.is_active))
        strategies = result.scalars().all()

        rankings = []

        for strategy in strategies:
            # Get or update performance
            perf = await self.update_strategy_performance(int(strategy.id), account_id, period_days)

            # Calculate ranking score based on criteria
            score = self._calculate_ranking_score(perf, ranking_criteria)

            ranking = StrategyRanking(
                strategy_id=strategy.strategy_id,
                strategy_name=strategy.strategy_name,
                rank=0,  # Will be set after sorting
                score=score,
                total_pnl=perf.total_pnl,
                win_rate=perf.win_rate,
                sharpe_ratio=perf.sharpe_ratio,
                max_drawdown=perf.max_drawdown,
            )

            rankings.append(ranking)

        # Sort by score and assign ranks
        rankings.sort(key=lambda x: x.score, reverse=True)
        for i, ranking in enumerate(rankings):
            ranking.rank = i + 1

        return rankings

    async def check_performance_alerts(
        self, account_id: Optional[int] = None, lookback_days: int = 7
    ) -> List[PerformanceAlert]:
        """Check for performance alerts that need attention."""

        alerts = []

        # Get recent strategy performances
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=lookback_days)

        query = select(StrategyPerformanceModel).where(
            StrategyPerformanceModel.period_end >= start_date
        )

        if account_id:
            query = query.where(StrategyPerformanceModel.account_id == account_id)

        result = await self.db.execute(query)
        performances = result.scalars().all()

        for perf in performances:
            # Check various alert conditions
            strategy_alerts = await self._check_strategy_alerts(perf)
            alerts.extend(strategy_alerts)

        return alerts

    async def get_performance_trends(
        self,
        strategy_id: int,
        account_id: Optional[int] = None,
        periods: int = 12,
        period_days: int = 7,
    ) -> List[Dict[str, Any]]:
        """Get performance trends over multiple periods."""

        trends = []

        for i in range(periods):
            end_date = datetime.now(timezone.utc) - timedelta(days=i * period_days)
            start_date = end_date - timedelta(days=period_days)

            # Get performance for this period
            query = select(StrategyPerformanceModel).where(
                and_(
                    StrategyPerformanceModel.strategy_id == strategy_id,
                    StrategyPerformanceModel.period_start >= start_date,
                    StrategyPerformanceModel.period_end <= end_date,
                )
            )

            if account_id:
                query = query.where(StrategyPerformanceModel.account_id == account_id)

            result = await self.db.execute(query)
            perf = result.scalar_one_or_none()

            if perf:
                trends.append(
                    {
                        "period_start": perf.period_start,
                        "period_end": perf.period_end,
                        "total_pnl": perf.total_pnl,
                        "win_rate": perf.win_rate,
                        "total_trades": perf.total_trades,
                        "sharpe_ratio": perf.sharpe_ratio,
                        "max_drawdown": perf.max_drawdown,
                    }
                )

        return list(reversed(trends))  # Chronological order

    async def update_all_strategy_performances(self, period_days: int = 30) -> Dict[str, int]:
        """Update performance metrics for all active strategies."""

        # Get all active strategies
        result = await self.db.execute(select(Strategy).where(Strategy.is_active))
        strategies = result.scalars().all()

        # Get all accounts with strategy assignments
        result = await self.db.execute(
            select(StrategyAssignment.account_id).distinct().where(StrategyAssignment.is_active)
        )
        account_ids = [row[0] for row in result]

        updated_count = 0
        error_count = 0

        # Update performance for each strategy-account combination
        for strategy in strategies:
            try:
                # Update aggregate performance (all accounts)
                await self.update_strategy_performance(int(strategy.id), None, period_days)
                updated_count += 1

                # Update per-account performance
                for account_id in account_ids:
                    await self.update_strategy_performance(
                        int(strategy.id), account_id, period_days
                    )
                    updated_count += 1

            except Exception as e:
                error_count += 1
                # Log error but continue with other strategies
                print(f"Error updating performance for strategy {strategy.strategy_id}: {e}")

        return {
            "updated_count": updated_count,
            "error_count": error_count,
            "total_strategies": len(strategies),
        }

    def _calculate_performance_metrics(
        self, decision_results: List[Tuple[Decision, Optional[DecisionResult]]]
    ) -> Dict[str, Any]:
        """Calculate performance metrics from decision results."""

        decisions = [dr[0] for dr in decision_results]
        results = [dr[1] for dr in decision_results if dr[1] is not None]
        closed_results = [r for r in results if r.is_closed]

        # Basic counts
        total_trades: int = len(decisions)

        if not closed_results:
            return {
                "total_trades": total_trades,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "max_win": 0.0,
                "max_loss": 0.0,
                "max_drawdown": 0.0,
                "profit_factor": 0.0,
                "avg_trade_duration_hours": 0.0,
                "total_volume_traded": 0.0,
            }

        # PnL calculations
        pnls = [r.realized_pnl for r in closed_results if r.realized_pnl is not None]
        winning_pnls = [p for p in pnls if p > 0]
        losing_pnls = [p for p in pnls if p < 0]

        total_pnl = sum(pnls)
        winning_trades = len(winning_pnls)
        losing_trades = len(losing_pnls)
        win_rate = (winning_trades / len(pnls)) * 100 if pnls else 0

        avg_win = sum(winning_pnls) / len(winning_pnls) if winning_pnls else 0
        avg_loss = sum(losing_pnls) / len(losing_pnls) if losing_pnls else 0
        max_win = max(winning_pnls) if winning_pnls else 0
        max_loss = min(losing_pnls) if losing_pnls else 0

        # Profit factor
        gross_profit = sum(winning_pnls) if winning_pnls else 0
        gross_loss = abs(sum(losing_pnls)) if losing_pnls else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Duration calculations
        durations = [r.duration_hours for r in closed_results if r.duration_hours is not None]
        avg_duration = sum(durations) / len(durations) if durations else 0

        # Volume calculations
        volumes = []
        for result in closed_results:
            if result.entry_price and result.position_size:
                volume = result.entry_price * result.position_size
                volumes.append(volume)
        total_volume = sum(volumes)

        # Drawdown calculation
        running_pnl: float = 0
        peak: float = 0
        max_drawdown: float = 0

        for pnl in pnls:
            running_pnl += pnl
            if running_pnl > peak:
                peak = running_pnl
            drawdown = peak - running_pnl
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "max_win": max_win,
            "max_loss": max_loss,
            "max_drawdown": -max_drawdown,  # Store as negative
            "profit_factor": profit_factor,
            "avg_trade_duration_hours": avg_duration,
            "total_volume_traded": total_volume,
        }

    async def _get_existing_performance_record(
        self, strategy_id: int, account_id: Optional[int], start_date: datetime, end_date: datetime
    ) -> Optional[StrategyPerformanceModel]:
        """Get existing performance record for the period."""

        query = select(StrategyPerformanceModel).where(
            and_(
                StrategyPerformanceModel.strategy_id == strategy_id,
                StrategyPerformanceModel.period_start == start_date,
                StrategyPerformanceModel.period_end == end_date,
            )
        )

        if account_id:
            query = query.where(StrategyPerformanceModel.account_id == account_id)
        else:
            query = query.where(StrategyPerformanceModel.account_id.is_(None))

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _create_performance_record(
        self,
        strategy_id: int,
        account_id: Optional[int],
        start_date: datetime,
        end_date: datetime,
        period_days: int,
        metrics: Dict[str, Any],
        decision_results: List[Any],
    ) -> StrategyPerformanceModel:
        """Create new performance record."""

        performance = StrategyPerformanceModel(
            strategy_id=strategy_id,
            period_start=start_date,
            period_end=end_date,
            period_days=period_days,
            account_id=account_id,
            total_trades=metrics.get("total_trades", 0),
            winning_trades=metrics.get("winning_trades", 0),  # Note: fixing typo here
            losing_trades=metrics.get("losing_trades", 0),
            win_rate=metrics.get("win_rate", 0.0),
            total_pnl=metrics.get("total_pnl", 0.0),
            avg_win=metrics.get("avg_win", 0.0),
            avg_loss=metrics.get("avg_loss", 0.0),
            max_win=metrics.get("max_win", 0.0),
            max_loss=metrics.get("max_loss", 0.0),
            max_drawdown=metrics.get("max_drawdown", 0.0),
            profit_factor=metrics.get("profit_factor", 0.0),
            avg_trade_duration_hours=metrics.get("avg_trade_duration_hours", 0.0),
            total_volume_traded=metrics.get("total_volume_traded", 0.0),
        )

        self.db.add(performance)
        return performance

    async def _update_performance_record(
        self,
        performance: StrategyPerformanceModel,
        metrics: Dict[str, Any],
        decision_results: List[Any],
    ) -> None:
        """Update existing performance record."""

        for key, value in metrics.items():
            setattr(performance, key, value)

    async def _create_empty_performance_record(
        self,
        strategy_id: int,
        account_id: Optional[int],
        start_date: datetime,
        end_date: datetime,
        period_days: int,
    ) -> StrategyPerformanceModel:
        """Create empty performance record when no data available."""

        performance = StrategyPerformanceModel(
            strategy_id=strategy_id,
            account_id=account_id,
            period_start=start_date,
            period_end=end_date,
            period_days=period_days,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            total_pnl=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            max_win=0.0,
            max_loss=0.0,
            max_drawdown=0.0,
            profit_factor=0.0,
            avg_trade_duration_hours=0.0,
            total_volume_traded=0.0,
        )

        self.db.add(performance)
        return performance

    def _rank_strategies(
        self, performances: List[StrategyPerformanceModel], criteria: str
    ) -> List[StrategyRanking]:
        """Rank strategies based on specified criteria."""

        rankings = []

        for perf in performances:
            score = self._calculate_ranking_score(perf, criteria)

            # Get strategy name (would need to join with Strategy table in real implementation)
            strategy_name = f"Strategy {perf.strategy_id}"

            ranking = StrategyRanking(
                strategy_id=str(perf.strategy_id),
                strategy_name=strategy_name,
                rank=0,  # Will be set after sorting
                score=score,
                total_pnl=perf.total_pnl,
                win_rate=perf.win_rate,
                sharpe_ratio=perf.sharpe_ratio,
                max_drawdown=perf.max_drawdown,
            )

            rankings.append(ranking)

        # Sort and assign ranks
        rankings.sort(key=lambda x: x.score, reverse=True)
        for i, ranking in enumerate(rankings):
            ranking.rank = i + 1

        return rankings

    def _calculate_ranking_score(
        self, performance: StrategyPerformanceModel, criteria: str
    ) -> float:
        """Calculate ranking score based on criteria."""

        if criteria == "total_pnl":
            return performance.total_pnl
        elif criteria == "win_rate":
            return performance.win_rate
        elif criteria == "sharpe_ratio":
            return performance.sharpe_ratio or 0
        elif criteria == "profit_factor":
            return performance.profit_factor
        else:
            # Default composite score
            score: float = 0
            score += performance.total_pnl * 0.3
            score += performance.win_rate * 0.2
            score += (performance.sharpe_ratio or 0) * 100 * 0.3
            score += performance.profit_factor * 50 * 0.2
            return score

    async def _check_strategy_alerts(
        self, performance: StrategyPerformanceModel
    ) -> List[PerformanceAlert]:
        """Check for performance alerts for a strategy."""

        alerts = []

        # Performance degradation alert
        if performance.win_rate < 30 and performance.total_trades > 10:
            alerts.append(
                PerformanceAlert(
                    strategy_id=str(performance.strategy_id),
                    account_id=performance.account_id or 0,
                    alert_type="performance_degradation",
                    severity="high",
                    message=f"Win rate dropped to {performance.win_rate:.1f}%",
                    threshold_value=30.0,
                    current_value=performance.win_rate,
                )
            )

        # Drawdown limit alert
        if performance.max_drawdown < -1000:
            alerts.append(
                PerformanceAlert(
                    strategy_id=str(performance.strategy_id),
                    account_id=performance.account_id or 0,
                    alert_type="drawdown_limit",
                    severity="critical",
                    message=f"Maximum drawdown reached ${abs(performance.max_drawdown):.2f}",
                    threshold_value=-1000.0,
                    current_value=performance.max_drawdown,
                )
            )

        # Consecutive losses alert (would need more detailed tracking)
        if (
            performance.losing_trades > performance.winning_trades * 2
            and performance.total_trades > 5
        ):
            alerts.append(
                PerformanceAlert(
                    strategy_id=str(performance.strategy_id),
                    account_id=performance.account_id or 0,
                    alert_type="consecutive_losses",
                    severity="medium",
                    message=f"High loss ratio: {performance.losing_trades} losses vs {performance.winning_trades} wins",
                    threshold_value=2.0,
                    current_value=performance.losing_trades / max(performance.winning_trades, 1),
                )
            )

        return alerts
