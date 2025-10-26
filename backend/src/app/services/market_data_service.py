"""
Market Data Service for fetching and managing real-time market data.

Implements candle-close based data fetching with event-driven architecture.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, TypeVar

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import config
from ..models.market_data import MarketData

logger = logging.getLogger(__name__)

# Type variable for generic event handling
T = TypeVar("T")


@dataclass
class BaseEvent:
    """Base class for all market data events."""

    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CandleCloseEvent(BaseEvent):
    """Event triggered when a candle closes."""

    symbol: str = ""
    interval: str = ""
    candle: dict = field(default_factory=dict)  # Raw candle data
    close_time: datetime = field(default_factory=datetime.utcnow)


class EventType(Enum):
    CANDLE_CLOSE = auto()
    # Add other event types as needed


def event_handler(event_type: EventType, interval: str = None):
    """
    Decorator for event handler methods.

    Args:
        event_type: The type of event to handle.
        interval: Optional interval filter for the event.
    """

    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        wrapper._is_event_handler = True
        wrapper._event_type = event_type
        wrapper._interval = interval
        return wrapper

    return decorator


class MarketDataService:
    """
    Service for managing market data operations with candle-close based scheduling.

    Features:
    - Interval-based candle close scheduling
    - Event-driven architecture
    - Automatic retries with backoff
    - Support for multiple intervals (e.g., 1h, 4h)
    """

    # Default retry configuration
    DEFAULT_RETRY_ATTEMPTS = 5
    DEFAULT_RETRY_DELAY = 1.0  # seconds
    MAX_RETRY_DELAY = 300.0  # 5 minutes

    def __init__(self):
        """Initialize the Market Data Service."""
        self.api_key = config.ASTERDEX_API_KEY
        self.api_secret = config.ASTERDEX_API_SECRET
        self.base_url = config.ASTERDEX_BASE_URL
        self.assets = [asset.strip() for asset in config.ASSETS.split(",") if asset.strip()]
        self.interval = config.INTERVAL
        self.long_interval = config.LONG_INTERVAL

        # Validate intervals
        if self.interval not in ["1m", "5m", "1h", "4h", "1d"]:
            raise ValueError(f"Invalid interval: {self.interval}")
        if self.long_interval not in ["1m", "5m", "1h", "4h", "1d"]:
            raise ValueError(f"Invalid long_interval: {self.long_interval}")

        # Scheduler state
        self._is_running = False
        self._scheduled_tasks: Dict[str, asyncio.Task] = {}
        self._event_handlers: Dict[EventType, Dict[Optional[str], List[Callable]]] = {
            EventType.CANDLE_CLOSE: {}
        }
        self._shutdown_event = asyncio.Event()
        self._fetch_lock = asyncio.Lock()

        # Aster client is created on-demand via the `aster_client` property
        # to ensure thread-safety and prevent stale connections.

        # Register default error handler
        self.register_event_handler(EventType.CANDLE_CLOSE, self._default_candle_close_handler)

    def register_event_handler(
        self, event_type: EventType, handler: Callable, interval: str = None
    ):
        """Register an event handler for a specific event type and optional interval."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = {}

        if interval not in self._event_handlers[event_type]:
            self._event_handlers[event_type][interval] = []

        self._event_handlers[event_type][interval].append(handler)
        logger.debug(
            f"Registered {event_type.name} handler for interval {interval}: {handler.__name__}"
        )

    async def _default_candle_close_handler(self, event: CandleCloseEvent):
        """Default handler for candle close events."""
        logger.info(f"Candle closed: {event.symbol} {event.interval} at {event.close_time}")

    async def _trigger_event(self, event: BaseEvent, event_type: EventType, interval: str = None):
        """Trigger all handlers for a specific event type and optional interval."""
        if event_type not in self._event_handlers:
            return

        # Get handlers for this specific interval and global handlers (None interval)
        handlers = []
        if interval in self._event_handlers[event_type]:
            handlers.extend(self._event_handlers[event_type][interval])
        if None in self._event_handlers[event_type]:
            handlers.extend(self._event_handlers[event_type][None])

        # Execute all handlers concurrently
        if handlers:
            await asyncio.gather(
                *[self._safe_execute_handler(h, event) for h in handlers], return_exceptions=True
            )

    async def _safe_execute_handler(self, handler: Callable, event: BaseEvent):
        """Execute a single event handler with error handling."""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                # Handle synchronous handlers
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, handler, event)
        except Exception as e:
            logger.error(f"Error in {handler.__name__}: {e}", exc_info=True)

    # Candle close scheduling methods
    async def start_scheduler(self):
        """Start the candle close scheduler for all intervals."""
        if self._is_running:
            logger.warning("Scheduler is already running")
            return

        self._is_running = True
        self._shutdown_event.clear()

        # Start a task for each interval
        for interval in {self.interval, self.long_interval}:
            if interval:
                self._scheduled_tasks[interval] = asyncio.create_task(
                    self._schedule_interval(interval), name=f"candle_scheduler_{interval}"
                )
                logger.info(f"Started candle scheduler for interval: {interval}")

    async def stop_scheduler(self):
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
        """Schedule candle close events for a specific interval."""
        logger.info(f"Starting candle scheduler for interval: {interval}")

        while self._is_running and not self._shutdown_event.is_set():
            try:
                now = datetime.utcnow()
                next_close = self._calculate_next_candle_close(interval, now)
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
                await asyncio.sleep(min(60, self._get_interval_seconds(interval) * 0.1))

    async def _process_candle_close(self, interval: str) -> None:
        """Process a candle close event for the specified interval.

        Fetches and stores the latest candle data for all configured assets.
        """
        logger.info("Processing %s candle close", interval)

        try:
            # Fetch and store the latest candle data for all configured assets
            await self._fetch_and_store_latest_candle(interval)

            # Calculate and schedule the next candle close
            next_close = self._calculate_next_candle_close(interval, datetime.utcnow())
            logger.info("Next %s candle will close at %s", interval, next_close)

        except Exception as e:
            logger.error("Error processing %s candle close: %s", interval, e, exc_info=True)
            raise

    async def _fetch_and_store_latest_candle(self, interval: str) -> bool:
        """Fetch and store the latest candle for all configured assets.

        Args:
            interval: Candle interval (e.g., '1h', '4h')

        Returns:
            bool: True if all assets were processed successfully, False otherwise
        """
        # Import here to get the initialized version
        from ..db.session import AsyncSessionLocal

        # Check if database is initialized
        if AsyncSessionLocal is None:
            raise RuntimeError("Database not initialized. AsyncSessionLocal is None.")

        # Process each configured asset
        all_successful = True
        for asset in self.assets:
            # Format symbol (e.g., "BTC" -> "BTCUSDT")
            symbol = f"{asset}USDT" if "USDT" not in asset.upper() else asset

            retry_count = 0
            last_error = None
            success = False

            while retry_count < self.DEFAULT_RETRY_ATTEMPTS and not self._shutdown_event.is_set():
                try:
                    async with self._fetch_lock, AsyncSessionLocal() as db:
                        # Add a small delay to ensure the candle is closed
                        await asyncio.sleep(1)

                        # Use the existing fetch_market_data method to get the latest candles
                        candles = await self.fetch_market_data(
                            symbol=symbol,
                            interval=interval,
                            limit=2,  # Get current and previous candle for validation
                        )

                        if not candles or len(candles) < 1:
                            raise ValueError(f"No candle data returned for {symbol}")

                        # The last candle is the most recent one
                        latest_candle = candles[-1]
                        candle_time = datetime.fromtimestamp(latest_candle[0] / 1000)

                        # Validate we got the latest candle
                        expected_close = self._calculate_previous_candle_close(
                            interval, datetime.utcnow()
                        )
                        if (
                            abs((candle_time - expected_close).total_seconds()) > 60
                        ):  # 1 min tolerance
                            raise ValueError(
                                f"Received stale candle data for {symbol}. Expected close at {expected_close}, got {candle_time}"
                            )

                        # Store the candle data
                        await self.store_market_data(
                            db=db,
                            symbol=symbol,
                            interval=interval,
                            data=[latest_candle],
                        )

                        # Commit the transaction
                        await db.commit()

                        # Trigger event handlers
                        event = CandleCloseEvent(
                            symbol=symbol,
                            interval=interval,
                            candle=latest_candle,
                            close_time=candle_time,
                        )
                        await self._trigger_event(event, EventType.CANDLE_CLOSE, interval)

                        logger.info(
                            f"Processed {interval} candle close for {symbol} at {candle_time}"
                        )
                        success = True
                        break  # Success, exit retry loop

                except Exception as e:
                    last_error = e
                    retry_delay = min(5 * (2**retry_count), 60)  # Exponential backoff, max 60s
                    logger.warning(
                        f"Attempt {retry_count + 1}/{self.DEFAULT_RETRY_ATTEMPTS} failed for {symbol} ({interval}): {e}. "
                        f"Retrying in {retry_delay}s..."
                    )
                    await asyncio.sleep(retry_delay)
                    retry_count += 1

            if not success:
                all_successful = False
                if last_error:
                    logger.error(
                        f"Failed to fetch {interval} candle for {symbol} after {self.DEFAULT_RETRY_ATTEMPTS} attempts: {last_error}"
                    )

        return all_successful

    def _calculate_next_candle_close(self, interval: str, current_time: datetime) -> datetime:
        """
        Calculate the next candle close time for a given interval.

        Args:
            interval: Candle interval (e.g., '1h', '4h')
            current_time: Current UTC time

        Returns:
            datetime: Next candle close time in UTC
        """
        interval_seconds = self._get_interval_seconds(interval)
        current_timestamp = int(current_time.timestamp())

        # Calculate the next close time
        next_close_timestamp = (
            current_timestamp - (current_timestamp % interval_seconds) + interval_seconds
        )
        return datetime.utcfromtimestamp(next_close_timestamp)

    def _calculate_previous_candle_close(self, interval: str, current_time: datetime) -> datetime:
        """
        Calculate the most recent candle close time for a given interval.

        Args:
            interval: Candle interval (e.g., '1h', '4h')
            current_time: Current UTC time

        Returns:
            datetime: Previous candle close time in UTC
        """
        interval_seconds = self._get_interval_seconds(interval)
        current_timestamp = int(current_time.timestamp())

        # Calculate the previous close time
        prev_close_timestamp = current_timestamp - (current_timestamp % interval_seconds)
        return datetime.utcfromtimestamp(prev_close_timestamp)

    def _get_interval_seconds(self, interval: str) -> int:
        """
        Convert interval string to seconds.

        Args:
            interval: Candle interval (e.g., '1m', '5m', '1h', '4h', '1d')

        Returns:
            int: Interval duration in seconds

        Raises:
            ValueError: If the interval format is invalid
        """
        if not interval:
            raise ValueError("Interval cannot be empty")

        if interval.endswith("m"):
            return int(interval[:-1]) * 60
        elif interval.endswith("h"):
            return int(interval[:-1]) * 3600
        elif interval.endswith("d"):
            return int(interval[:-1]) * 86400
        else:
            raise ValueError(f"Invalid interval format: {interval}")

    async def get_scheduler_status(self) -> dict:
        """
        Get the current status of the scheduler.

        Returns:
            dict: Status information including next scheduled runs
        """
        status = {"running": self._is_running, "intervals": {}, "next_runs": {}}

        now = datetime.utcnow()
        for interval in {self.interval, self.long_interval}:
            if not interval:
                continue

            next_close = self._calculate_next_candle_close(interval, now)
            status["intervals"][interval] = {
                "next_close": next_close.isoformat(),
                "in": (next_close - now).total_seconds(),
                "active": interval in self._scheduled_tasks,
                "seconds": self._get_interval_seconds(interval),
            }

        return status

    @property
    def aster_client(self):
        """
        Create and return a new Aster REST API client on each access.

        This approach avoids issues with thread-safety and stale connections
        by ensuring each operation gets a fresh, isolated client instance.
        """
        try:
            from aster.rest_api import Client

            # Create a new client instance for each call.
            client = Client(key=self.api_key, secret=self.api_secret, base_url=self.base_url)
            logger.debug("New Aster REST API client instance created.")
            return client
        except Exception as e:
            logger.error(f"Failed to initialize Aster client: {e}", exc_info=True)
            raise

    async def fetch_market_data(
        self, symbol: str, interval: str = "1h", limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetch market data from Aster DEX.

        This method uses the aster_client property and fetches data within a separate
        thread to avoid blocking the async event loop with synchronous I/O.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            interval: Candle interval (e.g., "1m", "1h", "4h")
            limit: Number of candles to fetch

        Returns:
            List of candle data dictionaries

        Raises:
            Exception: If the API call fails
        """
        try:
            # The actual fetching is done in a separate thread to handle blocking I/O.
            def _fetch_in_thread():
                try:
                    # Use the aster_client property to get a fresh client instance
                    client = self.aster_client

                    # Call klines with positional arguments for symbol and interval
                    result = client.klines(symbol, interval, limit=limit)
                    return result

                except Exception as e:
                    logger.error(f"Error fetching market data in thread: {e}", exc_info=True)
                    raise

            # Run the blocking I/O in a thread pool
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, _fetch_in_thread)

            logger.debug(f"Successfully fetched {len(data)} candles for {symbol} ({interval})")
            return data
        except Exception as e:
            # This will catch errors from the thread and log them.
            logger.error(f"Error in fetch_market_data task: {e}", exc_info=True)
            raise

    async def store_market_data(
        self,
        db: AsyncSession,
        symbol: str,
        interval: str,
        data: List[List],  # API returns list of lists
    ) -> int:
        """
        Store market data in TimescaleDB with upsert to handle duplicates.

        Args:
            db: Database session
            symbol: Trading pair symbol
            interval: Candlestick interval
            data: List of market data (from API as list of lists)

        Returns:
            Number of records stored or updated
        """
        try:
            count = 0
            for candle in data:
                # Parse candle data from list format
                # Format: [open_time, open, high, low, close, volume, close_time, quote_asset_volume,
                #          number_of_trades, taker_buy_base_asset_volume, taker_buy_quote_asset_volume, ignore]
                candle_time = datetime.fromtimestamp(candle[0] / 1000)  # open_time

                # Check if record already exists
                existing = await db.execute(
                    select(MarketData).where(
                        MarketData.symbol == symbol,
                        MarketData.interval == interval,
                        MarketData.time == candle_time,
                    )
                )
                existing = existing.scalar_one_or_none()

                if existing:
                    # Update existing record
                    existing.open = float(candle[1])
                    existing.high = float(candle[2])
                    existing.low = float(candle[3])
                    existing.close = float(candle[4])
                    existing.volume = float(candle[5])
                    existing.quote_asset_volume = float(candle[7]) if len(candle) > 7 else 0.0
                    existing.number_of_trades = float(candle[8]) if len(candle) > 8 else 0.0
                    existing.taker_buy_base_asset_volume = (
                        float(candle[9]) if len(candle) > 9 else 0.0
                    )
                    existing.taker_buy_quote_asset_volume = (
                        float(candle[10]) if len(candle) > 10 else 0.0
                    )
                    logger.debug(f"Updated existing market data for {symbol} at {candle_time}")
                else:
                    # Create new record
                    market_data = MarketData(
                        symbol=symbol,
                        interval=interval,
                        time=candle_time,
                        open=float(candle[1]),
                        high=float(candle[2]),
                        low=float(candle[3]),
                        close=float(candle[4]),
                        volume=float(candle[5]),
                        quote_asset_volume=float(candle[7]) if len(candle) > 7 else 0.0,
                        number_of_trades=float(candle[8]) if len(candle) > 8 else 0.0,
                        taker_buy_base_asset_volume=float(candle[9]) if len(candle) > 9 else 0.0,
                        taker_buy_quote_asset_volume=float(candle[10]) if len(candle) > 10 else 0.0,
                    )
                    db.add(market_data)
                    logger.debug(f"Added new market data for {symbol} at {candle_time}")

                count += 1

                # Commit in batches to improve performance
                if count % 100 == 0:
                    await db.commit()

            await db.commit()
            logger.info(f"Processed {count} market data records for {symbol}")
            return count
        except Exception as e:
            await db.rollback()
            logger.error(f"Error storing market data: {e}")
            raise

    async def get_latest_market_data(
        self, db: AsyncSession, symbol: str, interval: str = "1h", limit: int = 100
    ) -> List[MarketData]:
        """
        Get latest market data from database.

        Args:
            db: Database session
            symbol: Trading pair symbol
            interval: Candlestick interval
            limit: Number of records to fetch

        Returns:
            List of MarketData records
        """
        try:
            result = await db.execute(
                select(MarketData)
                .where(and_(MarketData.symbol == symbol, MarketData.interval == interval))
                .order_by(MarketData.time.desc())
                .limit(limit)
            )
            data = result.scalars().all()
            return list(reversed(data))  # Return in ascending order
        except Exception as e:
            logger.error(f"Error retrieving market data: {e}")
            raise

    async def get_market_data_range(
        self, db: AsyncSession, symbol: str, interval: str, start_time: datetime, end_time: datetime
    ) -> List[MarketData]:
        """
        Get market data within a time range.

        Args:
            db: Database session
            symbol: Trading pair symbol
            interval: Candlestick interval
            start_time: Start time
            end_time: End time

        Returns:
            List of MarketData records
        """
        try:
            result = await db.execute(
                select(MarketData)
                .where(
                    and_(
                        MarketData.symbol == symbol,
                        MarketData.interval == interval,
                        MarketData.time >= start_time,
                        MarketData.time <= end_time,
                    )
                )
                .order_by(MarketData.time.asc())
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error retrieving market data range: {e}")
            raise

    async def sync_market_data(
        self, db: AsyncSession, symbol: Optional[str] = None, interval: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Sync market data from Aster DEX to database.

        Args:
            db: Database session
            symbol: Optional specific symbol to sync
            interval: Optional specific interval to sync (if None, syncs both short and long intervals)

        Returns:
            Dictionary with sync results
        """
        symbols = [symbol] if symbol else self.assets
        intervals = [interval] if interval else [self.interval, self.long_interval]
        results = {}

        for sym in symbols:
            try:
                # Ensure symbol is in proper format (add USDT as quote currency if needed)
                # AsterDEX typically uses format like BTCUSDT, ETHUSDT, etc.
                formatted_symbol = f"{sym}USDT" if "USDT" not in sym.upper() else sym

                # Fetch and store market data for each interval
                for interval in intervals:
                    try:
                        data = await self.fetch_market_data(formatted_symbol, interval)
                        count = await self.store_market_data(db, formatted_symbol, interval, data)
                        results[f"{formatted_symbol}_{interval}"] = count
                        logger.info(f"Synced {count} records for {formatted_symbol} ({interval})")
                    except Exception as e:
                        logger.error(f"Error syncing {formatted_symbol} ({interval}): {e}")
                        results[f"{formatted_symbol}_{interval}"] = f"Error: {str(e)}"
            except Exception as e:
                logger.error(f"Error syncing data for {sym}: {e}")
                results[sym] = 0

        return results


# Global service instance
_market_data_service: Optional[MarketDataService] = None


def get_market_data_service() -> MarketDataService:
    """Get or create the market data service instance."""
    global _market_data_service
    if _market_data_service is None:
        _market_data_service = MarketDataService()
    return _market_data_service
