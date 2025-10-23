"""
Main FastAPI application for the AI Trading Agent.

Initializes the FastAPI app with middleware, routes, and WebSocket handlers.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import os

from .core.config import config
from .core.logging import setup_logging, get_logger
from .db import init_db, close_db, check_db_health
from .api.routes import accounts, positions, orders, trades, diary, performance, market_data, analysis

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
    logger.info(f"Debug mode: {config.DEBUG}")
    logger.info(f"API listening on {config.API_HOST}:{config.API_PORT}")

    # Initialize database
    try:
        await init_db()
        db_health = await check_db_health()
        if db_health:
            logger.info("Database connection successful")
        else:
            logger.warning("Database health check failed")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Handle shutdown event."""
    logger.info(f"Shutting down {config.APP_NAME}")

    # Close database
    try:
        await close_db()
    except Exception as e:
        logger.error(f"Error closing database: {e}")


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

