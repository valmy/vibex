"""
Decision Engine API routes.

Provides REST API endpoints for the LLM Decision Engine including
decision generation, batch processing, history, and management.
"""

import logging
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, WebSocket
from pydantic import BaseModel, Field

from ...schemas.trading_decision import DecisionResult, HealthStatus, TradingDecision, UsageMetrics
from ...services.llm.decision_engine import (
    DecisionEngineError,
    RateLimitExceededError,
    get_decision_engine,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/decisions", tags=["Decision Engine"])


# Request/Response Models
class DecisionRequest(BaseModel):
    """Request model for multi-asset decision generation."""

    symbols: Optional[List[str]] = Field(
        None,
        description="List of trading pair symbols (e.g., ['BTCUSDT', 'ETHUSDT']). "
        "If not provided or empty, defaults to ASSETS environment variable.",
    )
    account_id: int = Field(..., description="Account identifier")
    strategy_override: Optional[str] = Field(None, description="Optional strategy override")
    force_refresh: bool = Field(False, description="Force refresh of cached data")
    ab_test_name: Optional[str] = Field(None, description="Optional A/B test name")


class BatchDecisionRequest(BaseModel):
    """Request model for batch decision generation."""

    symbols: List[str] = Field(..., description="List of trading pair symbols")
    account_id: int = Field(..., description="Account identifier")
    strategy_override: Optional[str] = Field(None, description="Optional strategy override")
    force_refresh: bool = Field(False, description="Force refresh of cached data")


class StrategySwitch(BaseModel):
    """Request model for strategy switching."""

    strategy_id: str = Field(..., description="New strategy identifier")
    switch_reason: str = Field(default="API request", description="Reason for strategy switch")
    switched_by: Optional[str] = Field(None, description="User who initiated the switch")


class DecisionHistoryResponse(BaseModel):
    """Response model for decision history."""

    decisions: List[DecisionResult]
    total_count: int
    page: int
    page_size: int


class CacheStats(BaseModel):
    """Cache statistics model."""

    decision_cache_entries: int
    context_cache_entries: int
    total_cache_entries: int
    cache_hits: int
    cache_misses: int
    cache_hit_rate: float
    memory_usage_mb: float
    active_decisions: int
    max_concurrent_decisions: int


# API Endpoints
@router.post("/generate", response_model=DecisionResult)
async def generate_decision(request: DecisionRequest) -> DecisionResult:
    """
    Generate a multi-asset trading decision for the specified symbols and account.

    This endpoint orchestrates the complete decision-making process:
    - Builds trading context from market data and account state for all assets
    - Generates LLM-powered multi-asset trading decision
    - Validates the decision against business rules
    - Returns structured decision with metadata

    If symbols are not provided, defaults to assets defined in ASSETS environment variable.

    Rate limiting: 60 requests per minute per account.
    Caching: Results cached for 3-10 minutes depending on decision type.

    Example request:
    ```json
    {
        "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
        "account_id": 1,
        "force_refresh": false
    }
    ```

    Example response includes multi-asset TradingDecision with:
    - Individual AssetDecision for each symbol
    - Portfolio-level rationale explaining overall strategy
    - Total allocation across all assets
    - Portfolio risk assessment
    """
    try:
        decision_engine = get_decision_engine()

        result = await decision_engine.make_trading_decision(
            symbols=request.symbols,  # Now accepts optional list, defaults to ASSETS env var
            account_id=request.account_id,
            strategy_override=request.strategy_override,
            force_refresh=request.force_refresh,
            ab_test_name=request.ab_test_name,
        )

        return result

    except RateLimitExceededError as e:
        raise HTTPException(status_code=429, detail=str(e)) from e
    except DecisionEngineError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Unexpected error in generate_decision: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/batch", response_model=List[DecisionResult])
async def generate_batch_decisions(request: BatchDecisionRequest) -> List[DecisionResult]:
    """
    Generate trading decisions for multiple symbols concurrently.

    This endpoint processes multiple symbols in parallel for improved performance.
    Each symbol is processed independently, so failures on one symbol won't
    affect others.

    Rate limiting: Applied per account across all symbols.
    Concurrency: Limited to prevent resource exhaustion.
    """
    try:
        if len(request.symbols) > 20:
            raise HTTPException(
                status_code=400, detail="Maximum 20 symbols allowed per batch request"
            )

        decision_engine = get_decision_engine()

        results = await decision_engine.batch_decisions(
            symbols=request.symbols,
            account_id=request.account_id,
            strategy_override=request.strategy_override,
            force_refresh=request.force_refresh,
        )

        return results

    except RateLimitExceededError as e:
        raise HTTPException(status_code=429, detail=str(e)) from e
    except DecisionEngineError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Unexpected error in generate_batch_decisions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/history/{account_id}", response_model=DecisionHistoryResponse)
async def get_decision_history(
    account_id: int,
    symbol: Annotated[
        Optional[str],
        Query(
            description="Optional symbol filter. Filters asset decisions within multi-asset decisions "
            "to show only decisions for the specified symbol.",
        ),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=1000, description="Number of decisions to return")] = 100,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    start_date: Annotated[Optional[datetime], Query(description="Start date filter")] = None,
    end_date: Annotated[Optional[datetime], Query(description="End date filter")] = None,
) -> DecisionHistoryResponse:
    """
    Get decision history for an account with optional filtering.

    Returns paginated list of historical multi-asset decisions with metadata.
    Supports filtering by symbol, date range, and pagination.

    When symbol filter is provided:
    - Returns all multi-asset decisions for the account
    - Each decision's asset_decisions list is filtered to include only the specified symbol
    - Portfolio-level rationale and metadata are preserved

    Example:
    - GET /api/v1/decisions/history/1?symbol=BTCUSDT
      Returns all decisions for account 1, showing only BTC-related asset decisions

    - GET /api/v1/decisions/history/1
      Returns all decisions for account 1 with all asset decisions included
    """
    try:
        decision_engine = get_decision_engine()

        # Calculate offset for pagination
        offset = (page - 1) * limit

        decisions = await decision_engine.get_decision_history(
            account_id=account_id,
            symbol=symbol,  # Symbol filter now filters asset decisions within multi-asset decisions
            limit=limit,
            start_date=start_date,
            end_date=end_date,
        )

        # Apply pagination (simplified - in real implementation, this would be done in the database)
        paginated_decisions = decisions[offset : offset + limit]

        return DecisionHistoryResponse(
            decisions=paginated_decisions, total_count=len(decisions), page=page, page_size=limit
        )

    except Exception as e:
        logger.error(f"Error getting decision history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/validate", response_model=Dict[str, Any])
