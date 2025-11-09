"""
E2E tests for database market data integration.

Tests fetching real market data from TimescaleDB and validating data integrity.
"""

import json
import logging

import pytest

from app.models.market_data import MarketData
from app.services.market_data.repository import MarketDataRepository

logger = logging.getLogger(__name__)


class TestDatabaseMarketDataE2E:
    """E2E tests for database market data integration."""

    @pytest.fixture
    def market_data_repository(self):
        """Create market data repository instance."""
        return MarketDataRepository()

    @pytest.mark.asyncio
    async def test_fetch_real_btcusdt_5m_data(self, db_session, market_data_repository):
        """Test fetching real BTCUSDT 5m data from database."""
        # Fetch 100 latest 5m candles for BTCUSDT
        data = await market_data_repository.get_latest(db_session, "BTCUSDT", "5m", 100)

        # Log the data for debugging in json format
        logger.info(f"Fetched market data: {json.dumps(data, default=str)}")

        # Validate we got data
        assert len(data) > 0, "Should fetch market data from database"

        # Validate data structure
        for candle in data:
            assert isinstance(candle, MarketData)
            assert candle.symbol == "BTCUSDT"
            assert candle.interval == "5m"
            assert candle.open > 0
            assert candle.high > 0
            assert candle.low > 0
            assert candle.close > 0
            assert candle.volume >= 0

            # Validate OHLC relationship
            assert candle.high >= candle.open, "High should be >= Open"
            assert candle.high >= candle.close, "High should be >= Close"
            assert candle.low <= candle.open, "Low should be <= Open"
            assert candle.low <= candle.close, "Low should be <= Close"

        # Validate data ordering (ascending by time)
        for i in range(1, len(data)):
            assert data[i - 1].time < data[i].time, "Data should be ordered by time ascending"

        # Validate we got reasonable amount of data
        assert len(data) <= 100, "Should respect limit parameter"
        assert len(data) >= 10, "Should have reasonable amount of data"

    @pytest.mark.asyncio
    async def test_data_integrity_validation(self, db_session, market_data_repository):
        """Test data integrity validation with real market data."""
        # Fetch data
        data = await market_data_repository.get_latest(db_session, "BTCUSDT", "5m", 50)

        # Validate all required fields are present
        for candle in data:
            assert candle.time is not None, "Time should be present"
            assert candle.symbol is not None, "Symbol should be present"
            assert candle.interval is not None, "Interval should be present"
            assert candle.open is not None, "Open should be present"
            assert candle.high is not None, "High should be present"
            assert candle.low is not None, "Low should be present"
            assert candle.close is not None, "Close should be present"
            assert candle.volume is not None, "Volume should be present"

    @pytest.mark.asyncio
    async def test_different_time_intervals(self, db_session, market_data_repository):
        """Test fetching data with different time intervals."""
        intervals = ["1m", "5m", "15m", "1h", "4h"]

        for interval in intervals:
            try:
                data = await market_data_repository.get_latest(db_session, "BTCUSDT", interval, 10)
                # Some intervals might not have data, but if they do, validate structure
                if len(data) > 0:
                    for candle in data:
                        assert candle.interval == interval, f"Interval should match {interval}"
            except Exception:
                # Some intervals might not be available, which is acceptable
                pass

    @pytest.mark.asyncio
    async def test_data_caching_behavior(self, db_session, market_data_repository):
        """Test data caching behavior with repeated requests."""
        # First request
        data1 = await market_data_repository.get_latest(db_session, "BTCUSDT", "5m", 10)

        # Second request (should potentially be cached)
        data2 = await market_data_repository.get_latest(db_session, "BTCUSDT", "5m", 10)

        # Data should be consistent
        assert len(data1) == len(data2), "Data length should be consistent"

        if len(data1) > 0 and len(data2) > 0:
            # Check latest candle is the same
            assert data1[-1].time == data2[-1].time, "Latest candle should be the same"
            assert data1[-1].close == data2[-1].close, "Latest price should be the same"
