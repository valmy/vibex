"""
Test script for the candle-close based scheduler.

This script demonstrates how to use the MarketDataService with the new
candle-close based scheduling system.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.services.market_data_service import CandleCloseEvent, EventType, MarketDataService

from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("candle_scheduler_test.log")],
)
logger = logging.getLogger(__name__)

# Global service instance
market_data_service = None


async def candle_close_handler(event: CandleCloseEvent):
    """Handle candle close events."""
    logger.info(
        f"Candle closed - Symbol: {event.symbol}, "
        f"Interval: {event.interval}, "
        f"Close Time: {event.close_time}, "
        f"Close Price: {event.candle[4]}"
    )


async def main():
    """Test the candle-close scheduler."""
    global market_data_service

    logger.info("Starting candle-close scheduler test...")

    try:
        # Initialize the MarketDataService with test configuration
        market_data_service = MarketDataService(
            interval=settings.INTERVAL,
            long_interval=settings.LONG_INTERVAL,
            symbols=settings.SYMBOLS,
            max_retries=3,
            retry_delay=1,
        )

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
        logger.info(f"Initial scheduler status: {status}")

        # Keep the script running
        while True:
            await asyncio.sleep(60)

            # Log status every minute
            status = await market_data_service.get_scheduler_status()
            logger.debug(f"Scheduler status: {status}")

    except asyncio.CancelledError:
        logger.info("Received cancellation signal, shutting down...")
    except Exception as e:
        logger.error(f"Error in test: {e}", exc_info=True)
    finally:
        # Clean up
        if market_data_service:
            await market_data_service.stop_scheduler()
        logger.info("Test completed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
