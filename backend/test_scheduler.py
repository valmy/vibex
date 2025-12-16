#!/usr/bin/env python3
"""
Test script for the candle-close scheduler.

This script demonstrates the candle-close based scheduling system.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.absolute()))

from src.app.core.config import config as settings
from src.app.services.market_data_service import CandleCloseEvent, EventType, MarketDataService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("scheduler_test.log")],
)
logger = logging.getLogger(__name__)


async def candle_close_handler(event: CandleCloseEvent) -> None:
    """Handle candle close events."""
    logger.info(
        "Candle close event received - Symbol: %s, Interval: %s, Time: %s, "
        "Open: %s, High: %s, Low: %s, Close: %s, Volume: %s",
        event.symbol,
        event.interval,
        event.timestamp,
        event.candle[1],  # Open
        event.candle[2],  # High
        event.candle[3],  # Low
        event.candle[4],  # Close
        event.candle[5],  # Volume
    )


async def test_scheduler():
    """Test the candle-close scheduler."""
    logger.info("Starting candle-close scheduler test...")

    try:
        # Initialize the MarketDataService
        market_data_service = MarketDataService()

        # Register event handlers for both intervals
        market_data_service.register_event_handler(
            EventType.CANDLE_CLOSE, candle_close_handler, interval=settings.INTERVAL
        )

        if settings.INTERVAL != settings.LONG_INTERVAL:
            market_data_service.register_event_handler(
                EventType.CANDLE_CLOSE, candle_close_handler, interval=settings.LONG_INTERVAL
            )

        # Start the scheduler
        await market_data_service.start_scheduler()

        # Log initial status
        status = await market_data_service.get_scheduler_status()
        logger.info("Scheduler status: %s", status)

        # Keep the script running
        logger.info("Scheduler is running. Press Ctrl+C to stop...")
        while True:
            await asyncio.sleep(1)

    except asyncio.CancelledError:
        logger.info("Shutting down scheduler...")
        await market_data_service.stop_scheduler()
        logger.info("Scheduler stopped")
    except Exception as e:
        logger.error("Error in scheduler test: %s", e, exc_info=True)
        raise


if __name__ == "__main__":
    try:
        asyncio.run(test_scheduler())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error("Test failed: %s", e, exc_info=True)
        sys.exit(1)
