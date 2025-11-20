"""
Strategy Management API routes.

Provides REST API endpoints for managing trading strategies including
strategy retrieval, assignment, switching, and performance tracking.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ...core.exceptions import ConfigurationError, ValidationError
from ...schemas.trading_decision import (
    StrategyAlert,
    StrategyAssignment,
    StrategyComparison,
    StrategyMetrics,
    StrategyPerformance,
    StrategyRiskParameters,
    TradingStrategy,
)
from ...services.llm.strategy_manager import StrategyManager
from ...db.session import get_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/strategies", tags=["Strategy Management"])


# Request/Response Models
class CustomStrategyRequest(BaseModel):
    """Request model for creating custom strategies."""

    strategy_name: str = Field(..., description="Human-readable strategy name")
    prompt_template: str = Field(..., description="LLM prompt template")
    risk_parameters: StrategyRiskParameters = Field(..., description="Risk management parameters")
    timeframe_preference: List[str] = Field(
        default=["1h", "4h"], description="Preferred timeframes for analysis"
    )
    max_positions: int = Field(default=3, ge=1, le=10, description="Maximum concurrent positions")
    position_sizing: str = Field(
        default="percentage",
        description="Position sizing method (fixed, percentage, kelly, volatility_adjusted)",
    )


class StrategyAssignmentRequest(BaseModel):
    """Request model for strategy assignment."""

    strategy_id: str = Field(..., description="Strategy identifier to assign")
    assigned_by: Optional[str] = Field(None, description="User making the assignment")
    switch_reason: Optional[str] = Field(None, description="Reason for assignment/switch")


class StrategyUpdateRequest(BaseModel):
    """Request model for strategy updates."""

    strategy_name: Optional[str] = Field(None, description="Updated strategy name")
    prompt_template: Optional[str] = Field(None, description="Updated prompt template")
    risk_parameters: Optional[StrategyRiskParameters] = Field(
        None, description="Updated risk parameters"
    )
    timeframe_preference: Optional[List[str]] = Field(
        None, description="Updated timeframe preferences"
    )
    max_positions: Optional[int] = Field(None, ge=1, le=10, description="Updated max positions")
    position_sizing: Optional[str] = Field(None, description="Updated position sizing method")
    is_active: Optional[bool] = Field(None, description="Updated active status")


class StrategyListResponse(BaseModel):
    """Response model for strategy list."""

    strategies: List[TradingStrategy]
    total_count: int
    active_count: int
    inactive_count: int


class PerformanceRequest(BaseModel):
    """Request model for performance calculation."""

    start_date: datetime = Field(..., description="Performance calculation start date")
    end_date: datetime = Field(..., description="Performance calculation end date")
    include_trades: bool = Field(default=False, description="Include detailed trade data")


# Dependency to get strategy manager
def get_strategy_manager() -> StrategyManager:
    """Get strategy manager instance."""
    try:
        return StrategyManager(session_factory=get_session_factory())
    except RuntimeError:
        # Fallback for tests or when DB not initialized
        return StrategyManager()


# API Endpoints
@router.get("/available", response_model=StrategyListResponse)
async def get_available_strategies(
    include_inactive: bool = Query(False, description="Include inactive strategies"),
    strategy_manager: StrategyManager = Depends(get_strategy_manager),
):
    """
    Get all available trading strategies.

    Returns a list of all available strategies with their configurations.
    Can optionally include inactive strategies.
    """
    try:
        all_strategies = await strategy_manager.get_available_strategies()

        if not include_inactive:
            strategies = [s for s in all_strategies if s.is_active]
        else:
            strategies = all_strategies

        active_count = sum(1 for s in all_strategies if s.is_active)
        inactive_count = len(all_strategies) - active_count

        return StrategyListResponse(
            strategies=strategies,
            total_count=len(all_strategies),
            active_count=active_count,
            inactive_count=inactive_count,
        )

    except Exception as e:
        logger.error(f"Error getting available strategies: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{strategy_id}", response_model=TradingStrategy)
async def get_strategy(
    strategy_id: str, strategy_manager: StrategyManager = Depends(get_strategy_manager)
):
    """
    Get a specific strategy by ID.

    Returns detailed configuration for the specified strategy.
    """
    try:
        strategy = await strategy_manager.get_strategy(strategy_id)

        if not strategy:
            raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")

        return strategy

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting strategy {strategy_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/account/{account_id}", response_model=TradingStrategy)
async def get_account_strategy(
    account_id: int, strategy_manager: StrategyManager = Depends(get_strategy_manager)
):
    """
    Get the currently assigned strategy for an account.

    Returns the strategy configuration currently assigned to the specified account.
    """
    try:
        strategy = await strategy_manager.get_account_strategy(account_id)

        if not strategy:
            raise HTTPException(
                status_code=404, detail=f"No strategy assigned to account {account_id}"
            )

        return strategy

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting strategy for account {account_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/account/{account_id}/assign", response_model=StrategyAssignment)
async def assign_strategy_to_account(
    account_id: int,
    request: StrategyAssignmentRequest,
    strategy_manager: StrategyManager = Depends(get_strategy_manager),
):
    """
    Assign a strategy to an account.

    Creates a new strategy assignment for the specified account.
    If the account already has a strategy, this will switch to the new one.
    """
    try:
        assignment = await strategy_manager.assign_strategy_to_account(
            account_id=account_id,
            strategy_id=request.strategy_id,
            assigned_by=request.assigned_by,
            switch_reason=request.switch_reason,
        )

        return assignment

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error assigning strategy to account {account_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/account/{account_id}/switch", response_model=StrategyAssignment)
async def switch_account_strategy(
    account_id: int,
    request: StrategyAssignmentRequest,
    strategy_manager: StrategyManager = Depends(get_strategy_manager),
):
    """
    Switch an account's strategy.

    Changes the strategy assignment for an account. This endpoint validates
    the switch and ensures proper transition between strategies.
    """
    try:
        assignment = await strategy_manager.switch_account_strategy(
            account_id=account_id,
            new_strategy_id=request.strategy_id,
            switch_reason=request.switch_reason or "API request",
            switched_by=request.assigned_by,
        )

        return assignment

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error switching strategy for account {account_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/custom", response_model=TradingStrategy)
async def create_custom_strategy(
    request: CustomStrategyRequest,
    strategy_manager: StrategyManager = Depends(get_strategy_manager),
):
    """
    Create a custom trading strategy.

    Creates a new custom strategy with the provided configuration.
    The strategy ID will be auto-generated based on the strategy name.
    """
    try:
        # Generate strategy ID from name
        strategy_id = request.strategy_name.lower().replace(" ", "_").replace("-", "_")

        # Ensure unique ID
        existing_strategy = await strategy_manager.get_strategy(strategy_id)
        if existing_strategy:
            # Add timestamp to make it unique
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            strategy_id = f"{strategy_id}_{timestamp}"

        strategy = await strategy_manager.create_custom_strategy(
            strategy_id=strategy_id,
            strategy_name=request.strategy_name,
            prompt_template=request.prompt_template,
            risk_parameters=request.risk_parameters,
            timeframe_preference=request.timeframe_preference,
            max_positions=request.max_positions,
            position_sizing=request.position_sizing,
        )

        return strategy

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConfigurationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating custom strategy: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{strategy_id}", response_model=TradingStrategy)
async def update_strategy(
    strategy_id: str,
    request: StrategyUpdateRequest,
    strategy_manager: StrategyManager = Depends(get_strategy_manager),
):
    """
    Update an existing strategy.

    Updates the configuration of an existing strategy. Only provided fields
    will be updated, others will remain unchanged.
    """
    try:
        strategy = await strategy_manager.get_strategy(strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")

        # Update fields if provided
        if request.strategy_name is not None:
            strategy.strategy_name = request.strategy_name
        if request.prompt_template is not None:
            strategy.prompt_template = request.prompt_template
        if request.risk_parameters is not None:
            strategy.risk_parameters = request.risk_parameters
        if request.timeframe_preference is not None:
            strategy.timeframe_preference = request.timeframe_preference
        if request.max_positions is not None:
            strategy.max_positions = request.max_positions
        if request.position_sizing is not None:
            strategy.position_sizing = request.position_sizing
        if request.is_active is not None:
            strategy.is_active = request.is_active

        # Validate updated strategy
        validation_errors = await strategy_manager.validate_strategy(strategy)
        if validation_errors:
            raise HTTPException(
                status_code=400,
                detail=f"Strategy validation failed: {', '.join(validation_errors)}",
            )

        # Save updated strategy (this would typically update the database)
        # For now, the strategy is updated in memory
        logger.info(f"Updated strategy '{strategy_id}'")

        return strategy

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating strategy {strategy_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{strategy_id}")
async def delete_strategy(
    strategy_id: str,
    force: bool = Query(False, description="Force delete even if assigned to accounts"),
    strategy_manager: StrategyManager = Depends(get_strategy_manager),
):
    """
    Delete a strategy.

    Removes a strategy from the system. By default, prevents deletion if
    the strategy is assigned to any accounts unless force=true.
    """
    try:
        strategy = await strategy_manager.get_strategy(strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")

        # Check if strategy is assigned to accounts
        assigned_accounts = await strategy_manager.get_accounts_using_strategy(strategy_id)
        if assigned_accounts and not force:
            raise HTTPException(
                status_code=400,
                detail=f"Strategy '{strategy_id}' is assigned to {len(assigned_accounts)} accounts. "
                f"Use force=true to delete anyway.",
            )

        # Prevent deletion of predefined strategies
        if strategy_id in ["conservative", "aggressive", "scalping", "swing", "dca"]:
            raise HTTPException(
                status_code=400, detail=f"Cannot delete predefined strategy '{strategy_id}'"
            )

        # Deactivate strategy instead of actual deletion for safety
        await strategy_manager.deactivate_strategy(strategy_id)

        return {
            "message": f"Strategy '{strategy_id}' deactivated successfully",
            "strategy_id": strategy_id,
            "assigned_accounts": assigned_accounts,
            "force_deleted": force,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting strategy {strategy_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{strategy_id}/activate")
async def activate_strategy(
    strategy_id: str, strategy_manager: StrategyManager = Depends(get_strategy_manager)
):
    """
    Activate a strategy.

    Enables a strategy for assignment to accounts.
    """
    try:
        success = await strategy_manager.activate_strategy(strategy_id)

        if not success:
            raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")

        return {
            "message": f"Strategy '{strategy_id}' activated successfully",
            "strategy_id": strategy_id,
            "is_active": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating strategy {strategy_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{strategy_id}/deactivate")
async def deactivate_strategy(
    strategy_id: str, strategy_manager: StrategyManager = Depends(get_strategy_manager)
):
    """
    Deactivate a strategy.

    Prevents a strategy from being assigned to new accounts.
    Existing assignments remain active.
    """
    try:
        success = await strategy_manager.deactivate_strategy(strategy_id)

        if not success:
            raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")

        return {
            "message": f"Strategy '{strategy_id}' deactivated successfully",
            "strategy_id": strategy_id,
            "is_active": False,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating strategy {strategy_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{strategy_id}/assignments")
async def get_strategy_assignments(
    strategy_id: str, strategy_manager: StrategyManager = Depends(get_strategy_manager)
):
    """
    Get all accounts using a specific strategy.

    Returns a list of account IDs currently assigned to the strategy.
    """
    try:
        strategy = await strategy_manager.get_strategy(strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")

        assigned_accounts = await strategy_manager.get_accounts_using_strategy(strategy_id)

        return {
            "strategy_id": strategy_id,
            "strategy_name": strategy.strategy_name,
            "assigned_accounts": assigned_accounts,
            "assignment_count": len(assigned_accounts),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting assignments for strategy {strategy_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/assignments/all")
async def get_all_strategy_assignments(
    strategy_manager: StrategyManager = Depends(get_strategy_manager),
):
    """
    Get all current strategy assignments.

    Returns a mapping of all account IDs to their assigned strategies.
    """
    try:
        assignments = await strategy_manager.get_strategy_assignments()

        # Convert to more detailed format
        detailed_assignments = []
        for account_id, strategy_id in assignments.items():
            strategy = await strategy_manager.get_strategy(strategy_id)
            detailed_assignments.append(
                {
                    "account_id": account_id,
                    "strategy_id": strategy_id,
                    "strategy_name": strategy.strategy_name if strategy else "Unknown",
                    "is_active": strategy.is_active if strategy else False,
                }
            )

        return {"assignments": detailed_assignments, "total_assignments": len(assignments)}

    except Exception as e:
        logger.error(f"Error getting all strategy assignments: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/validate")
async def validate_strategy_config(
    strategy: TradingStrategy, strategy_manager: StrategyManager = Depends(get_strategy_manager)
):
    """
    Validate a strategy configuration.

    Validates strategy configuration without creating or updating the strategy.
    Useful for testing strategy configurations before applying them.
    """
    try:
        validation_errors = await strategy_manager.validate_strategy(strategy)

        return {
            "is_valid": len(validation_errors) == 0,
            "errors": validation_errors,
            "strategy_id": strategy.strategy_id,
            "strategy_name": strategy.strategy_name,
        }

    except Exception as e:
        logger.error(f"Error validating strategy: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{strategy_id}/performance", response_model=StrategyPerformance)
async def get_strategy_performance(
    strategy_id: str,
    timeframe: str = Query("7d", description="Timeframe for performance (7d, 30d, 90d)"),
    strategy_manager: StrategyManager = Depends(get_strategy_manager),
):
    """
    Get performance metrics for a specific strategy.

    Returns comprehensive performance metrics including P&L, win rate,
    Sharpe ratio, and other key performance indicators.
    """
    try:
        strategy = await strategy_manager.get_strategy(strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")

        performance = await strategy_manager.get_strategy_performance(strategy_id, timeframe)

        if not performance:
            raise HTTPException(
                status_code=404,
                detail=f"No performance data available for strategy '{strategy_id}'",
            )

        return performance

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting performance for strategy {strategy_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{strategy_id}/performance/calculate", response_model=StrategyPerformance)
async def calculate_strategy_performance(
    strategy_id: str,
    request: PerformanceRequest,
    strategy_manager: StrategyManager = Depends(get_strategy_manager),
):
    """
    Calculate performance metrics for a strategy over a specific period.

    Calculates comprehensive performance metrics based on trade data
    for the specified time period.
    """
    try:
        strategy = await strategy_manager.get_strategy(strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")

        # TODO: In a real implementation, this would fetch trade data from database
        # For now, return placeholder data
        trades_data = []  # Would fetch from database based on strategy_id and date range

        performance = await strategy_manager.calculate_strategy_performance(
            strategy_id=strategy_id,
            start_date=request.start_date,
            end_date=request.end_date,
            trades_data=trades_data,
        )

        return performance

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error calculating performance for strategy {strategy_id}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/compare", response_model=StrategyComparison)
async def compare_strategies(
    strategy_ids: List[str],
    comparison_period_days: int = Query(
        30, ge=1, le=365, description="Period for comparison in days"
    ),
    ranking_criteria: str = Query(
        "sharpe_ratio",
        description="Criteria for ranking (sharpe_ratio, total_pnl, win_rate, profit_factor)",
    ),
    strategy_manager: StrategyManager = Depends(get_strategy_manager),
):
    """
    Compare performance of multiple strategies.

    Compares the performance of multiple strategies over a specified period
    and ranks them based on the selected criteria.
    """
    try:
        if len(strategy_ids) < 2:
            raise HTTPException(
                status_code=400, detail="At least 2 strategies required for comparison"
            )

        if len(strategy_ids) > 10:
            raise HTTPException(
                status_code=400, detail="Maximum 10 strategies allowed for comparison"
            )

        # Validate all strategies exist
        for strategy_id in strategy_ids:
            strategy = await strategy_manager.get_strategy(strategy_id)
            if not strategy:
                raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")

        comparison = await strategy_manager.compare_strategies(
            strategy_ids=strategy_ids,
            comparison_period_days=comparison_period_days,
            ranking_criteria=ranking_criteria,
        )

        return comparison

    except HTTPException:
        raise
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error comparing strategies: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{strategy_id}/metrics/{account_id}", response_model=StrategyMetrics)
async def get_strategy_metrics(
    strategy_id: str,
    account_id: int,
    strategy_manager: StrategyManager = Depends(get_strategy_manager),
):
    """
    Get real-time metrics for a strategy on a specific account.

    Returns current strategy metrics including positions, P&L,
    risk utilization, and cooldown status.
    """
    try:
        strategy = await strategy_manager.get_strategy(strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")

        metrics = await strategy_manager.get_strategy_metrics(strategy_id, account_id)

        if not metrics:
            raise HTTPException(
                status_code=404,
                detail=f"No metrics available for strategy '{strategy_id}' on account {account_id}",
            )

        return metrics

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error getting metrics for strategy {strategy_id}, account {account_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/recommendations/{account_id}")
async def get_strategy_recommendations(
    account_id: int, strategy_manager: StrategyManager = Depends(get_strategy_manager)
):
    """
    Get strategy recommendations for an account.

    Analyzes current strategy performance and provides recommendations
    for optimization or strategy changes.
    """
    try:
        recommendations = await strategy_manager.get_strategy_recommendations(account_id)

        return {
            "account_id": account_id,
            "recommendations": recommendations,
            "recommendation_count": len(recommendations),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting recommendations for account {account_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/alerts", response_model=List[StrategyAlert])
async def get_strategy_alerts(
    strategy_id: Optional[str] = Query(None, description="Filter by strategy ID"),
    account_id: Optional[int] = Query(None, description="Filter by account ID"),
    severity: Optional[str] = Query(
        None, description="Filter by severity (low, medium, high, critical)"
    ),
    strategy_manager: StrategyManager = Depends(get_strategy_manager),
):
    """
    Get strategy alerts with optional filtering.

    Returns active alerts for strategies, optionally filtered by
    strategy, account, or severity level.
    """
    try:
        alerts = await strategy_manager.get_strategy_alerts(
            strategy_id=strategy_id, account_id=account_id, severity=severity
        )

        return alerts

    except Exception as e:
        logger.error(f"Error getting strategy alerts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/alerts/{alert_index}/acknowledge")
async def acknowledge_strategy_alert(
    alert_index: int,
    acknowledged_by: str = Query(..., description="User acknowledging the alert"),
    strategy_manager: StrategyManager = Depends(get_strategy_manager),
):
    """
    Acknowledge a strategy alert.

    Marks an alert as acknowledged by the specified user.
    """
    try:
        success = await strategy_manager.acknowledge_alert(alert_index, acknowledged_by)

        if not success:
            raise HTTPException(status_code=404, detail=f"Alert {alert_index} not found")

        return {
            "message": f"Alert {alert_index} acknowledged successfully",
            "alert_index": alert_index,
            "acknowledged_by": acknowledged_by,
            "acknowledged_at": datetime.now(timezone.utc).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error acknowledging alert {alert_index}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/alerts/cleanup")
async def cleanup_old_alerts(
    max_age_hours: int = Query(
        24, ge=1, le=168, description="Maximum age of alerts to keep (hours)"
    ),
    strategy_manager: StrategyManager = Depends(get_strategy_manager),
):
    """
    Clean up old strategy alerts.

    Removes old alerts to prevent memory buildup. Only removes
    acknowledged alerts older than the specified age.
    """
    try:
        cleared_count = await strategy_manager.clear_old_alerts(max_age_hours)

        return {
            "message": f"Cleaned up {cleared_count} old alerts",
            "cleared_count": cleared_count,
            "max_age_hours": max_age_hours,
            "cleanup_time": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error cleaning up alerts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
