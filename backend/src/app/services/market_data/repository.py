"""Database repository for market data operations."""

import logging
from datetime import datetime
from typing import List

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.market_data import MarketData

logger = logging.getLogger(__name__)


class MarketDataRepository:
    """Repository for market data database operations."""

    async def store_candles(
        self,
        db: AsyncSession,
        symbol: str,
        interval: str,
        data: List[List],  # API returns list of lists
    ) -> int:
        """
        Store market data in TimescaleDB with upsert to handle duplicates.

        Note: This method does NOT commit the transaction. The caller is responsible
        for calling db.commit() after this method returns.

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
                #          number_of_trades, taker_buy_base_asset_volume, taker_buy_quote_asset_volume, ignore, funding_rate (optional)]
                # Note: funding_rate is appended as the last element when correlated with funding data
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
                    # Funding rate is appended as the last element (index 12) when correlated
                    existing.funding_rate = (
                        float(candle[-1])
                        if len(candle) > 11 and candle[-1] is not None
                        else None
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
                        # Funding rate is appended as the last element (index 12) when correlated
                        funding_rate=(
                            float(candle[-1])
                            if len(candle) > 11 and candle[-1] is not None
                            else None
                        ),
                    )
                    db.add(market_data)
                    logger.debug(f"Added new market data for {symbol} at {candle_time}")

                count += 1

            logger.info(f"Processed {count} market data records for {symbol}")
            return count
        except Exception as e:
            await db.rollback()
            logger.error(f"Error storing market data: {e}")
            raise

    async def get_latest(
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

    async def get_range(
        self,
        db: AsyncSession,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
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
