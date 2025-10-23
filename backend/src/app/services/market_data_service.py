"""
Market Data Service for fetching and managing real-time market data.

Integrates with Aster Connector for market data fetching and stores data in TimescaleDB.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import logging

from ..models.market_data import MarketData
from ..core.config import config
from ..core.logging import get_logger

logger = get_logger(__name__)


class MarketDataService:
    """Service for managing market data operations."""

    def __init__(self):
        """Initialize the Market Data Service."""
        self.api_key = config.ASTERDEX_API_KEY
        self.api_secret = config.ASTERDEX_API_SECRET
        self.base_url = config.ASTERDEX_BASE_URL
        self.assets = [asset.strip() for asset in config.ASSETS.split(",")]
        self.interval = config.INTERVAL
        
        # Initialize Aster client (lazy loaded)
        self._aster_client = None
        self._ws_client = None

    @property
    def aster_client(self):
        """Lazy load Aster REST API client."""
        if self._aster_client is None:
            try:
                from aster.rest_api import AsterDEXClient
                self._aster_client = AsterDEXClient(
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    base_url=self.base_url
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
                from aster.websocket import AsterDEXWebSocket
                self._ws_client = AsterDEXWebSocket(
                    api_key=self.api_key,
                    api_secret=self.api_secret
                )
                logger.info("Aster WebSocket client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize WebSocket client: {e}")
                raise
        return self._ws_client

    async def fetch_market_data(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 100
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
            data = await asyncio.to_thread(
                self.aster_client.get_klines,
                symbol=symbol,
                interval=interval,
                limit=limit
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
        data: List[Dict[str, Any]]
    ) -> int:
        """
        Store market data in TimescaleDB.

        Args:
            db: Database session
            symbol: Trading pair symbol
            interval: Candlestick interval
            data: List of market data dictionaries

        Returns:
            Number of records stored
        """
        try:
            count = 0
            for candle in data:
                # Parse candle data
                market_data = MarketData(
                    symbol=symbol,
                    interval=interval,
                    time=datetime.fromtimestamp(candle.get("time", 0) / 1000),
                    open=float(candle.get("open", 0)),
                    high=float(candle.get("high", 0)),
                    low=float(candle.get("low", 0)),
                    close=float(candle.get("close", 0)),
                    volume=float(candle.get("volume", 0)),
                    quote_asset_volume=float(candle.get("quote_asset_volume", 0)),
                    number_of_trades=float(candle.get("number_of_trades", 0)),
                    taker_buy_base_asset_volume=float(candle.get("taker_buy_base_asset_volume", 0)),
                    taker_buy_quote_asset_volume=float(candle.get("taker_buy_quote_asset_volume", 0)),
                )
                db.add(market_data)
                count += 1
            
            await db.commit()
            logger.info(f"Stored {count} market data records for {symbol}")
            return count
        except Exception as e:
            await db.rollback()
            logger.error(f"Error storing market data: {e}")
            raise

    async def get_latest_market_data(
        self,
        db: AsyncSession,
        symbol: str,
        interval: str = "1h",
        limit: int = 100
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
                .where(
                    and_(
                        MarketData.symbol == symbol,
                        MarketData.interval == interval
                    )
                )
                .order_by(MarketData.time.desc())
                .limit(limit)
            )
            data = result.scalars().all()
            return list(reversed(data))  # Return in ascending order
        except Exception as e:
            logger.error(f"Error retrieving market data: {e}")
            raise

    async def get_market_data_range(
        self,
        db: AsyncSession,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime
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
                        MarketData.time <= end_time
                    )
                )
                .order_by(MarketData.time.asc())
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error retrieving market data range: {e}")
            raise

    async def sync_market_data(
        self,
        db: AsyncSession,
        symbol: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Sync market data from Aster DEX to database.

        Args:
            db: Database session
            symbol: Optional specific symbol to sync

        Returns:
            Dictionary with sync results
        """
        symbols = [symbol] if symbol else self.assets
        results = {}

        for sym in symbols:
            try:
                # Fetch data from Aster
                data = await self.fetch_market_data(sym, self.interval, limit=100)
                
                # Store in database
                count = await self.store_market_data(db, sym, self.interval, data)
                results[sym] = count
                
                logger.info(f"Synced {count} records for {sym}")
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

