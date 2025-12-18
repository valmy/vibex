from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.market_data import (
    CandleCloseEvent,
    EventType,
    MarketDataService,
)
from app.services.market_data.scheduler import CandleScheduler


@pytest.mark.asyncio
class TestCandleSchedulerIntegration:
    """Integration tests for the Candle Scheduler component."""

    async def test_scheduler_lifecycle(self):
        """Test that the scheduler starts and stops correctly."""
        # Mock dependencies to avoid actual scheduling interactions during lifecycle test
        mock_event_manager = MagicMock()
        mock_fetch_callback = AsyncMock()

        scheduler = CandleScheduler(
            intervals=["1h"],
            event_manager=mock_event_manager,
            fetch_callback=mock_fetch_callback,
        )

        # Test Start
        await scheduler.start()
        assert scheduler._is_running is True
        assert len(scheduler._scheduled_tasks) == 1
        assert "1h" in scheduler._scheduled_tasks

        # Test Stop
        await scheduler.stop()
        assert scheduler._is_running is False
        assert len(scheduler._scheduled_tasks) == 0

    @patch("app.db.session.AsyncSessionLocal")
    async def test_scheduler_callback_execution(self, mock_session_local):
        """
        Test the end-to-end flow of the scheduler callback:
        1. Fetch data (mocked)
        2. Store data (mocked DB)
        3. Trigger event
        """
        # Setup Mock DB Session
        mock_db_session = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_db_session

        # Initialize Service
        service = MarketDataService()

        # Mock API Client
        service.client = AsyncMock()

        # Mock the specific fetch_market_data response
        # Using a timestamp that will pass validation (very recent)
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        # Create a candle that closed just now
        mock_candle = [
            now_ms - 3600000,  # Open time
            "50000.0",
            "51000.0",
            "49000.0",
            "50500.0",  # OHLC
            "100.0",  # Volume
            now_ms,  # Close time (current time)
            "5000000.0",  # Quote vol
            1000,  # Trades
            "50.0",
            "2500000.0",  # Taker buy base/quote
            "0",
        ]

        # Return 2 candles as required by the validation logic (needs prev + current)
        # But for the test we only care about the latest one
        prev_candle = list(mock_candle)
        prev_candle[0] -= 3600000
        prev_candle[6] -= 3600000

        service.client.fetch_klines.return_value = [prev_candle, mock_candle]

        # Mock Funding Rate (optional but good to handle)
        service.client.fetch_funding_rate.return_value = []

        # Mock Repository
        service.repository = AsyncMock()
        service.repository.store_candles.return_value = 1

        # Mock Event Handler to verify event triggering
        mock_handler = AsyncMock()
        service.register_event_handler(EventType.CANDLE_CLOSE, mock_handler)

        # Mock "config" assets if needed, or assume default
        service.assets = ["BTCUSDT"]

        # --- Execute the callback directly ---
        # We don't need to wait for the actual scheduler time, we just test the logic that runs
        result = await service._fetch_and_store_latest_candle("1h")

        # --- Assertions ---
        assert result is True

        # Verify API called
        service.client.fetch_klines.assert_called_with("BTCUSDT", "1h", 2)

        # Verify DB interactions
        service.repository.store_candles.assert_called()
        mock_db_session.commit.assert_called_once()

        # Verify Event Triggered
        # The service triggers the event via event_manager
        # We registered a handler, so it should be called
        assert mock_handler.called

        # Check event data
        call_args = mock_handler.call_args
        event = call_args[0][0]
        assert isinstance(event, CandleCloseEvent)
        assert event.symbol == "BTCUSDT"
        assert event.interval == "1h"
        assert event.candle["close"] == "50500.0"

    @patch("app.services.market_data.service.MarketDataService.fetch_market_data")
    async def test_process_candle_close_integration(self, mock_fetch):
        """
        Verify that the CandleScheduler correctly calls the service callback.
        """
        # We mock the callback mechanism
        on_fetch = AsyncMock()

        scheduler = CandleScheduler(
            intervals=["1h"], event_manager=MagicMock(), fetch_callback=on_fetch
        )

        # Manually trigger the process method
        await scheduler._process_candle_close("1h")

        # Assert callback was called
        on_fetch.assert_called_once_with("1h")
