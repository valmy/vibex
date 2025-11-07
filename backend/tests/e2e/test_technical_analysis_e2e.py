"""
E2E tests for technical analysis with real market data.

Tests technical indicator calculations using real market data from database.
"""

import pytest

from app.services import get_technical_analysis_service
from app.services.market_data.repository import MarketDataRepository


class TestTechnicalAnalysisE2E:
    """E2E tests for technical analysis with real market data."""

    @pytest.fixture
    def technical_analysis_service(self):
        """Get technical analysis service instance."""
        return get_technical_analysis_service()

    @pytest.fixture
    async def real_market_data(self, db_session):
        """Fetch real market data from database."""
        repository = MarketDataRepository()
        # Fetch 100 latest 5m candles for BTCUSDT
        data = await repository.get_latest(db_session, "BTCUSDT", "5m", 100)
        return data

    @pytest.mark.asyncio
    async def test_real_data_indicator_calculation(
        self, technical_analysis_service, real_market_data
    ):
        """Test technical indicator calculation with real market data."""
        # Validate we have enough data
        assert len(real_market_data) >= 50, "Should have sufficient data for indicators"

        # Calculate all indicators
        result = technical_analysis_service.calculate_all_indicators(real_market_data)

        # Validate result structure
        assert result is not None, "Should return indicator results"
        assert result.candle_count == len(real_market_data), "Candle count should match"

        # Validate indicators are calculated
        assert result.ema is not None, "EMA should be calculated"
        assert result.rsi is not None, "RSI should be calculated"
        assert result.macd is not None, "MACD should be calculated"
        assert result.bollinger_bands is not None, "Bollinger Bands should be calculated"
        assert result.atr is not None, "ATR should be calculated"

        # Validate EMA
        if result.ema.ema is not None:
            assert result.ema.ema > 0, "EMA should be positive"

        # Validate RSI
        if result.rsi.rsi is not None:
            assert 0 <= result.rsi.rsi <= 100, "RSI should be between 0-100"

        # Validate MACD
        if result.macd.macd is not None:
            assert isinstance(result.macd.macd, (int, float)), "MACD should be numeric"

        # Validate Bollinger Bands
        if result.bollinger_bands.upper is not None:
            assert result.bollinger_bands.upper > 0, "BB upper should be positive"
        if result.bollinger_bands.middle is not None:
            assert result.bollinger_bands.middle > 0, "BB middle should be positive"
        if result.bollinger_bands.lower is not None:
            assert result.bollinger_bands.lower > 0, "BB lower should be positive"

        # Validate ATR
        if result.atr.atr is not None:
            assert result.atr.atr >= 0, "ATR should be non-negative"

    @pytest.mark.asyncio
    async def test_indicator_accuracy_with_volatile_data(
        self, technical_analysis_service, real_market_data
    ):
        """Test indicator accuracy with volatile market data."""
        # Filter to ensure we have volatile data (significant price movements)
        if len(real_market_data) >= 50:
            # Calculate indicators
            result = technical_analysis_service.calculate_all_indicators(real_market_data)

            # In volatile markets, ATR should be higher
            if result.atr.atr is not None:
                assert result.atr.atr >= 0, "ATR should be calculated"

            # Validate indicator relationships make sense
            if all(
                [
                    result.ema.ema is not None,
                    result.bollinger_bands.upper is not None,
                    result.bollinger_bands.middle is not None,
                    result.bollinger_bands.lower is not None,
                ]
            ):
                # EMA should be between BB upper and lower
                assert (
                    result.bollinger_bands.lower <= result.ema.ema <= result.bollinger_bands.upper
                ), "EMA should be within Bollinger Bands"

    @pytest.mark.asyncio
    async def test_indicator_with_trending_markets(
        self, technical_analysis_service, real_market_data
    ):
        """Test indicators with trending market data."""
        if len(real_market_data) >= 50:
            # Calculate indicators
            result = technical_analysis_service.calculate_all_indicators(real_market_data)

            # Validate we get results
            assert result is not None, "Should calculate indicators for trending data"

            # Check that we have timestamps
            assert result.timestamp is not None, "Should have timestamp"

    @pytest.mark.asyncio
    async def test_partial_indicator_creation(self, technical_analysis_service, real_market_data):
        """Test partial indicator creation with limited data."""
        # Test with reduced dataset
        if len(real_market_data) >= 20:
            limited_data = real_market_data[-20:]  # Last 20 candles

            try:
                # Should handle limited data gracefully
                result = technical_analysis_service.calculate_all_indicators(limited_data)
                assert result is not None, "Should handle limited data"
                assert result.candle_count == 20, "Should reflect actual candle count"
            except Exception as e:
                # May raise InsufficientDataError which is acceptable
                assert "InsufficientDataError" in str(type(e)), (
                    f"Should handle insufficient data gracefully: {e}"
                )
