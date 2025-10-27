"""
Main FastAPI application for the AI Trading Agent.

Initializes the FastAPI app with middleware, routes, and WebSocket handlers.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import (
    accounts,
    analysis,
    diary,
    market_data,
    orders,
    performance,
    positions,
    trades,
)
from .core.config import config
from .core.config_manager import get_config_manager
from .core.logging import get_logger, setup_logging
from .db import check_db_health, close_db, init_db

# Initialize logging
setup_logging(config)
logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title=config.APP_NAME,
    description="LLM-powered cryptocurrency trading agent for AsterDEX",
    version=config.APP_VERSION,
    debug=config.DEBUG,
)

# Add CORS middleware
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


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": config.APP_NAME,
        "version": config.APP_VERSION,
        "environment": config.ENVIRONMENT,
    }


# Status endpoint
@app.get("/status")
async def status():
    """System status endpoint."""
    return {
        "status": "running",
        "app": config.APP_NAME,
        "version": config.APP_VERSION,
        "environment": config.ENVIRONMENT,
        "debug": config.DEBUG,
        "api_host": config.API_HOST,
        "api_port": config.API_PORT,
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "AI Trading Agent API",
        "version": config.APP_VERSION,
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


# Error handlers
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
