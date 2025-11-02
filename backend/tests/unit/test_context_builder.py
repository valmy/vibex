"""
Unit tests for Context Builder Service.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.schemas.trading_decision import TradingContext
from app.services.llm.context_builder import (
    ContextBuilderError,
    ContextBuilderService,
    get_context_builder_service,
)


class TestContextBuilderService:
    """Test cases for ContextBuilderService."""

    @pytest.fixture
    def context_builder(self):
        """Create a ContextBuilderService instance for testing."""
        return ContextBuilderService()

    @pytest.fixture
    def mock_market_data(self):
        """Create mock market data."""
        mock_candles = []
        base_time = datetime.now(timezone.utc) - timedelta(hours=100)

        for i in range(100):
            mock_candle = Mock()
            mock_candle.timestamp = base_time + timedelta(hours=i)
            mock_candle.open = 50000.0 + i * 10
            mock_candle.high = 50100.0 + i * 10
            mock_candle.low = 49900.0 + i * 10
            mock_candle.close = 50000.0 + i * 10
            mock_candle.volume = 1000.0
            mock_candles.append(mock_candle)

        return mock_candles

    @pytest.fixture
    def mock_account(self):
        """Create mock account."""
        mock_account = Mock()
        mock_account.id = 1
        mock_account.max_position_size_usd = 10000.0
        mock_account.risk_per_trade = 0.02
        return mock_account

    def test_service_initialization(self, context_builder):
        """Test service initialization."""
        assert context_builder is not None
        assert context_builder.MAX_DATA_AGE_MINUTES == 15
        assert context_builder.MIN_CANDLES_FOR_INDICATORS == 50
        assert context_builder._cache_ttl_seconds == 300

    def test_get_context_builder_service_singleton(self):
        """Test that get_context_builder_service returns singleton."""
        service1 = get_context_builder_service()
        service2 = get_context_builder_service()
        assert service1 is service2

    @pytest.mark.skip(reason="validate_data_freshness method removed - functionality moved to MarketContext.validate_data_freshness()")
    def test_validate_data_freshness_fresh_data(self, context_builder):
        """Test data freshness validation with fresh data."""
        pass

    @pytest.mark.skip(reason="validate_data_freshness method removed - functionality moved to MarketContext.validate_data_freshness()")
    def test_validate_data_freshness_stale_data(self, context_builder):
        """Test data freshness validation with stale data."""
        pass

    @pytest.mark.skip(reason="validate_data_freshness method removed - functionality moved to MarketContext.validate_data_freshness()")
    def test_validate_data_freshness_custom_max_age(self, context_builder):
        """Test data freshness validation with custom max age."""
        pass

    def test_cache_operations(self, context_builder):
        """Test cache operations."""
        # Test cleanup expired cache
        now = datetime.now(timezone.utc)
        context_builder._cache["test_key_1"] = (now, "test_data_1")
        context_builder._cache["test_key_2"] = (
            now - timedelta(seconds=400),
            "test_data_2",
        )  # Expired

        # Test cleanup expired cache
        context_builder.cleanup_expired_cache()
        assert len(context_builder._cache) == 1
        assert "test_key_1" in context_builder._cache
        assert "test_key_2" not in context_builder._cache

        # Test clear cache with pattern
        context_builder._cache["account_context_1"] = (now, "account_data")
        context_builder._cache["market_context_BTC"] = (now, "market_data")

        context_builder.clear_cache("account_context")
        assert "account_context_1" not in context_builder._cache
        assert "market_context_BTC" in context_builder._cache

        # Test clear all cache
        context_builder.clear_cache()
        assert len(context_builder._cache) == 0

    @pytest.mark.skip(reason="invalidate_cache_for_account method removed - use clear_cache() instead")
    def test_invalidate_cache_for_account(self, context_builder):
        """Test cache invalidation for specific account."""
        pass

    @pytest.mark.skip(reason="invalidate_cache_for_symbol method removed - use clear_cache() instead")
    def test_invalidate_cache_for_symbol(self, context_builder):
        """Test cache invalidation for specific symbol."""
        pass

    def test_create_partial_indicators_insufficient_data(self, context_builder):
        """Test partial indicators creation with insufficient data."""
        # Test with less than 20 candles
        mock_data = [Mock() for _ in range(10)]
        result = context_builder._create_partial_indicators(mock_data)
        assert result is None

    def test_create_partial_indicators_sufficient_data(self, context_builder, mock_market_data):
        """Test partial indicators creation with sufficient data."""
        # Use first 30 candles (enough for partial indicators)
        partial_data = mock_market_data[:30]

        result = context_builder._create_partial_indicators(partial_data)
        # Should return flat TechnicalIndicators structure
        assert result is not None
        # Check for flat structure fields
        assert hasattr(result, 'ema_20')
        assert hasattr(result, 'rsi')

    @pytest.mark.skip(reason="_validate_indicator_freshness method removed - validation moved to _validate_context")
    def test_validate_indicator_freshness_no_indicators(self, context_builder):
        """Test indicator freshness validation with no indicators."""
        pass

    @pytest.mark.skip(reason="_validate_indicator_freshness method removed - validation moved to _validate_context")
    def test_validate_indicator_freshness_with_indicators(self, context_builder):
        """Test indicator freshness validation with indicators."""
        pass

    @pytest.mark.asyncio
    async def test_validate_context_data_availability_missing_account(self, context_builder):
        """Test data availability validation with missing account."""
        # Set up a mock database session
        mock_db = AsyncMock()
        context_builder._db_session = mock_db

        # Mock account not found
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Mock market data service
        context_builder.market_data_service.get_latest_market_data = AsyncMock(return_value=[])

        result = await context_builder.validate_context_data_availability("BTCUSDT", 999)

        # Result is now a dict instead of ContextValidationResult object
        assert not result["is_valid"]
        assert "Account 999 not found" in result["missing_data"]

    @pytest.mark.asyncio
    async def test_validate_context_data_availability_no_market_data(self, context_builder):
        """Test data availability validation with no market data."""
        # Set up a mock database session
        mock_db = AsyncMock()
        context_builder._db_session = mock_db

        # Mock account found
        mock_account = Mock()
        mock_account.id = 1
        mock_account_result = AsyncMock()
        mock_account_result.scalar_one_or_none.return_value = mock_account
        mock_db.execute.return_value = mock_account_result

        # Mock no market data
        context_builder.market_data_service.get_latest_market_data = AsyncMock(return_value=[])

        result = await context_builder.validate_context_data_availability("BTCUSDT", 1)

        # Result is now a dict instead of ContextValidationResult object
        assert not result["is_valid"]
        assert "No market data available for BTCUSDT" in result["missing_data"]

    def test_handle_data_unavailability_invalid_data(self, context_builder):
        """Test data unavailability handling with invalid data."""
        # validation_result is now a dict instead of ContextValidationResult object
        validation_result = {
            "is_valid": False,
            "missing_data": ["Account not found"],
            "stale_data": [],
            "warnings": [],
            "data_age_seconds": 0,
        }

        result = context_builder.handle_data_unavailability("BTCUSDT", 1, validation_result)
        assert result is None

    def test_handle_data_unavailability_with_warnings(self, context_builder):
        """Test data unavailability handling with warnings."""
        # validation_result is now a dict instead of ContextValidationResult object
        validation_result = {
            "is_valid": True,
            "missing_data": [],
            "stale_data": [],
            "warnings": ["Limited data available"],
            "data_age_seconds": 300,
        }

        result = context_builder.handle_data_unavailability("BTCUSDT", 1, validation_result)
        # Currently returns None as degradation is not implemented
        assert result is None

    def test_validate_context_valid_context(self, context_builder):
        """Test context validation with valid context."""
        # Create mock contexts with flat TechnicalIndicators structure
        market_context = Mock()
        market_context.current_price = 50000.0
        market_context.technical_indicators = Mock()
        market_context.technical_indicators.ema_20 = 50000.0
        market_context.technical_indicators.rsi = 65.0
        market_context.funding_rate = 0.01
        market_context.open_interest = 1000000.0
        # Add price_history for validation
        mock_price = Mock()
        mock_price.timestamp = datetime.now(timezone.utc) - timedelta(minutes=2)
        market_context.price_history = [mock_price]
        market_context.validate_data_freshness = Mock(return_value=True)

        account_context = Mock()
        account_context.available_balance = 5000.0
        account_context.balance_usd = 10000.0  # Add balance_usd for validation

        result = context_builder._validate_context(market_context, account_context)

        # Result is now a dict instead of ContextValidationResult object
        assert result["is_valid"]
        assert len(result["missing_data"]) == 0
        assert len(result["stale_data"]) == 0

    def test_validate_context_stale_data(self, context_builder):
        """Test context validation with stale data."""
        # Create mock contexts with stale data and flat TechnicalIndicators structure
        market_context = Mock()
        market_context.current_price = 50000.0
        market_context.technical_indicators = None
        market_context.funding_rate = None
        market_context.open_interest = None
        # Add price_history with stale data
        mock_price = Mock()
        mock_price.timestamp = datetime.now(timezone.utc) - timedelta(minutes=30)  # Stale
        market_context.price_history = [mock_price]
        market_context.validate_data_freshness = Mock(return_value=False)

        account_context = Mock()
        account_context.available_balance = 0.0  # No balance
        account_context.balance_usd = 0.0  # Add balance_usd for validation

        result = context_builder._validate_context(market_context, account_context)

        # Result is now a dict instead of ContextValidationResult object
        assert not result["is_valid"]
        assert len(result["warnings"]) > 0


class TestContextBuilderIntegration:
    """Integration tests for Context Builder Service."""

    @pytest.fixture
    def context_builder(self):
        """Create a ContextBuilderService instance for testing."""
        return ContextBuilderService()

    @pytest.mark.asyncio
    async def test_build_trading_context_insufficient_data(self, context_builder):
        """Test building trading context with insufficient data."""
        # Mock the data availability check to return invalid (now returns dict)
        mock_validation = {
            "is_valid": False,
            "missing_data": ["No market data"],
            "stale_data": [],
            "warnings": [],
            "data_age_seconds": 0,
        }

        with patch.object(
            context_builder,
            "validate_context_data_availability",
            new_callable=AsyncMock,
            return_value=mock_validation,
        ):
            with patch.object(context_builder, "handle_data_unavailability", return_value=None):
                with pytest.raises(ContextBuilderError):
                    await context_builder.build_trading_context("BTCUSDT", 1)

    @pytest.mark.asyncio
    async def test_build_trading_context_with_degraded_context(self, context_builder):
        """Test building trading context with degraded context."""
        # Mock the data availability check to return invalid (now returns dict)
        mock_validation = {
            "is_valid": False,
            "missing_data": ["Limited data"],
            "stale_data": [],
            "warnings": [],
            "data_age_seconds": 0,
        }

        # Mock degraded context
        mock_degraded_context = Mock(spec=TradingContext)

        with patch.object(
            context_builder,
            "validate_context_data_availability",
            new_callable=AsyncMock,
            return_value=mock_validation,
        ):
            with patch.object(
                context_builder, "handle_data_unavailability", return_value=mock_degraded_context
            ):
                result = await context_builder.build_trading_context("BTCUSDT", 1)
                assert result is mock_degraded_context
