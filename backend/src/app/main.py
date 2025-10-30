"""
Main FastAPI application for the AI Trading Agent.

Initializes the FastAPI app with middleware, routes, and WebSocket handlers.
"""

import os
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import (
    accounts,
    analysis,
    decision_engine,
    diary,
    llm_decisions,
    market_data,
    monitoring,
    orders,
    performance,
    positions,
    strategies,
    trades,
    auth,
)
from .core.config import config
from .core.config_manager import get_config_manager
from .core.logging import get_logger, setup_logging
from .middleware import AdminOnlyMiddleware

# Initialize logging
setup_logging(config)
logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title=config.APP_NAME,
    description="LLM-powered cryptocurrency trading agent for AsterDEX with advanced decision engine",
    version=config.APP_VERSION,
    debug=config.DEBUG,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "Decision Engine",
            "description": "LLM-powered trading decision generation and management",
        },
        {
            "name": "Strategy Management",
            "description": "Trading strategy configuration and assignment",
        },
        {
            "name": "Monitoring & Analytics",
            "description": "System monitoring, health checks, and performance analytics",
        },
        {
            "name": "LLM Decisions",
            "description": "Direct LLM service interactions and model management",
        },
        {"name": "Market Data", "description": "Market data collection and technical analysis"},
        {
            "name": "Trading",
            "description": "Trading operations including positions, orders, and trades",
        },
        {"name": "Performance", "description": "Performance tracking and analytics"},
        {"name": "Authentication", "description": "User authentication and authorization"},
        {"name": "System", "description": "System health, status, and configuration"},
    ],
)

# Configure OpenAPI security scheme for Bearer token authentication
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    from fastapi.openapi.utils import get_openapi

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Add security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter JWT token obtained from /api/v1/auth/login"
        }
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Add CORS middleware
app.add_middleware(AdminOnlyMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(accounts.router)
app.include_router(positions.router)
app.include_router(orders.router)
app.include_router(trades.router)
app.include_router(diary.router)
app.include_router(performance.router)
app.include_router(market_data.router)
app.include_router(analysis.router)
app.include_router(llm_decisions.router)
app.include_router(decision_engine.router)
app.include_router(strategies.router)
app.include_router(monitoring.router)
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])


# Health check endpoint
@app.get("/health", tags=["System"])
async def health_check():
    """
    Basic health check endpoint.

    Returns basic application health status. For comprehensive health
    monitoring, use /api/v1/monitoring/health/system.
    """
    return {
        "status": "healthy",
        "app": config.APP_NAME,
        "version": config.APP_VERSION,
        "environment": config.ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat(),
        "detailed_health": "/api/v1/monitoring/health/system",
    }


# Status endpoint
@app.get("/status", tags=["System"])
async def status():
    """
    System status endpoint.

    Returns detailed system configuration and runtime information.
    """
    return {
        "status": "running",
        "app": config.APP_NAME,
        "version": config.APP_VERSION,
        "environment": config.ENVIRONMENT,
        "debug": config.DEBUG,
        "api_host": config.API_HOST,
        "api_port": config.API_PORT,
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "decision_engine": "active",
            "llm_service": "active",
            "strategy_manager": "active",
            "monitoring": "active",
        },
        "detailed_status": "/api/v1/monitoring/health/system",
    }


# Root endpoint
@app.get("/", tags=["System"])
async def root():
    """
    Root endpoint with API overview.

    Returns basic API information and available endpoint categories.
    """
    return {
        "message": "AI Trading Agent API with LLM Decision Engine",
        "version": config.APP_VERSION,
        "environment": config.ENVIRONMENT,
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi": "/openapi.json",
        "endpoints": {
            "decision_engine": "/api/v1/decisions",
            "strategies": "/api/v1/strategies",
            "monitoring": "/api/v1/monitoring",
            "llm_decisions": "/api/v1/decisions",
            "market_data": "/api/v1/market-data",
            "trading": {
                "accounts": "/api/v1/accounts",
                "positions": "/api/v1/positions",
                "orders": "/api/v1/orders",
                "trades": "/api/v1/trades",
            },
            "performance": "/api/v1/performance",
            "system": {"health": "/health", "status": "/status"},
        },
        "features": [
            "LLM-powered trading decisions",
            "Multi-strategy support",
            "Real-time monitoring",
            "Performance analytics",
            "Risk management",
            "A/B testing",
            "Multi-account support",
        ],
    }


# Error handlers
from .services.llm.decision_engine import DecisionEngineError, RateLimitExceededError
from .core.exceptions import ValidationError, ConfigurationError


@app.exception_handler(DecisionEngineError)
async def decision_engine_exception_handler(request, exc):
    """Handle decision engine specific exceptions."""
    logger.error(f"Decision engine error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc), "error_type": "decision_engine_error"},
    )


@app.exception_handler(RateLimitExceededError)
async def rate_limit_exception_handler(request, exc):
    """Handle rate limit exceeded exceptions."""
    logger.warning(f"Rate limit exceeded: {exc}")
    return JSONResponse(
        status_code=429,
        content={"detail": str(exc), "error_type": "rate_limit_exceeded"},
    )


@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc):
    """Handle validation errors."""
    logger.warning(f"Validation error: {exc}")
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc), "error_type": "validation_error"},
    )


@app.exception_handler(ConfigurationError)
async def configuration_exception_handler(request, exc):
    """Handle configuration errors."""
    logger.error(f"Configuration error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "error_type": "configuration_error"},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Startup event
@app.on_event("startup")
async def startup_event():
    """Handle startup event."""
    logger.info(f"Starting {config.APP_NAME} v{config.APP_VERSION}")
    logger.info(f"Environment: {config.ENVIRONMENT}")

    # Initialize configuration manager
    try:
        config_manager = get_config_manager()
        await config_manager.initialize()
        logger.info("Configuration manager initialized")
    except Exception as e:
        logger.error(f"Failed to initialize configuration manager: {e}")
        raise

    # Initialize database
    try:
        from .db.session import init_db

        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    # Initialize market data service with candle-close scheduling
    try:
        from .services import get_market_data_service

        market_data_service = get_market_data_service()

        # Start the scheduler for both intervals
        await market_data_service.start_scheduler()
        logger.info("Candle-close scheduler started")

        # Log scheduler status
        status = await market_data_service.get_scheduler_status()
        logger.info(f"Scheduler status: {status}")

    except Exception as e:
        logger.error(f"Failed to start candle-close scheduler: {e}")
        raise


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Handle shutdown event."""
    logger.info(f"Shutting down {config.APP_NAME}")

    # Shutdown configuration manager
    try:
        config_manager = get_config_manager()
        await config_manager.shutdown()
        logger.info("Configuration manager shut down")
    except Exception as e:
        logger.error(f"Error shutting down configuration manager: {e}")

    # Stop the market data scheduler
    try:
        from .services import get_market_data_service

        market_data_service = get_market_data_service()
        await market_data_service.stop_scheduler()
        logger.info("Market data scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping market data scheduler: {e}")

    # Shutdown decision engine
    try:
        from .services.llm.decision_engine import get_decision_engine

        decision_engine = get_decision_engine()
        await decision_engine.shutdown()
        logger.info("Decision engine shut down")
    except Exception as e:
        logger.error(f"Error shutting down decision engine: {e}")

    # Close any remaining database connections
    try:
        from .db.session import close_db

        await close_db()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")


# Mount static files if they exist
static_dir = os.path.join(os.path.dirname(__file__), "..", "..", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=config.API_HOST,
        port=config.API_PORT,
        reload=config.DEBUG,
        log_level=config.LOG_LEVEL.lower(),
    )