async def validate_decision(decision: TradingDecision) -> Dict[str, Any]:
    """
    Validate a multi-asset trading decision without executing it.

    This endpoint allows testing decision validation logic
    without generating a full decision through the LLM.

    Accepts a multi-asset TradingDecision with:
    - List of AssetDecision objects for each asset
    - Portfolio-level rationale
    - Total allocation across all assets
    - Portfolio risk level

    Returns validation results including:
    - Overall validity status
    - List of validation errors (if any)
    - List of validation warnings
    - Validation time in milliseconds
    - Number of rules checked

    Example request:
    ```json
    {
        "decisions": [
            {
                "asset": "BTCUSDT",
                "action": "buy",
                "allocation_usd": 1000.0,
                "tp_price": 52000.0,
                "sl_price": 48000.0,
                "exit_plan": "Take profit at resistance",
                "rationale": "Strong bullish momentum",
                "confidence": 75.0,
                "risk_level": "medium"
            }
        ],
        "portfolio_rationale": "Bullish market conditions",
        "total_allocation_usd": 1000.0,
        "portfolio_risk_level": "medium"
    }
    ```
    """
    try:
        # Create minimal multi-asset context for validation
        # In a real implementation, this would use actual account/market data
        from ...schemas.trading_decision import (
            AccountContext,
            AssetMarketData,
            MarketContext,
            PerformanceMetrics,
            PricePoint,
            RiskMetrics,
            StrategyRiskParameters,
            TechnicalIndicators,
            TechnicalIndicatorsSet,
            TradingContext,
            TradingStrategy,
        )
        from ...services.llm.decision_validator import get_decision_validator

        # Create a minimal trading strategy
        strategy = TradingStrategy(
            strategy_id="placeholder",
            strategy_name="placeholder",
            strategy_type="conservative",
            prompt_template="",
            risk_parameters=StrategyRiskParameters(
                max_risk_per_trade=2.0,
                max_daily_loss=5.0,
                stop_loss_percentage=5.0,
                take_profit_ratio=2.0,
                max_leverage=1.0,
                cooldown_period=300,
            ),
            is_active=True,
        )

        # Extract symbols from decision
        symbols = [asset_decision.asset for asset_decision in decision.decisions]

        # Create placeholder market data for each asset
        assets_market_data = {}
        for symbol in symbols:
            assets_market_data[symbol] = AssetMarketData(
                symbol=symbol,
                current_price=50000.0,  # Placeholder
                price_change_24h=0.0,
                volume_24h=1000000.0,
                funding_rate=0.0001,
                open_interest=1000000.0,
                volatility=2.5,
                price_history=[PricePoint(timestamp=datetime.now(timezone.utc), price=50000.0)],
                technical_indicators=TechnicalIndicators(
                    interval=TechnicalIndicatorsSet(),
                    long_interval=TechnicalIndicatorsSet(),
                ),
            )

        context = TradingContext(
            symbols=symbols,
            account_id=1,  # Placeholder
            timeframes=["5m", "1h"],
            market_data=MarketContext(
                assets=assets_market_data,
                market_sentiment="neutral",
            ),
            account_state=AccountContext(
                account_id=1,
                balance_usd=10000.0,
                available_balance=8000.0,
                total_pnl=0.0,
                recent_performance=PerformanceMetrics(
                    total_pnl=0.0,
                    win_rate=50.0,
                    avg_win=100.0,
                    avg_loss=-80.0,
                    max_drawdown=500.0,
                    sharpe_ratio=1.0,
                ),
                risk_exposure=20.0,
                max_position_size=2000.0,
                active_strategy=strategy,
            ),
            recent_trades={symbol: [] for symbol in symbols},
            risk_metrics=RiskMetrics(
                var_95=500.0,
                max_drawdown=500.0,
                correlation_risk=20.0,
                concentration_risk=30.0,
            ),
        )

        validator = get_decision_validator()
        result = await validator.validate_decision(decision, context)

        return {
            "is_valid": result.is_valid,
            "errors": result.errors,
            "warnings": result.warnings,
            "validation_time_ms": result.validation_time_ms,
            "rules_checked": result.rules_checked,
        }

    except Exception as e:
        logger.error(f"Error validating decision: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/strategies/{account_id}/switch")
