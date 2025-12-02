import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from src.app.api.routes.market_data import get_market_data_by_symbol, get_market_data_range
from src.app.models.market_data import MarketData

@pytest.mark.asyncio
async def test_get_market_data_by_symbol_correct_total_count():
    """Test that total count is independent of pagination limit."""
    mock_db = AsyncMock()

    # Mock return values
    # We expect two calls to execute:
    # 1. Count query -> returns scalar 200
    # 2. Data query -> returns list of 10 items

    # Mock for count query result
    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 200

    # Mock for data query result
    mock_data_result = MagicMock()
    mock_data = []
    for _ in range(10):
        m = MagicMock(spec=MarketData)
        # Set attributes required by MarketDataRead schema
        m.symbol = "BTCUSDT"
        m.timeframe = "1h"
        m.open_price = 100.0
        m.high_price = 110.0
        m.low_price = 90.0
        m.close_price = 105.0
        m.volume = 1000.0
        m.time = datetime.now(timezone.utc)
        m.funding_rate = None
        mock_data.append(m)

    mock_data_result.scalars.return_value.all.return_value = mock_data

    # side_effect to return count_result then data_result
    mock_db.execute.side_effect = [mock_count_result, mock_data_result]

    response = await get_market_data_by_symbol(
        symbol="BTCUSDT",
        interval="1h",
        limit=10,
        db=mock_db
    )

    assert len(response.items) == 10
    assert response.total == 200
    assert mock_db.execute.call_count == 2

@pytest.mark.asyncio
async def test_get_market_data_range_total_count():
    """Test that get_market_data_range returns correct total count (equal to len(data))."""
    mock_db = AsyncMock()

    # Mock service
    mock_service = MagicMock()

    # Create mock data items
    mock_data = []
    for _ in range(5):
        m = MagicMock(spec=MarketData)
        m.symbol = "BTCUSDT"
        m.timeframe = "1h"
        m.open_price = 100.0
        m.high_price = 110.0
        m.low_price = 90.0
        m.close_price = 105.0
        m.volume = 1000.0
        m.time = datetime.now(timezone.utc)
        m.funding_rate = None
        mock_data.append(m)

    mock_service.get_market_data_range = AsyncMock(return_value=mock_data)

    # Patch the get_market_data_service function where it is used
    with patch("src.app.api.routes.market_data.get_market_data_service", return_value=mock_service):
        response = await get_market_data_range(
            symbol="BTCUSDT",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            interval="1h",
            db=mock_db
        )

        assert len(response.items) == 5
        assert response.total == 5
