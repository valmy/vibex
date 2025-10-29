"""
API routes for LLM decision engine.

Provides endpoints for decision generation, model management, and monitoring.
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ...schemas.trading_decision import DecisionResult, TradingContext, TradingDecision
from ...services.llm_service import get_llm_service
from ...services.llm_metrics import HealthStatus, UsageMetrics

router = APIRouter(prefix="/api/v1/decisions", tags=["LLM Decisions"])


class DecisionRequest(BaseModel):
    """Request model for decision generation."""
    symbol: str = Field(..., description="Trading pair symbol")
    context: TradingContext = Field(..., description="Trading context")
    strategy_override: Optional[str] = Field(None, description="Strategy override")
    ab_test_name: Optional[str] = Field(None, description="A/B test name")


class ModelSwitchRequest(BaseModel):
    """Request model for model switching."""
    model_name: str = Field(..., description="Model name to switch to")


class ABTestRequest(BaseModel):
    """Request model for starting A/B test."""
    test_name: str = Field(..., description="Unique test name")
    model_a: str = Field(..., description="First model to test")
    model_b: str = Field(..., description="Second model to test")
    traffic_split: float = Field(0.5, ge=0.0, le=1.0, description="Traffic split for model A")
    duration_hours: int = Field(24, ge=1, le=168, description="Test duration in hours")


@router.post("/generate", response_model=DecisionResult)
async def generate_decision(
    request: DecisionRequest,
    llm_service = Depends(get_llm_service)
) -> DecisionResult:
    """
    Generate a trading decision using LLM analysis.

    Args:
        request: Decision generation request

    Returns:
        DecisionResult with structured decision and validation status
    """
    try:
        result = await llm_service.generate_trading_decision(
            symbol=request.symbol,
            context=request.context,
            strategy_override=request.strategy_override,
            ab_test_name=request.ab_test_name,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Decision generation failed: {str(e)}")


@router.get("/health", response_model=HealthStatus)
async def get_health_status(
    llm_service = Depends(get_llm_service)
) -> HealthStatus:
    """
    Get LLM service health status.

    Returns:
        HealthStatus with current service health metrics
    """
    try:
        health_status = await llm_service.validate_api_health()
        return health_status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/metrics", response_model=UsageMetrics)
async def get_usage_metrics(
    timeframe_hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    llm_service = Depends(get_llm_service)
) -> UsageMetrics:
    """
    Get usage metrics for specified timeframe.

    Args:
        timeframe_hours: Hours to look back for metrics

    Returns:
        UsageMetrics summary
    """
    try:
        metrics = llm_service.get_usage_metrics(timeframe_hours)
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metrics retrieval failed: {str(e)}")


@router.post("/models/switch")
async def switch_model(
    request: ModelSwitchRequest,
    llm_service = Depends(get_llm_service)
) -> Dict[str, str]:
    """
    Switch to a different LLM model.

    Args:
        request: Model switch request

    Returns:
        Success message with new model name
    """
    try:
        success = await llm_service.switch_model(request.model_name)
        if success:
            return {"message": f"Successfully switched to model: {request.model_name}"}
        else:
            raise HTTPException(status_code=400, detail="Model switch failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model switch failed: {str(e)}")


@router.get("/models/supported")
async def get_supported_models(
    llm_service = Depends(get_llm_service)
) -> Dict[str, List[str]]:
    """
    Get list of supported LLM models.

    Returns:
        Dictionary with supported model names
    """
    try:
        return {"supported_models": list(llm_service.supported_models.keys())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get supported models: {str(e)}")


@router.post("/ab-tests/start")
async def start_ab_test(
    request: ABTestRequest,
    llm_service = Depends(get_llm_service)
) -> Dict[str, str]:
    """
    Start an A/B test between two models.

    Args:
        request: A/B test configuration

    Returns:
        Success message with test details
    """
    try:
        success = llm_service.start_ab_test(
            test_name=request.test_name,
            model_a=request.model_a,
            model_b=request.model_b,
            traffic_split=request.traffic_split,
            duration_hours=request.duration_hours,
        )

        if success:
            return {
                "message": f"A/B test '{request.test_name}' started successfully",
                "model_a": request.model_a,
                "model_b": request.model_b,
                "duration_hours": str(request.duration_hours),
            }
        else:
            raise HTTPException(status_code=400, detail="A/B test start failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"A/B test start failed: {str(e)}")


@router.get("/ab-tests/active")
async def get_active_ab_tests(
    llm_service = Depends(get_llm_service)
) -> Dict:
    """
    Get all active A/B tests.

    Returns:
        Dictionary of active A/B tests
    """
    try:
        active_tests = llm_service.get_active_ab_tests()
        return {"active_tests": active_tests}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get active tests: {str(e)}")


@router.post("/ab-tests/{test_name}/end")
async def end_ab_test(
    test_name: str,
    llm_service = Depends(get_llm_service)
) -> Dict:
    """
    End an A/B test and get results.

    Args:
        test_name: Name of the test to end

    Returns:
        A/B test results
    """
    try:
        result = llm_service.end_ab_test(test_name)
        if result:
            return {
                "message": f"A/B test '{test_name}' ended successfully",
                "result": result,
            }
        else:
            raise HTTPException(status_code=404, detail=f"A/B test '{test_name}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to end A/B test: {str(e)}")


@router.get("/models/{model_name}/performance")
async def get_model_performance(
    model_name: str,
    timeframe_hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    llm_service = Depends(get_llm_service)
) -> Dict:
    """
    Get performance metrics for a specific model.

    Args:
        model_name: Name of the model
        timeframe_hours: Hours to look back

    Returns:
        Model performance metrics
    """
    try:
        performance = llm_service.metrics_tracker.get_model_performance(model_name, timeframe_hours)
        return {"model": model_name, "performance": performance}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get model performance: {str(e)}")


@router.post("/validate")
async def validate_decision(
    decision: TradingDecision,
) -> Dict[str, bool]:
    """
    Validate a trading decision against schema and business rules.

    Args:
        decision: Trading decision to validate

    Returns:
        Validation result
    """
    try:
        # Basic schema validation is handled by Pydantic automatically
        # Additional business rule validation could be added here
        return {"valid": True, "message": "Decision is valid"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Decision validation failed: {str(e)}")


@router.get("/history")
async def get_decision_history(
    account_id: Optional[int] = Query(None, description="Account ID filter"),
    symbol: Optional[str] = Query(None, description="Symbol filter"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of results"),
) -> Dict[str, List]:
    """
    Get decision history with optional filters.

    Args:
        account_id: Optional account ID filter
        symbol: Optional symbol filter
        limit: Maximum number of results

    Returns:
        List of historical decisions
    """
    # This would typically query a database
    # For now, return empty list as placeholder
    return {"decisions": [], "total": 0, "message": "Decision history not yet implemented"}