async def switch_strategy(account_id: int, request: StrategySwitch) -> Dict[str, Any]:
    """
    Switch the trading strategy for an account.

    This endpoint changes the active strategy for an account and
    invalidates related caches to ensure new decisions use the new strategy.
    """
    try:
        decision_engine = get_decision_engine()

        success = await decision_engine.switch_strategy(
            account_id=account_id,
            strategy_id=request.strategy_id,
            switch_reason=request.switch_reason,
            switched_by=request.switched_by,
        )

        return {
            "success": success,
            "message": f"Strategy switched to {request.strategy_id}",
            "account_id": account_id,
            "new_strategy": request.strategy_id,
            "switch_reason": request.switch_reason,
        }

    except DecisionEngineError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error switching strategy: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/health", response_model=HealthStatus)
async def get_engine_health() -> HealthStatus:
    """
    Get the health status of the decision engine.

    Returns comprehensive health information including:
    - Overall engine health
    - LLM service connectivity
    - Cache performance
    - Active processing status
    """
    try:
        decision_engine = get_decision_engine()
        health_status = await decision_engine.get_engine_health()
        return health_status

    except Exception as e:
        logger.error(f"Error getting engine health: {e}", exc_info=True)
        return HealthStatus(
            is_healthy=False,
            consecutive_failures=999,
            circuit_breaker_open=True,
            error_message=f"Health check failed: {str(e)}",
        )


