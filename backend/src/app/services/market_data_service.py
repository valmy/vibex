"""
Market Data Service for fetching and managing real-time market data.

Integrates with Aster Connector for market data fetching and stores data in TimescaleDB.
"""

from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Awaitable
import asyncio
import logging

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..core.config import config
from ..models.market_data import MarketData

logger = logging.getLogger(__name__)

class MarketDataService:
    """Service for managing market data operations."""

    class WSEventType(Enum):
        KLINE = "kline"
        TRADE = "trade"
        TICKER = "ticker"
        DEPTH = "depth"
        ALL_TICKERS = "all_tickers"

    @dataclass
    class WSSubscription:
        symbol: str
        interval: str
        callback: Callable[[Dict], Awaitable[None]]

    def __init__(self):
        """Initialize the Market Data Service."""
        self.api_key = config.ASTERDEX_API_KEY
        self.api_secret = config.ASTERDEX_API_SECRET
        self.base_url = config.ASTERDEX_BASE_URL
        self.assets = [asset.strip() for asset in config.ASSETS.split(",")]
        self.interval = config.INTERVAL
        self.long_interval = config.LONG_INTERVAL

        # WebSocket state
        self._ws_connected = False
        self._ws_task = None
        self._subscriptions = []
        self._ws_lock = asyncio.Lock()
        self._shutdown_event = asyncio.Event()
        self._event_loop = None  # Store reference to the main event loop

        # Initialize Aster client (lazy loaded)
        self._aster_client = None
        self._ws_client = None

    @property
    def aster_client(self):
        """Lazy load Aster REST API client."""
        if self._aster_client is None:
            try:
                from aster.rest_api import Client

                self._aster_client = Client(
                    key=self.api_key, secret=self.api_secret, base_url=self.base_url
                )
                logger.info("Aster REST API client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Aster client: {e}")
                raise
        return self._aster_client

    @property
    def ws_client(self):
        """Lazy load Aster WebSocket client."""
        if self._ws_client is None:
            try:
                from aster.websocket.client.stream import WebsocketClient

                self._ws_client = WebsocketClient()
                logger.info("Aster WebSocket client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize WebSocket client: {e}")
                raise
        return self._ws_client


    async def connect_websocket(self) -> None:
        """Initialize WebSocket connection."""
        if self._ws_connected:
            return

        try:
            # Store reference to the current event loop
            self._event_loop = asyncio.get_running_loop()
            
            # Start the WebSocket client
            self.ws_client.start()
            self._ws_connected = True
            logger.info("WebSocket connected successfully")

        except Exception as e:
            logger.error(f"Failed to connect WebSocket: {e}")
            self._ws_connected = False
            raise


    async def subscribe_market_data(
        self,
        symbol: str,
        interval: str,
        callback: Callable[[Dict], Awaitable[None]]
    ) -> None:
        """Subscribe to market data updates.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            interval: Time interval (e.g., '1h', '4h')
            callback: Async function to handle updates
        """
        # Ensure WebSocket is connected
        if not self._ws_connected:
            await self.connect_websocket()

        # Format symbol if needed
        formatted_symbol = f"{symbol}USDT" if not symbol.upper().endswith("USDT") else symbol.upper()

        # Create and store subscription
        subscription = self.WSSubscription(
            symbol=formatted_symbol,
            interval=interval,
            callback=callback
        )

        async with self._ws_lock:
            self._subscriptions.append(subscription)

        # Subscribe to the WebSocket stream
        await self._subscribe_kline(formatted_symbol, interval)

    async def _subscribe_kline(self, symbol: str, interval: str) -> None:
        """Subscribe to kline/candlestick WebSocket stream."""
        if not self._ws_connected:
            return

        try:
            # Use the kline method from Aster WebSocket client
            # Generate a unique ID for this subscription
            subscription_id = len(self._subscriptions) + 1
            self.ws_client.kline(
                symbol=symbol.lower(),
                id=subscription_id,
                interval=interval,
                callback=self._handle_market_data_update
            )
            logger.info(f"Subscribed to {symbol}@kline_{interval} (id={subscription_id})")
        except Exception as e:
            logger.error(f"Failed to subscribe to {symbol}@{interval}: {e}")
            raise

    async def initialize_websocket(self) -> None:
        """Initialize WebSocket connection and subscribe to market data for all assets."""
        if self._ws_connected or self._shutdown_event.is_set():
            return

        try:
            # Connect to WebSocket
            await self.connect_websocket()

            # Subscribe to all assets and intervals
            for symbol in self.assets:
                # Subscribe to both short and long intervals
                for interval in [self.interval, self.long_interval]:
                    try:
                        await self.subscribe_market_data(
                            symbol=symbol,
                            interval=interval,
                            callback=self._handle_market_data_update
                        )
                    except Exception as e:
                        logger.error(f"Failed to subscribe to {symbol}@{interval}: {e}")
                        continue

            logger.info("WebSocket market data subscriptions initialized")

        except Exception as e:
            logger.error(f"Failed to initialize WebSocket: {e}")
            self._ws_connected = False
            raise

    def _handle_market_data_update(self, kline_data: Dict) -> None:
        """Handle incoming market data update from WebSocket (synchronous callback)."""
        try:
            # Skip subscription confirmation messages
            if 'result' in kline_data:
                return

            # Log the raw data for debugging
            logger.debug(f"Received WebSocket data: {kline_data}")

            # Extract data from kline update
            # The data structure might be nested under 'k' key or directly available
            if 'k' in kline_data:
                kline = kline_data['k']
                symbol = kline.get('s', 'UNKNOWN')
                interval = kline.get('i', 'UNKNOWN')
                open_price = float(kline.get('o', 0))
                close_price = float(kline.get('c', 0))
                high_price = float(kline.get('h', 0))
                low_price = float(kline.get('l', 0))
                volume = float(kline.get('v', 0))
                open_time = int(kline.get('t', 0))
                quote_volume = float(kline.get('q', 0))
                num_trades = float(kline.get('n', 0))
                taker_buy_base = float(kline.get('V', 0))
                taker_buy_quote = float(kline.get('Q', 0))
            else:
                # Fallback for direct structure
                symbol = kline_data.get('s', 'UNKNOWN')
                interval = kline_data.get('i', 'UNKNOWN')
                open_price = float(kline_data.get('o', 0))
                close_price = float(kline_data.get('c', 0))
                high_price = float(kline_data.get('h', 0))
                low_price = float(kline_data.get('l', 0))
                volume = float(kline_data.get('v', 0))
                open_time = int(kline_data.get('t', 0))
                quote_volume = float(kline_data.get('q', 0))
                num_trades = float(kline_data.get('n', 0))
                taker_buy_base = float(kline_data.get('V', 0))
                taker_buy_quote = float(kline_data.get('Q', 0))

            # Skip if essential data is missing
            if symbol == 'UNKNOWN' or open_time == 0:
                return

            # Log the update
            logger.info(f"Market data update - {symbol} {interval}: {open_price} -> {close_price}")

            # Store to database asynchronously using the stored event loop
            if self._event_loop and not self._event_loop.is_closed():
                asyncio.run_coroutine_threadsafe(
                    self._store_websocket_data(
                        symbol=symbol,
                        interval=interval,
                        open_time=open_time,
                        open_price=open_price,
                        high_price=high_price,
                        low_price=low_price,
                        close_price=close_price,
                        volume=volume,
                        quote_volume=quote_volume,
                        num_trades=num_trades,
                        taker_buy_base=taker_buy_base,
                        taker_buy_quote=taker_buy_quote
                    ),
                    self._event_loop
                )
            else:
                logger.warning("Cannot store market data: event loop not available")

        except Exception as e:
            logger.error(f"Error processing market data update: {e}")

    async def _store_websocket_data(
        self,
        symbol: str,
        interval: str,
        open_time: int,
        open_price: float,
        high_price: float,
        low_price: float,
        close_price: float,
        volume: float,
        quote_volume: float,
        num_trades: float,
        taker_buy_base: float,
        taker_buy_quote: float
    ) -> None:
        """Store WebSocket market data to database with duplicate prevention."""
        try:
            from ..db.session import AsyncSessionLocal

            # Get database session
            async with AsyncSessionLocal() as db:
                # Convert timestamp to datetime
                candle_time = datetime.fromtimestamp(open_time / 1000)

                # Check if record already exists
                existing = await db.execute(
                    select(MarketData).where(
                        and_(
                            MarketData.symbol == symbol,
                            MarketData.interval == interval,
                            MarketData.time == candle_time
                        )
                    )
                )
                existing_record = existing.scalar_one_or_none()

                if existing_record:
                    # Update existing record
                    existing_record.open = open_price
                    existing_record.high = high_price
                    existing_record.low = low_price
                    existing_record.close = close_price
                    existing_record.volume = volume
                    existing_record.quote_asset_volume = quote_volume
                    existing_record.number_of_trades = num_trades
                    existing_record.taker_buy_base_asset_volume = taker_buy_base
                    existing_record.taker_buy_quote_asset_volume = taker_buy_quote
                    logger.debug(f"Updated market data for {symbol} {interval} at {candle_time}")
                else:
                    # Create new record
                    market_data = MarketData(
                        symbol=symbol,
                        interval=interval,
                        time=candle_time,
                        open=open_price,
                        high=high_price,
                        low=low_price,
                        close=close_price,
                        volume=volume,
                        quote_asset_volume=quote_volume,
                        number_of_trades=num_trades,
                        taker_buy_base_asset_volume=taker_buy_base,
                        taker_buy_quote_asset_volume=taker_buy_quote
                    )
                    db.add(market_data)
                    logger.debug(f"Inserted new market data for {symbol} {interval} at {candle_time}")

                await db.commit()

        except Exception as e:
            logger.error(f"Error storing WebSocket market data: {e}")
            if 'db' in locals():
                await db.rollback()

    async def close_websocket(self) -> None:
        """Close WebSocket connection and clean up resources."""
        if not self._ws_connected:
            return

        try:
            # Signal shutdown to background tasks
            self._shutdown_event.set()

            # Close the WebSocket connection
            if self._ws_client:
                self._ws_client.stop()

            # Reset state
            self._ws_connected = False
            self._subscriptions.clear()
            self._shutdown_event.clear()

            logger.info("WebSocket connection closed")

        except Exception as e:
            logger.error(f"Error closing WebSocket: {e}")
            raise

    async def fetch_market_data(
        self, symbol: str, interval: str = "1h", limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetch market data from Aster DEX.

        Args:
            symbol: Trading pair symbol (e.g., BTC/USDT)
            interval: Candlestick interval (1m, 5m, 1h, 4h, 1d)
            limit: Number of candles to fetch

        Returns:
            List of market data dictionaries
        """
        try:
            logger.info(f"Fetching market data for {symbol} ({interval})")

            # Call Aster API to get market data
            # Use the klines method from the Client class
            data = await asyncio.to_thread(
                self.aster_client.klines, symbol=symbol, interval=interval, limit=limit
            )

            logger.info(f"Successfully fetched {len(data)} candles for {symbol}")
            return data
        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
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
                    select(MarketData)
                    .where(
                        MarketData.symbol == symbol,
                        MarketData.interval == interval,
                        MarketData.time == candle_time
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
                    existing.taker_buy_base_asset_volume = float(candle[9]) if len(candle) > 9 else 0.0
                    existing.taker_buy_quote_asset_volume = float(candle[10]) if len(candle) > 10 else 0.0
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
