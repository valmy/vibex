"""Candle-close scheduler for market data fetching."""

import asyncio
import logging
from datetime import datetime
from typing import Callable, Dict, List

from .events import EventManager
from .utils import calculate_next_candle_close, get_interval_seconds

logger = logging.getLogger(__name__)


class CandleScheduler:
    """Manages candle-close based scheduling."""

    # Retry configuration
    DEFAULT_RETRY_ATTEMPTS = 5
    DEFAULT_RETRY_DELAY = 1.0  # seconds
    MAX_RETRY_DELAY = 300.0  # 5 minutes

    def __init__(
        self,
        intervals: List[str],
        event_manager: EventManager,
        fetch_callback: Callable,
    ):
        """
        Initialize the candle scheduler.

        Args:
            intervals: List of intervals to schedule (e.g., ['1h', '4h'])
            event_manager: Event manager for triggering events
            fetch_callback: Async callback function to fetch and store candles
        """
        self.intervals = intervals
        self.event_manager = event_manager
        self.fetch_callback = fetch_callback

        self._is_running = False
        self._scheduled_tasks: Dict[str, asyncio.Task] = {}
        self._shutdown_event = asyncio.Event()

    async def start(self):
        """Start the candle close scheduler for all intervals."""
        if self._is_running:
            logger.warning("Scheduler is already running")
            return

        self._is_running = True
        self._shutdown_event.clear()

        # Start a task for each interval
        for interval in self.intervals:
            if interval:
                self._scheduled_tasks[interval] = asyncio.create_task(
                    self._schedule_interval(interval), name=f"candle_scheduler_{interval}"
                )
                logger.info(f"Started candle scheduler for interval: {interval}")

    async def stop(self):
        """Stop all scheduled tasks gracefully."""
        if not self._is_running:
            return

        logger.info("Stopping candle schedulers...")
        self._is_running = False
        self._shutdown_event.set()

        # Cancel all running tasks
        for task in self._scheduled_tasks.values():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._scheduled_tasks.clear()
        logger.info("All candle schedulers stopped")

    async def _schedule_interval(self, interval: str):
        """
        Schedule candle close events for a specific interval.

        Args:
            interval: Candle interval (e.g., '1h', '4h')
        """
        logger.info(f"Starting candle scheduler for interval: {interval}")

        while self._is_running and not self._shutdown_event.is_set():
            try:
                now = datetime.utcnow()
                next_close = calculate_next_candle_close(interval, now)
                wait_seconds = (next_close - now).total_seconds()

                # Log the next scheduled candle close
                logger.info(
                    f"Next {interval} candle will close at {next_close} (in {wait_seconds:.1f} seconds)"
                )

                # Sleep until the next candle close
                while wait_seconds > 0 and self._is_running and not self._shutdown_event.is_set():
                    sleep_time = min(wait_seconds, 1.0)  # Check every second
                    await asyncio.sleep(sleep_time)
                    now = datetime.utcnow()
                    wait_seconds = (next_close - now).total_seconds()

                # If we get here, it's time to process the candle close
                if self._is_running and not self._shutdown_event.is_set():
                    logger.info(f"Processing {interval} candle close at {now}")
                    await self._process_candle_close(interval)

                    # Small delay to avoid tight loop in case of errors
                    await asyncio.sleep(1)

            except asyncio.CancelledError:
                logger.info(f"Candle scheduler for {interval} was cancelled")
                raise
            except Exception as e:
                logger.error(f"Error in {interval} scheduler: {e}", exc_info=True)
                # Wait a bit before retrying, but not too long
                await asyncio.sleep(min(60, get_interval_seconds(interval) * 0.1))

    async def _process_candle_close(self, interval: str) -> None:
        """
        Process a candle close event for the specified interval.

        Fetches and stores the latest candle data for all configured assets.

        Args:
            interval: Candle interval (e.g., '1h', '4h')
        """
        logger.info("Processing %s candle close", interval)

        try:
            # Call the fetch callback to fetch and store the latest candle
            await self.fetch_callback(interval)

            # Calculate and schedule the next candle close
            next_close = calculate_next_candle_close(interval, datetime.utcnow())
            logger.info("Next %s candle will close at %s", interval, next_close)

        except Exception as e:
            logger.error("Error processing %s candle close: %s", interval, e, exc_info=True)
            raise

    async def get_status(self) -> dict:
        """
        Get the current status of the scheduler.

        Returns:
            dict: Status information including next scheduled runs
        """
        status = {"running": self._is_running, "intervals": {}, "next_runs": {}}

        now = datetime.utcnow()
        for interval in self.intervals:
            if not interval:
                continue

            next_close = calculate_next_candle_close(interval, now)
            status["intervals"][interval] = {
                "next_close": next_close.isoformat(),
                "in": (next_close - now).total_seconds(),
                "active": interval in self._scheduled_tasks,
                "seconds": get_interval_seconds(interval),
            }

        return status