@router.get("/metrics", response_model=UsageMetrics)
async def get_usage_metrics(
    timeframe_hours: Annotated[
        int, Query(ge=1, le=168, description="Hours to look back for metrics")
    ] = 24,
) -> UsageMetrics:
    """
    Get usage metrics for the decision engine.

    Returns comprehensive usage statistics including:
    - Request counts and success rates
    - Performance metrics
    - Cost information
    - Uptime statistics
    """
    try:
        decision_engine = get_decision_engine()
        metrics = decision_engine.get_usage_metrics(timeframe_hours)
        return metrics

    except Exception as e:
        logger.error(f"Error getting usage metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/cache/stats", response_model=CacheStats)
async def get_cache_stats() -> CacheStats:
    """
    Get cache statistics and performance metrics.

    Returns detailed information about cache usage, hit rates,
    and memory consumption.
    """
    try:
        decision_engine = get_decision_engine()
        stats = decision_engine.get_cache_stats()

        return CacheStats(**stats)

    except Exception as e:
        logger.error(f"Error getting cache stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/cache/clear")
async def clear_cache(
    background_tasks: BackgroundTasks,
    account_id: Annotated[
        Optional[int], Query(description="Clear cache for specific account")
    ] = None,
    symbol: Annotated[Optional[str], Query(description="Clear cache for specific symbol")] = None,
) -> Dict[str, Any]:
    """
    Clear decision engine caches.

    Supports clearing all caches or filtering by account/symbol.
    Cache clearing is performed in the background to avoid blocking the request.
    """
    try:
        decision_engine = get_decision_engine()

        def clear_caches() -> None:
            if account_id:
                decision_engine._invalidate_account_caches(account_id)
                logger.info(f"Cleared caches for account {account_id}")
            elif symbol:
                decision_engine.invalidate_symbol_caches(symbol)
                logger.info(f"Cleared caches for symbol {symbol}")
            else:
                decision_engine.clear_all_caches()
                logger.info("Cleared all caches")

        background_tasks.add_task(clear_caches)

        return {
            "message": "Cache clearing initiated",
            "account_id": account_id,
            "symbol": symbol,
            "scope": "account" if account_id else "symbol" if symbol else "all",
        }

    except Exception as e:
        logger.error(f"Error clearing cache: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/metrics/reset")
async def reset_metrics() -> Dict[str, Any]:
    """
    Reset performance metrics.

    Clears all accumulated metrics and starts fresh tracking.
    Useful for testing or after maintenance periods.
    """
    try:
        decision_engine = get_decision_engine()
        decision_engine.reset_metrics()

        return {
            "message": "Metrics reset successfully",
            "reset_time": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error resetting metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e


# WebSocket endpoint for real-time decision streaming
@router.websocket("/stream/{account_id}")
async def decision_stream(websocket: WebSocket, account_id: int) -> None:
    """
    WebSocket endpoint for real-time decision streaming.

    Provides real-time updates of trading decisions for an account.
    Clients can subscribe to receive decisions as they are generated.

    Note: This is a placeholder implementation. Full WebSocket support
    would require additional infrastructure and connection management.
    """
    await websocket.accept()

    try:
        # Send initial connection confirmation
        await websocket.send_json(
            {
                "type": "connection",
                "message": f"Connected to decision stream for account {account_id}",
                "account_id": account_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for client messages (e.g., subscription requests)
                data = await websocket.receive_json()

                # Handle different message types
                if data.get("type") == "subscribe":
                    symbols = data.get("symbols", [])
                    await websocket.send_json(
                        {
                            "type": "subscription",
                            "message": f"Subscribed to {len(symbols)} symbols",
                            "symbols": symbols,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )

                elif data.get("type") == "ping":
                    await websocket.send_json(
                        {"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()}
                    )

                # TODO: Implement actual decision streaming logic
                # This would involve:
                # 1. Maintaining active subscriptions
                # 2. Generating decisions based on market events
                # 3. Streaming decisions to connected clients
                # 4. Handling connection management

            except Exception as e:
                logger.error(f"WebSocket error for account {account_id}: {e}")
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": str(e),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                break

    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        await websocket.close()
