"""Main market data service orchestrating all components."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import config
from ...models.market_data import MarketData
from .client import AsterClient
from .events import CandleCloseEvent, EventManager, EventType
from .repository import MarketDataRepository
from .scheduler import CandleScheduler
from .utils import (
    calculate_previous_candle_close,
    format_symbol,
    validate_interval,
)

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

    def __init__(self) -> None:
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
            EventType.CANDLE_CLOSE,
            self._default_candle_close_handler,  # type: ignore[arg-type]
        )

    # Scheduler delegation methods
    async def start_scheduler(self) -> None:
        """Start the candle close scheduler."""
        await self.scheduler.start()

    async def stop_scheduler(self) -> None:
        """Stop the scheduler."""
        await self.scheduler.stop()

    async def get_scheduler_status(self) -> Dict[str, Any]:
        """Get scheduler status."""
        return await self.scheduler.get_status()

    # Event system delegation
    def register_event_handler(
        self, event_type: EventType, handler: Any, interval: Optional[str] = None
    ) -> None:
        """Register an event handler."""
        self.event_manager.register_handler(event_type, handler, interval)

    async def _default_candle_close_handler(self, event: CandleCloseEvent) -> None:
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

                        # Log entry point to the function for debugging
                        logger.info(
                            f"Funding rate debug: Starting fetch for {symbol} at {datetime.now(timezone.utc)}"
                        )

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
                        candle_time_ms = latest_candle[6]  # Close time in milliseconds
                        candle_time = datetime.fromtimestamp(candle_time_ms / 1000, timezone.utc)

                        # Validate we got the latest candle (must be closed)
                        # Use integer millisecond comparison to avoid floating-point precision issues
                        expected_close = calculate_previous_candle_close(
                            interval, datetime.now(timezone.utc)
                        )
                        expected_close_ms = int(expected_close.timestamp() * 1000)

                        # Only reject if candle is more than 1 second behind expected close
                        if expected_close_ms - candle_time_ms > 1000:
                            raise ValueError(
                                f"Received stale candle data for {symbol}. Expected close at {expected_close}, got {candle_time}"
                            )

                        # Log that we're about to fetch funding rates
                        logger.info(f"About to fetch funding rates for {symbol}")

                        # Fetch funding rate data for correlation
                        # Get funding rates for a time range up to the candle close time
                        # Funding rates are typically published every 8 hours, so look back much further than the candle interval
                        # to find the most recent funding rate that was active during the candle period
                        candle_timestamp = latest_candle[6]  # close_time (index 6), not open time
                        # Look back up to 12 hours to find the most recent funding rate
                        # (funding rates are typically every 8 hours but we'll use 12h to be safe)
                        funding_rate_window_ms = 12 * 60 * 60 * 1000  # 12 hours in milliseconds
                        start_time = candle_timestamp - funding_rate_window_ms
                        end_time = candle_timestamp  # Don't fetch future rates

                        try:
                            # Log the API call details at INFO level
                            logger.info(
                                f"Fetching funding rates for {symbol} in time range: {datetime.fromtimestamp(start_time / 1000)} to {datetime.fromtimestamp(end_time / 1000)}"
                            )

                            funding_rates = await self.fetch_funding_rate(
                                symbol=symbol, startTime=start_time, endTime=end_time, limit=100
                            )

                            # Log the API response at INFO level
                            logger.info(
                                f"Fetched {len(funding_rates)} funding rate(s) for {symbol}"
                            )

                            # Correlate funding rates with candle data
                            correlated_candles = self.correlate_funding_rates_with_candles(
                                [latest_candle], funding_rates, symbol
                            )
                            candle_with_funding = correlated_candles[0]

                            # Log the result at INFO level
                            funding_rate_value = candle_with_funding[
                                -1
                            ]  # funding rate is the last element
                            logger.info(
                                f"Funding rate for {symbol} at {datetime.fromtimestamp(latest_candle[6] / 1000)}: {funding_rate_value}"
                            )

                        except Exception as e:
                            logger.warning(f"Failed to fetch funding rates for {symbol}: {e}")
                            # Continue with candle data without funding rate
                            candle_with_funding = latest_candle + [None]

                        # Store the candle data with funding rate
                        await self.store_market_data(
                            db=db,
                            symbol=symbol,
                            interval=interval,
                            data=[candle_with_funding],
                        )

                        # Commit the transaction
                        await db.commit()

                        # Convert candle list to dictionary format expected by CandleCloseEvent
                        candle_dict = {
                            "open_time": latest_candle[0],
                            "open": latest_candle[1],
                            "high": latest_candle[2],
                            "low": latest_candle[3],
                            "close": latest_candle[4],
                            "volume": latest_candle[5],
                            "close_time": latest_candle[6],
                            "quote_asset_volume": latest_candle[7]
                            if len(latest_candle) > 7
                            else None,
                            "number_of_trades": latest_candle[8]
                            if len(latest_candle) > 8
                            else None,
                            "taker_buy_base_asset_volume": latest_candle[9]
                            if len(latest_candle) > 9
                            else None,
                            "taker_buy_quote_asset_volume": latest_candle[10]
                            if len(latest_candle) > 10
                            else None,
                        }

                        # Trigger event handlers
                        event = CandleCloseEvent(
                            symbol=symbol,
                            interval=interval,
                            candle=candle_dict,
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
    ) -> List[List[Any]]:
        """
        Fetch market data from Aster DEX.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            interval: Candle interval (e.g., "1m", "1h", "4h")
            limit: Number of candles to fetch

        Returns:
            List of candle data dictionaries
        """
        return await self.client.fetch_klines(symbol, interval, limit)  # type: ignore[return-value]

    async def fetch_funding_rate(
        self,
        symbol: Optional[str] = None,
        startTime: Optional[int] = None,
        endTime: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch funding rate data from Aster DEX.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT"). If None, fetches for all symbols.
            startTime: Start time in milliseconds
            endTime: End time in milliseconds
            limit: Number of funding rate records to fetch

        Returns:
            List of funding rate data dictionaries
        """
        return await self.client.fetch_funding_rate(symbol, startTime, endTime, limit)

    def correlate_funding_rates_with_candles(
        self, candles: List[List[Any]], funding_rates: List[Dict[str, Any]], symbol: str
    ) -> List[List[Any]]:
        """
        Correlate funding rates with candle data based on timestamps.

        For each candle, finds the funding rate with timestamp closest to the candle's close time.

        Args:
            candles: List of candle data (API format)
            funding_rates: List of funding rate data
            symbol: Symbol to filter funding rates (if needed)

        Returns:
            List of candle data with funding rates appended
        """
        if not funding_rates:
            # If no funding rates available, append None to all candles
            return [candle + [None] for candle in candles]

        # Convert funding rates to list of (timestamp, rate) tuples for efficient lookup
        funding_data = [
            (rate["fundingTime"], float(rate["fundingRate"]))
            for rate in funding_rates
            if rate.get("symbol") == symbol or symbol is None
        ]

        if not funding_data:
            # No funding rates for this symbol
            return [candle + [None] for candle in candles]

        correlated_candles = []
        for candle in candles:
            candle_close_time = candle[6]  # close_time is at index 6

            # Find funding rate with closest timestamp
            closest_rate = min(funding_data, key=lambda x: abs(x[0] - candle_close_time))[1]

            # Append funding rate to candle data
            correlated_candles.append(candle + [closest_rate])

        return correlated_candles

    async def store_market_data(
        self, db: AsyncSession, symbol: str, interval: str, data: List[List[Any]]
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

    async def list_market_data(
        self, db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> Tuple[List[MarketData], int]:
        """
        List all market data with pagination.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Number of records to fetch

        Returns:
            Tuple containing list of MarketData records and total count
        """
        return await self.repository.list_with_count(db, skip, limit)

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
        return await self.repository.get_latest(db, symbol, interval, limit)

    async def get_latest_market_data_with_total(
        self, db: AsyncSession, symbol: str, interval: str = "1h", limit: int = 100
    ) -> Tuple[List[MarketData], int]:
        """
        Get latest market data and total count from database.

        Args:
            db: Database session
            symbol: Trading pair symbol
            interval: Candlestick interval
            limit: Number of records to fetch

        Returns:
            Tuple containing list of MarketData records and total count
        """
        return await self.repository.get_latest_with_count(db, symbol, interval, limit)

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
        return await self.repository.get_range(db, symbol, interval, start_time, end_time)

    async def sync_market_data(
        self, db: AsyncSession, symbol: Optional[str] = None, interval: Optional[str] = None
    ) -> Dict[str, Any]:  # Can be int (count) or str (error message)
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
        results: Dict[str, Any] = {}  # Can store both counts (int) and error messages (str)

        for sym in symbols:
            try:
                # Ensure symbol is in proper format (add USDT as quote currency if needed)
                formatted_symbol = format_symbol(sym)

                # Fetch and store market data for each interval
                for intv in intervals:
                    try:
                        data = await self.fetch_market_data(formatted_symbol, intv)

                        # Get funding rates that may be relevant for this data range
                        # For sync operations, we'll correlate funding rates with the market data
                        if data and len(data) > 0:
                            # Determine the time range for the fetched market data
                            min_time = min(candle[0] for candle in data)  # open_time
                            max_time = max(candle[6] for candle in data)  # close_time

                            # Fetch funding rates for the time period, looking back by funding rate window (12 hours)
                            # since funding rates are typically published every 8 hours, not per candle
                            funding_rate_window_ms = 12 * 60 * 60 * 1000  # 12 hours in milliseconds
                            start_time = min_time - funding_rate_window_ms
                            end_time = max_time

                            try:
                                # Log the API call details at INFO level
                                logger.info(
                                    f"Sync: Fetching funding rates for {formatted_symbol} in time range: {datetime.fromtimestamp(start_time / 1000)} to {datetime.fromtimestamp(end_time / 1000)}"
                                )

                                funding_rates = await self.fetch_funding_rate(
                                    symbol=formatted_symbol,
                                    startTime=start_time,
                                    endTime=end_time,
                                    limit=1000,  # Higher limit for sync operations
                                )

                                # Log the API response at INFO level
                                logger.info(
                                    f"Sync: Fetched {len(funding_rates)} funding rate(s) for {formatted_symbol}"
                                )

                                # Correlate funding rates with the candle data
                                data = self.correlate_funding_rates_with_candles(
                                    data, funding_rates, formatted_symbol
                                )
                            except Exception as e:
                                logger.warning(
                                    f"Failed to fetch funding rates during sync for {formatted_symbol}: {e}"
                                )
                                # Continue with original data without funding rates
                                data = [candle + [None] for candle in data]

                        count = await self.store_market_data(db, formatted_symbol, intv, data)
                        await db.commit()
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
