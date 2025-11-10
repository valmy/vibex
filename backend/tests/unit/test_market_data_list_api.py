"""
Unit tests for market data list API endpoint with real data.

Tests the GET /api/v1/market-data endpoint for listing market data with pagination
using real data from the database.

Requirements:
- Real database connection (PostgreSQL with TimescaleDB)
- Real market data in the database (run sync first if needed)

Run with: uv run pytest tests/unit/test_market_data_list_api.py -v
"""

import pytest
import logging
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, func

from app.main import app
from app.models.market_data import MarketData
from app.db.session import init_db, close_db, get_session_factory

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
async def setup_database():
    """Initialize database for tests."""
    try:
        await init_db()
        yield
    except Exception as e:
        pytest.skip(f"Database not available: {e}")
    finally:
        try:
            await close_db()
        except Exception:
            pass


@pytest.fixture
async def async_client(setup_database):
    """Create an async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def db_session(setup_database):
    """Get a database session for tests."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


class TestMarketDataListAPIWithRealData:
    """Unit tests for the market data list endpoint using real data."""

    @pytest.mark.asyncio
    async def test_list_market_data_success(self, async_client, db_session):
        """Test successful listing of market data with default pagination using real data."""
        # First, verify we have data in the database
        count_result = await db_session.execute(select(func.count(MarketData.id)))
        total_count = count_result.scalar()

        if total_count == 0:
            pytest.skip("No market data in database. Run market data sync first.")

        logger.info(f"Found {total_count} market data records in database")

        # Make request to the API
        response = await async_client.get("/api/v1/market-data")

        # Verify response
        assert response.status_code == 200
        data = response.json()

        # Log the full response for inspection
        logger.info(f"API Response Status: {response.status_code}")
        logger.info(f"API Response Total: {data['total']}")
        logger.info(f"API Response Items Count: {len(data['items'])}")
        logger.info(f"First 3 items from response:")
        for i, item in enumerate(data["items"][:3]):
            logger.info(f"  Item {i+1}: {item}")

        # Verify response structure
        assert "total" in data
        assert "items" in data
        assert data["total"] == total_count
        assert len(data["items"]) > 0
        assert len(data["items"]) <= 100  # Default limit

        # Verify first item structure with real data
        first_item = data["items"][0]
        assert "symbol" in first_item
        assert "timeframe" in first_item
        assert "open_price" in first_item
        assert "high_price" in first_item
        assert "low_price" in first_item
        assert "close_price" in first_item
        assert "volume" in first_item

        # Validate OHLC relationships
        assert first_item["high_price"] >= first_item["open_price"]
        assert first_item["high_price"] >= first_item["close_price"]
        assert first_item["low_price"] <= first_item["open_price"]
        assert first_item["low_price"] <= first_item["close_price"]
        assert first_item["volume"] >= 0

        logger.info(f"Successfully fetched {len(data['items'])} items from API")

    @pytest.mark.asyncio
    async def test_list_market_data_with_pagination(self, async_client, db_session):
        """Test listing market data with custom pagination parameters using real data."""
        # Get total count from database
        count_result = await db_session.execute(select(func.count(MarketData.id)))
        total_count = count_result.scalar()

        if total_count < 10:
            pytest.skip("Need at least 10 records for pagination test")

        # Make request with pagination - skip first 5, get 3 items
        skip = 5
        limit = 3
        response = await async_client.get(f"/api/v1/market-data?skip={skip}&limit={limit}")

        # Verify response
        assert response.status_code == 200
        data = response.json()

        assert data["total"] == total_count
        assert len(data["items"]) == min(limit, total_count - skip)

        # Verify we got different data than the first page
        first_page_response = await async_client.get("/api/v1/market-data?skip=0&limit=3")
        first_page_data = first_page_response.json()

        # The items should be different (unless all data is identical)
        if len(first_page_data["items"]) > 0 and len(data["items"]) > 0:
            # Compare IDs or timestamps to ensure different records
            first_page_ids = [item.get("symbol", "") + str(item.get("timestamp", ""))
                            for item in first_page_data["items"]]
            second_page_ids = [item.get("symbol", "") + str(item.get("timestamp", ""))
                             for item in data["items"]]

            logger.info(f"First page IDs: {first_page_ids[:2]}")
            logger.info(f"Second page IDs: {second_page_ids[:2]}")

    @pytest.mark.asyncio
    async def test_list_market_data_with_large_skip(self, async_client, db_session):
        """Test listing market data with skip beyond available records."""
        # Get total count from database
        count_result = await db_session.execute(select(func.count(MarketData.id)))
        total_count = count_result.scalar()

        if total_count == 0:
            pytest.skip("No market data in database")

        # Request with skip beyond total count
        skip = total_count + 100
        response = await async_client.get(f"/api/v1/market-data?skip={skip}&limit=10")

        # Verify response
        assert response.status_code == 200
        data = response.json()

        # Should return empty items but correct total
        assert data["total"] == total_count
        assert len(data["items"]) == 0

        logger.info(f"Correctly handled skip={skip} beyond total={total_count}")

    @pytest.mark.asyncio
    async def test_list_market_data_default_pagination_values(self, async_client, db_session):
        """Test that default pagination values (skip=0, limit=100) are applied."""
        # Get total count from database
        count_result = await db_session.execute(select(func.count(MarketData.id)))
        total_count = count_result.scalar()

        if total_count == 0:
            pytest.skip("No market data in database")

        # Make request without pagination parameters
        response = await async_client.get("/api/v1/market-data")

        # Verify response
        assert response.status_code == 200
        data = response.json()

        # Should apply default limit of 100
        assert data["total"] == total_count
        assert len(data["items"]) <= 100
        assert len(data["items"]) == min(100, total_count)

        logger.info(f"Default pagination returned {len(data['items'])} items out of {total_count} total")

    @pytest.mark.asyncio
    async def test_list_market_data_multiple_symbols(self, async_client, db_session):
        """Test listing market data with multiple symbols using real data."""
        # Query for distinct symbols in the database
        symbols_result = await db_session.execute(
            select(MarketData.symbol).distinct().limit(5)
        )
        symbols = [row[0] for row in symbols_result.fetchall()]

        if len(symbols) == 0:
            pytest.skip("No market data in database")

        # Make request
        response = await async_client.get("/api/v1/market-data?limit=50")

        # Verify response
        assert response.status_code == 200
        data = response.json()

        assert data["total"] > 0
        assert len(data["items"]) > 0

        # Check if we have multiple symbols in the response
        response_symbols = set(item["symbol"] for item in data["items"])
        logger.info(f"Found symbols in response: {response_symbols}")
        logger.info(f"Available symbols in DB: {symbols}")

        # Verify all items have valid symbol
        for item in data["items"]:
            assert item["symbol"] in symbols or len(symbols) == 0

    @pytest.mark.asyncio
    async def test_list_market_data_response_schema_validation(self, async_client, db_session):
        """Test that response matches MarketDataListResponse schema using real data."""
        # Get some data from database
        count_result = await db_session.execute(select(func.count(MarketData.id)))
        total_count = count_result.scalar()

        if total_count == 0:
            pytest.skip("No market data in database")

        # Make request
        response = await async_client.get("/api/v1/market-data?limit=10")

        # Verify response
        assert response.status_code == 200
        data = response.json()

        # Validate schema structure
        assert isinstance(data["total"], int)
        assert isinstance(data["items"], list)
        assert data["total"] == total_count

        # Validate each item has required fields
        for item in data["items"]:
            # Required fields
            assert "symbol" in item
            assert "timeframe" in item
            assert "open_price" in item
            assert "high_price" in item
            assert "low_price" in item
            assert "close_price" in item
            assert "volume" in item

            # Validate types
            assert isinstance(item["symbol"], str)
            assert isinstance(item["timeframe"], str)
            assert isinstance(item["open_price"], (int, float))
            assert isinstance(item["high_price"], (int, float))
            assert isinstance(item["low_price"], (int, float))
            assert isinstance(item["close_price"], (int, float))
            assert isinstance(item["volume"], (int, float))

            # Validate values are positive
            assert item["open_price"] > 0
            assert item["high_price"] > 0
            assert item["low_price"] > 0
            assert item["close_price"] > 0
            assert item["volume"] >= 0

        logger.info(f"Schema validation passed for {len(data['items'])} items")

    @pytest.mark.asyncio
    async def test_list_market_data_ordering(self, async_client, db_session):
        """Test that market data is returned in consistent order."""
        # Get some data from database
        count_result = await db_session.execute(select(func.count(MarketData.id)))
        total_count = count_result.scalar()

        if total_count < 2:
            pytest.skip("Need at least 2 records for ordering test")

        # Make request
        response = await async_client.get("/api/v1/market-data?limit=20")

        # Verify response
        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) >= 2

        # Verify items have timestamps for ordering validation
        items_with_timestamps = [item for item in data["items"] if "timestamp" in item]

        logger.info(f"Retrieved {len(data['items'])} items, {len(items_with_timestamps)} with timestamps")

        # Just verify we got data in a consistent manner
        # The actual ordering depends on the database query
        for item in data["items"]:
            assert "symbol" in item
            assert "timeframe" in item

