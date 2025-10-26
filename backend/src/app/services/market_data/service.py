"""Main market data service orchestrating all components."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import config
from .client import AsterClient
from .events import CandleCloseEvent, EventManager, EventType
from .repository import MarketDataRepository
from .scheduler import CandleScheduler
from .utils import calculate_previous_candle_close, format_symbol, validate_interval

logger = logging.getLogger(__name__)


class MarketDataService:
    """
    Service for managing market data operations.

    Orchestrates:
    - API client for fetching data
    - Repository for database operations
    - Scheduler for candle-close events
    - Event system for notifications
    """

    # Default retry configuration
    DEFAULT_RETRY_ATTEMPTS = 5
    DEFAULT_RETRY_DELAY = 1.0  # seconds
    MAX_RETRY_DELAY = 300.0  # 5 minutes

    def __init__(self):
        """Initialize the Market Data Service."""
        # Configuration
        self.assets = [asset.strip() for asset in config.ASSETS.split(",") if asset.strip()]
        self.interval = config.INTERVAL
        self.long_interval = config.LONG_INTERVAL

        # Validate intervals
        if not validate_interval(self.interval):
            raise ValueError(f"Invalid interval: {self.interval}")
        if not validate_interval(self.long_interval):
            raise ValueError(f"Invalid long_interval: {self.long_interval}")

        # Components
        self.client = AsterClient(
            api_key=config.ASTERDEX_API_KEY,
            api_secret=config.ASTERDEX_API_SECRET,
            base_url=config.ASTERDEX_BASE_URL,
        )
        self.repository = MarketDataRepository()
        self.event_manager = EventManager()
        self.scheduler = CandleScheduler(
            intervals=[self.interval, self.long_interval],
            event_manager=self.event_manager,
            fetch_callback=self._fetch_and_store_latest_candle,
        )

        self._fetch_lock = asyncio.Lock()

        # Register default handler
        self.event_manager.register_handler(
            EventType.CANDLE_CLOSE, self._default_candle_close_handler
        )

    # Scheduler delegation methods
    async def start_scheduler(self):
        """Start the candle close scheduler."""
        await self.scheduler.start()

    async def stop_scheduler(self):
        """Stop the scheduler."""
        await self.scheduler.stop()

    async def get_scheduler_status(self) -> dict:
        """Get scheduler status."""
        return await self.scheduler.get_status()

    # Event system delegation
    def register_event_handler(
        self, event_type: EventType, handler, interval: str = None
    ):
        """Register an event handler."""
        self.event_manager.register_handler(event_type, handler, interval)

    async def _default_candle_close_handler(self, event: CandleCloseEvent):
        """Default handler for candle close events."""
        logger.info(f"Candle closed: {event.symbol} {event.interval} at {event.close_time}")

    # Core business logic
    async def _fetch_and_store_latest_candle(self, interval: str) -> bool:
        """
        Fetch and store the latest candle for all configured assets.

        Args:
            interval: Candle interval (e.g., '1h', '4h')

        Returns:
            bool: True if all assets were processed successfully, False otherwise
        """
        # Import here to get the initialized version
        from ...db.session import AsyncSessionLocal

        # Check if database is initialized
        if AsyncSessionLocal is None:
            raise RuntimeError("Database not initialized. AsyncSessionLocal is None.")

        # Process each configured asset
        all_successful = True
        for asset in self.assets:
            # Format symbol (e.g., "BTC" -> "BTCUSDT")
            symbol = format_symbol(asset)

            retry_count = 0
            last_error = None
            success = False

            while (
                retry_count < self.DEFAULT_RETRY_ATTEMPTS
                and not self.scheduler._shutdown_event.is_set()
            ):
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
                        expected_close = calculate_previous_candle_close(
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
                        await self.event_manager.trigger_event(
                            event, EventType.CANDLE_CLOSE, interval
                        )

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

    # Public API methods - delegate to components
    async def fetch_market_data(
        self, symbol: str, interval: str = "1h", limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetch market data from Aster DEX.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            interval: Candle interval (e.g., "1m", "1h", "4h")
            limit: Number of candles to fetch

        Returns:
            List of candle data dictionaries
        """
        return await self.client.fetch_klines(symbol, interval, limit)

    async def store_market_data(
        self, db: AsyncSession, symbol: str, interval: str, data: List[List]
    ) -> int:
        """
        Store market data in database.

        Args:
            db: Database session
            symbol: Trading pair symbol
            interval: Candlestick interval
            data: List of market data

        Returns:
            Number of records stored
        """
        return await self.repository.store_candles(db, symbol, interval, data)

    async def get_latest_market_data(
        self, db: AsyncSession, symbol: str, interval: str = "1h", limit: int = 100
    ) -> List:
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
        return await self.repository.get_latest(db, symbol, interval, limit)

    async def get_market_data_range(
        self, db: AsyncSession, symbol: str, interval: str, start_time, end_time
    ) -> List:
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
        return await self.repository.get_range(db, symbol, interval, start_time, end_time)

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
                formatted_symbol = format_symbol(sym)

                # Fetch and store market data for each interval
                for intv in intervals:
                    try:
                        data = await self.fetch_market_data(formatted_symbol, intv)
                        count = await self.store_market_data(db, formatted_symbol, intv, data)
                        results[f"{formatted_symbol}_{intv}"] = count
                        logger.info(f"Synced {count} records for {formatted_symbol} ({intv})")
                    except Exception as e:
                        logger.error(f"Error syncing {formatted_symbol} ({intv}): {e}")
                        results[f"{formatted_symbol}_{intv}"] = f"Error: {str(e)}"
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

