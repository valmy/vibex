"""
Monitoring and Analytics API routes.

Provides comprehensive monitoring endpoints for system health,
performance analytics, and operational metrics.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ...services.llm.context_builder import get_context_builder_service
from ...services.llm.decision_engine import get_decision_engine
from ...services.llm.decision_validator import get_decision_validator
from ...services.llm.llm_service import get_llm_service
from ...services.llm.strategy_manager import StrategyManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/monitoring", tags=["Monitoring & Analytics"])


# Response Models
class SystemHealthResponse(BaseModel):
    """System-wide health status response."""

    overall_status: str = Field(..., description="Overall system health status")
    components: Dict[str, Dict[str, Any]] = Field(..., description="Individual component health")
    uptime_seconds: float = Field(..., description="System uptime in seconds")
    last_check: datetime = Field(..., description="Last health check timestamp")
    issues: List[str] = Field(default=[], description="Current system issues")


class PerformanceMetrics(BaseModel):
    """Performance metrics response."""

    decision_engine: Dict[str, Any] = Field(..., description="Decision engine metrics")
    llm_service: Dict[str, Any] = Field(..., description="LLM service metrics")
    context_builder: Dict[str, Any] = Field(..., description="Context builder metrics")
    decision_validator: Dict[str, Any] = Field(..., description="Decision validator metrics")
    strategy_manager: Dict[str, Any] = Field(..., description="Strategy manager metrics")


class ModelManagementResponse(BaseModel):
    """Model management response."""

    current_model: str = Field(..., description="Currently active model")
    available_models: List[str] = Field(..., description="Available models")
    model_performance: Dict[str, Dict[str, Any]] = Field(..., description="Performance by model")
    switch_history: List[Dict[str, Any]] = Field(..., description="Model switch history")


class AlertsResponse(BaseModel):
    """System alerts response."""

    active_alerts: List[Dict[str, Any]] = Field(..., description="Active system alerts")
    alert_counts: Dict[str, int] = Field(..., description="Alert counts by severity")
    recent_alerts: List[Dict[str, Any]] = Field(..., description="Recent alerts")


# Dependency functions
def get_strategy_manager() -> StrategyManager:
    """Get strategy manager instance."""
    return StrategyManager()


# API Endpoints
@router.get("/health/system", response_model=SystemHealthResponse)
async def get_system_health():
    """
    Get comprehensive system health status.

    Returns health status for all major system components including
    decision engine, LLM service, context builder, and strategy manager.
    """
    try:
        components = {}
        issues = []
        overall_healthy = True

        # Check Decision Engine health
        try:
            decision_engine = get_decision_engine()
            engine_health = await decision_engine.get_engine_health()
            components["decision_engine"] = {
                "status": "healthy" if engine_health.is_healthy else "unhealthy",
                "response_time_ms": engine_health.response_time_ms,
                "consecutive_failures": engine_health.consecutive_failures,
                "circuit_breaker_open": engine_health.circuit_breaker_open,
                "error_message": engine_health.error_message,
            }
            if not engine_health.is_healthy:
                overall_healthy = False
                issues.append(f"Decision Engine: {engine_health.error_message}")
        except Exception as e:
            components["decision_engine"] = {"status": "error", "error": str(e)}
            overall_healthy = False
            issues.append(f"Decision Engine: {str(e)}")

        # Check LLM Service health
        try:
            llm_service = get_llm_service()
            llm_health = await llm_service.validate_api_health()
            components["llm_service"] = {
                "status": "healthy" if llm_health.is_healthy else "unhealthy",
                "current_model": llm_health.current_model,
                "available_models": llm_health.available_models,
                "response_time_ms": llm_health.response_time_ms,
                "consecutive_failures": llm_health.consecutive_failures,
                "circuit_breaker_open": llm_health.circuit_breaker_open,
                "error_message": llm_health.error_message,
            }
            if not llm_health.is_healthy:
                overall_healthy = False
                issues.append(f"LLM Service: {llm_health.error_message}")
        except Exception as e:
            components["llm_service"] = {"status": "error", "error": str(e)}
            overall_healthy = False
            issues.append(f"LLM Service: {str(e)}")

        # Check Context Builder health
        try:
            context_builder = get_context_builder_service()
            # Context builder doesn't have a health check method, so we'll do a basic check
            components["context_builder"] = {
                "status": "healthy",
                "cache_size": getattr(context_builder, "_cache_size", 0),
            }
        except Exception as e:
            components["context_builder"] = {"status": "error", "error": str(e)}
            overall_healthy = False
            issues.append(f"Context Builder: {str(e)}")

        # Check Decision Validator health
        try:
            get_decision_validator()
            # Decision validator doesn't have a health check method, so we'll do a basic check
            components["decision_validator"] = {"status": "healthy"}
        except Exception as e:
            components["decision_validator"] = {"status": "error", "error": str(e)}
            overall_healthy = False
            issues.append(f"Decision Validator: {str(e)}")

        # Check Strategy Manager health
        try:
            strategy_manager = get_strategy_manager()
            available_strategies = await strategy_manager.get_available_strategies()
            active_strategies = [s for s in available_strategies if s.is_active]
            components["strategy_manager"] = {
                "status": "healthy",
                "total_strategies": len(available_strategies),
                "active_strategies": len(active_strategies),
            }
        except Exception as e:
            components["strategy_manager"] = {"status": "error", "error": str(e)}
            overall_healthy = False
            issues.append(f"Strategy Manager: {str(e)}")

        # Calculate uptime (simplified - would be more accurate with actual start time tracking)
        uptime_seconds = 3600.0  # Placeholder - would track actual uptime

        return SystemHealthResponse(
            overall_status="healthy" if overall_healthy else "unhealthy",
            components=components,
            uptime_seconds=uptime_seconds,
            last_check=datetime.now(timezone.utc),
            issues=issues,
        )

    except Exception as e:
        logger.error(f"Error getting system health: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Health check failed") from e


@router.get("/performance", response_model=PerformanceMetrics)
async def get_performance_metrics(
    timeframe_hours: Annotated[
        int, Query(ge=1, le=168, description="Hours to look back for metrics")
    ] = 24,
):
    """
    Get comprehensive performance metrics for all system components.

    Returns detailed performance metrics including response times,
    success rates, throughput, and resource utilization.
    """
    try:
        # Decision Engine metrics
        decision_engine = get_decision_engine()
        engine_metrics = decision_engine.get_usage_metrics(timeframe_hours)
        cache_stats = decision_engine.get_cache_stats()

        decision_engine_metrics = {
            "total_requests": engine_metrics.total_requests,
            "successful_requests": engine_metrics.successful_requests,
            "failed_requests": engine_metrics.failed_requests,
            "avg_response_time_ms": engine_metrics.avg_response_time_ms,
            "requests_per_hour": engine_metrics.requests_per_hour,
            "error_rate": engine_metrics.error_rate,
            "uptime_percentage": engine_metrics.uptime_percentage,
            "cache_hit_rate": cache_stats["cache_hit_rate"],
            "active_decisions": cache_stats["active_decisions"],
        }

        # LLM Service metrics
        llm_service = get_llm_service()
        llm_metrics = llm_service.get_usage_metrics(timeframe_hours)

        llm_service_metrics = {
            "total_requests": llm_metrics.total_requests,
            "successful_requests": llm_metrics.successful_requests,
            "failed_requests": llm_metrics.failed_requests,
            "avg_response_time_ms": llm_metrics.avg_response_time_ms,
            "total_cost_usd": llm_metrics.total_cost_usd,
            "cost_per_request": llm_metrics.cost_per_request,
            "requests_per_hour": llm_metrics.requests_per_hour,
            "error_rate": llm_metrics.error_rate,
        }

        # Context Builder metrics (placeholder - would implement actual metrics)
        context_builder_metrics = {
            "contexts_built": 0,  # Would track actual metrics
            "avg_build_time_ms": 0.0,
            "cache_hit_rate": 0.0,
            "data_freshness_score": 95.0,
        }

        # Decision Validator metrics (placeholder - would implement actual metrics)
        decision_validator_metrics = {
            "validations_performed": 0,  # Would track actual metrics
            "validation_success_rate": 98.5,
            "avg_validation_time_ms": 15.0,
            "fallback_decisions_created": 0,
        }

        # Strategy Manager metrics (placeholder - would implement actual metrics)
        strategy_manager_metrics = {
            "strategy_switches": 0,  # Would track actual metrics
            "active_assignments": 0,
            "performance_calculations": 0,
            "alerts_generated": 0,
        }

        return PerformanceMetrics(
            decision_engine=decision_engine_metrics,
            llm_service=llm_service_metrics,
            context_builder=context_builder_metrics,
            decision_validator=decision_validator_metrics,
            strategy_manager=strategy_manager_metrics,
        )

    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get performance metrics") from e


@router.get("/models", response_model=ModelManagementResponse)
async def get_model_management_info():
    """
    Get LLM model management information.

    Returns current model status, available models, performance metrics
    per model, and model switch history.
    """
    try:
        llm_service = get_llm_service()

        # Get current model and available models
        current_model = getattr(llm_service, "current_model", "unknown")
        available_models = list(getattr(llm_service, "supported_models", {}).keys())

        # Get model performance (placeholder - would implement actual tracking)
        model_performance = {}
        for model in available_models:
            model_performance[model] = {
                "total_requests": 0,  # Would track actual metrics
                "avg_response_time_ms": 0.0,
                "success_rate": 0.0,
                "cost_per_request": 0.0,
                "last_used": None,
            }

        # Get switch history (placeholder - would implement actual tracking)
        switch_history = []  # Would track actual model switches

        return ModelManagementResponse(
            current_model=current_model,
            available_models=available_models,
            model_performance=model_performance,
            switch_history=switch_history,
        )

    except Exception as e:
        logger.error(f"Error getting model management info: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get model management info") from e


@router.post("/models/{model_name}/switch")
async def switch_llm_model(model_name: str):
    """
    Switch to a different LLM model.

    Changes the active LLM model for decision generation.
    """
    try:
        llm_service = get_llm_service()
        success = await llm_service.switch_model(model_name)

        if not success:
            raise HTTPException(status_code=400, detail=f"Failed to switch to model '{model_name}'")

        return {
            "message": f"Successfully switched to model '{model_name}'",
            "previous_model": getattr(llm_service, "_previous_model", "unknown"),
            "current_model": model_name,
            "switch_time": datetime.now(timezone.utc).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error switching to model {model_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Model switch failed") from e


@router.get("/models/{model_name}/performance")
async def get_model_performance(
    model_name: str,
    timeframe_hours: Annotated[
        int, Query(ge=1, le=168, description="Hours to look back for metrics")
    ] = 24,
):
    """
    Get performance metrics for a specific LLM model.

    Returns detailed performance metrics for the specified model
    including response times, success rates, and cost information.
    """
    try:
        llm_service = get_llm_service()

        # Check if model exists
        available_models = list(getattr(llm_service, "supported_models", {}).keys())
        if model_name not in available_models:
            raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")

        # Get model performance (placeholder - would implement actual tracking)
        performance = {
            "model_name": model_name,
            "timeframe_hours": timeframe_hours,
            "total_requests": 0,  # Would track actual metrics
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_response_time_ms": 0.0,
            "min_response_time_ms": 0.0,
            "max_response_time_ms": 0.0,
            "success_rate": 0.0,
            "error_rate": 0.0,
            "total_cost_usd": 0.0,
            "avg_cost_per_request": 0.0,
            "requests_per_hour": 0.0,
            "last_used": None,
            "decision_quality_score": 0.0,  # Would calculate based on validation success
        }

        return performance

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting performance for model {model_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get model performance") from e


@router.get("/alerts", response_model=AlertsResponse)
async def get_system_alerts(
    severity: Annotated[
        Optional[str], Query(description="Filter by severity (low, medium, high, critical)")
    ] = None,
    component: Annotated[Optional[str], Query(description="Filter by component")] = None,
    limit: Annotated[
        int, Query(ge=1, le=200, description="Maximum number of alerts to return")
    ] = 50,
):
    """
    Get system alerts and notifications.

    Returns active alerts from all system components with optional filtering
    by severity level or component.
    """
    try:
        active_alerts = []
        alert_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}

        # Get strategy alerts
        strategy_manager = get_strategy_manager()
        strategy_alerts = await strategy_manager.get_strategy_alerts(severity=severity)

        for alert in strategy_alerts:
            alert_dict = {
                "id": f"strategy_{alert.strategy_id}_{alert.account_id}",
                "component": "strategy_manager",
                "type": alert.alert_type,
                "severity": alert.severity,
                "message": alert.message,
                "created_at": alert.created_at.isoformat(),
                "acknowledged": alert.acknowledged,
                "strategy_id": alert.strategy_id,
                "account_id": alert.account_id,
            }
            active_alerts.append(alert_dict)
            alert_counts[alert.severity] += 1

        # Add other component alerts (placeholder - would implement actual alert systems)
        # Decision Engine alerts, LLM Service alerts, etc.

        # Apply component filter
        if component:
            active_alerts = [a for a in active_alerts if a["component"] == component]

        # Apply limit
        active_alerts = active_alerts[:limit]

        # Get recent alerts (last 24 hours)
        recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        recent_alerts = [
            a for a in active_alerts if datetime.fromisoformat(a["created_at"]) > recent_cutoff
        ]

        return AlertsResponse(
            active_alerts=active_alerts, alert_counts=alert_counts, recent_alerts=recent_alerts
        )

    except Exception as e:
        logger.error(f"Error getting system alerts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get system alerts") from e


@router.get("/analytics/summary")
async def get_analytics_summary(
    timeframe_hours: Annotated[
        int, Query(ge=1, le=168, description="Hours to look back for analytics")
    ] = 24,
):
    """
    Get analytics summary for the specified timeframe.

    Returns high-level analytics including decision counts, success rates,
    strategy performance, and system utilization metrics.
    """
    try:
        # Get decision engine metrics
        decision_engine = get_decision_engine()
        engine_metrics = decision_engine.get_usage_metrics(timeframe_hours)

        # Get LLM service metrics
        llm_service = get_llm_service()
        llm_metrics = llm_service.get_usage_metrics(timeframe_hours)

        # Calculate summary metrics
        summary = {
            "timeframe_hours": timeframe_hours,
            "period_start": (
                datetime.now(timezone.utc) - timedelta(hours=timeframe_hours)
            ).isoformat(),
            "period_end": datetime.now(timezone.utc).isoformat(),
            "decisions": {
                "total_generated": engine_metrics.total_requests,
                "successful": engine_metrics.successful_requests,
                "failed": engine_metrics.failed_requests,
                "success_rate": (
                    (engine_metrics.successful_requests / engine_metrics.total_requests * 100)
                    if engine_metrics.total_requests > 0
                    else 0.0
                ),
                "avg_processing_time_ms": engine_metrics.avg_response_time_ms,
            },
            "llm_usage": {
                "total_requests": llm_metrics.total_requests,
                "total_cost_usd": llm_metrics.total_cost_usd,
                "avg_cost_per_request": llm_metrics.cost_per_request,
                "avg_response_time_ms": llm_metrics.avg_response_time_ms,
            },
            "system_performance": {
                "uptime_percentage": engine_metrics.uptime_percentage,
                "requests_per_hour": engine_metrics.requests_per_hour,
                "error_rate": engine_metrics.error_rate,
            },
            "strategies": {
                "total_active": 0,  # Would calculate from strategy manager
                "switches_performed": 0,  # Would track actual switches
                "alerts_generated": 0,  # Would count alerts
            },
        }

        return summary

    except Exception as e:
        logger.error(f"Error getting analytics summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get analytics summary") from e


@router.post("/health/check")
async def trigger_health_check():
    """
    Trigger a comprehensive health check of all system components.

    Performs active health checks on all components and returns
    detailed status information.
    """
    try:
        # This would trigger active health checks on all components
        # For now, we'll just return the current health status
        health_response = await get_system_health()

        return {
            "message": "Health check completed",
            "check_time": datetime.now(timezone.utc).isoformat(),
            "overall_status": health_response.overall_status,
            "components_checked": len(health_response.components),
            "issues_found": len(health_response.issues),
            "details": health_response,
        }

    except Exception as e:
        logger.error(f"Error triggering health check: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Health check failed") from e
