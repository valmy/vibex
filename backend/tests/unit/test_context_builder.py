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

    def test_validate_data_freshness_fresh_data(self, context_builder):
        """Test data freshness validation with fresh data."""
        fresh_timestamp = datetime.now(timezone.utc) - timedelta(minutes=5)
        is_fresh, age_minutes = context_builder.validate_data_freshness(fresh_timestamp)

        assert is_fresh is True
        assert age_minutes == pytest.approx(5.0, abs=0.1)

    def test_validate_data_freshness_stale_data(self, context_builder):
        """Test data freshness validation with stale data."""
        stale_timestamp = datetime.now(timezone.utc) - timedelta(minutes=30)
        is_fresh, age_minutes = context_builder.validate_data_freshness(stale_timestamp)

        assert is_fresh is False
        assert age_minutes == pytest.approx(30.0, abs=0.1)

    def test_validate_data_freshness_custom_max_age(self, context_builder):
        """Test data freshness validation with custom max age."""
        timestamp = datetime.now(timezone.utc) - timedelta(minutes=10)
        is_fresh, age_minutes = context_builder.validate_data_freshness(
            timestamp, max_age_minutes=5
        )

        assert is_fresh is False
        assert age_minutes == pytest.approx(10.0, abs=0.1)

    def test_cache_operations(self, context_builder):
        """Test cache operations."""
        # Test initial cache stats
        stats = context_builder.get_cache_stats()
        assert stats["total_entries"] == 0
        assert stats["expired_entries"] == 0
        assert stats["active_entries"] == 0

        # Add some mock cache entries
        now = datetime.now(timezone.utc)
        context_builder._cache["test_key_1"] = (now, "test_data_1")
        context_builder._cache["test_key_2"] = (
            now - timedelta(seconds=400),
            "test_data_2",
        )  # Expired

        # Test cache stats with entries
        stats = context_builder.get_cache_stats()
        assert stats["total_entries"] == 2
        assert stats["expired_entries"] == 1
        assert stats["active_entries"] == 1

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

    def test_invalidate_cache_for_account(self, context_builder):
        """Test cache invalidation for specific account."""
        now = datetime.now(timezone.utc)
        context_builder._cache["account_context_1"] = (now, "account_data_1")
        context_builder._cache["account_context_2"] = (now, "account_data_2")
        context_builder._cache["market_context_BTC"] = (now, "market_data")

        context_builder.invalidate_cache_for_account(1)

        assert "account_context_1" not in context_builder._cache
        assert "account_context_2" in context_builder._cache
        assert "market_context_BTC" in context_builder._cache

    def test_invalidate_cache_for_symbol(self, context_builder):
        """Test cache invalidation for specific symbol."""
        now = datetime.now(timezone.utc)
        context_builder._cache["market_context_BTC_1h-4h"] = (now, "btc_data")
        context_builder._cache["market_context_ETH_1h-4h"] = (now, "eth_data")
        context_builder._cache["account_context_1"] = (now, "account_data")

        context_builder.invalidate_cache_for_symbol("BTC")

        assert "market_context_BTC" not in [
            key for key in context_builder._cache.keys() if "BTC" in key
        ]
        assert "market_context_ETH_1h-4h" in context_builder._cache
        assert "account_context_1" in context_builder._cache

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

        with patch(
            "app.services.technical_analysis.schemas.TechnicalIndicators"
        ) as mock_indicators:
            result = context_builder._create_partial_indicators(partial_data)
            # Should attempt to create indicators
            mock_indicators.assert_called_once()

    def test_validate_indicator_freshness_no_indicators(self, context_builder):
        """Test indicator freshness validation with no indicators."""
        warnings = context_builder._validate_indicator_freshness(None, datetime.now(timezone.utc))
        assert "No technical indicators available" in warnings

    def test_validate_indicator_freshness_with_indicators(self, context_builder):
        """Test indicator freshness validation with indicators."""
        mock_indicators = Mock()
        mock_indicators.ema = Mock()
        mock_indicators.ema.ema = None  # Missing EMA value
        mock_indicators.rsi = Mock()
        mock_indicators.rsi.rsi = 65.0  # Valid RSI
        mock_indicators.macd = Mock()
        mock_indicators.macd.macd = None  # Missing MACD
        mock_indicators.macd.signal = None

        # Test with old data
        old_timestamp = datetime.now(timezone.utc) - timedelta(minutes=45)
        warnings = context_builder._validate_indicator_freshness(mock_indicators, old_timestamp)

        assert "EMA indicator not available" in warnings
        assert "MACD indicator incomplete" in warnings
        assert any("minutes old" in warning for warning in warnings)

    @pytest.mark.asyncio
    async def test_validate_context_data_availability_missing_account(self, context_builder):
        """Test data availability validation with missing account."""
        with patch("app.services.llm.context_builder.AsyncSessionLocal") as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db

            # Mock account not found
            mock_result = Mock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute.return_value = mock_result

            # Mock market data service
            context_builder.market_data_service.get_latest_market_data = AsyncMock(return_value=[])

            result = await context_builder.validate_context_data_availability("BTCUSDT", 999)

            assert not result.is_valid
            assert "Account 999 not found" in result.missing_data

    @pytest.mark.asyncio
    async def test_validate_context_data_availability_no_market_data(self, context_builder):
        """Test data availability validation with no market data."""
        with patch("app.services.llm.context_builder.AsyncSessionLocal") as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db

            # Mock account found
            mock_account_result = AsyncMock()
            mock_account_result.scalar_one_or_none.return_value = Mock()
            mock_db.execute.return_value = mock_account_result

            # Mock no market data
            context_builder.market_data_service.get_latest_market_data = AsyncMock(return_value=[])

            result = await context_builder.validate_context_data_availability("BTCUSDT", 1)

            assert not result.is_valid
            assert "No market data available for BTCUSDT" in result.missing_data

    def test_handle_data_unavailability_invalid_data(self, context_builder):
        """Test data unavailability handling with invalid data."""
        validation_result = ContextValidationResult(
            is_valid=False,
            missing_data=["Account not found"],
            stale_data=[],
            warnings=[],
            data_age_seconds=0,
        )

        result = context_builder.handle_data_unavailability("BTCUSDT", 1, validation_result)
        assert result is None

    def test_handle_data_unavailability_with_warnings(self, context_builder):
        """Test data unavailability handling with warnings."""
        validation_result = ContextValidationResult(
            is_valid=True,
            missing_data=[],
            stale_data=[],
            warnings=["Limited data available"],
            data_age_seconds=300,
        )

        result = context_builder.handle_data_unavailability("BTCUSDT", 1, validation_result)
        # Currently returns None as degradation is not implemented
        assert result is None

    def test_validate_context_valid_context(self, context_builder):
        """Test context validation with valid context."""
        # Create mock contexts
        market_context = Mock()
        market_context.data_freshness = datetime.now(timezone.utc) - timedelta(minutes=5)
        market_context.technical_indicators = Mock()
        market_context.technical_indicators.ema = Mock()
        market_context.technical_indicators.ema.ema = 50000.0
        market_context.funding_rate = 0.01
        market_context.open_interest = 1000000.0

        account_context = Mock()
        account_context.available_balance = 5000.0

        # Mock the indicator freshness validation
        with patch.object(context_builder, "_validate_indicator_freshness", return_value=[]):
            result = context_builder._validate_context(market_context, account_context)

        assert result.is_valid
        assert len(result.missing_data) == 0
        assert len(result.stale_data) == 0

    def test_validate_context_stale_data(self, context_builder):
        """Test context validation with stale data."""
        # Create mock contexts with stale data
        market_context = Mock()
        market_context.data_freshness = datetime.now(timezone.utc) - timedelta(minutes=30)  # Stale
        market_context.technical_indicators = None
        market_context.funding_rate = None
        market_context.open_interest = None

        account_context = Mock()
        account_context.available_balance = 0.0  # No balance

        result = context_builder._validate_context(market_context, account_context)

        assert not result.is_valid
        assert len(result.stale_data) > 0
        assert "Market data is" in result.stale_data[0]
        assert len(result.warnings) > 0


class TestContextBuilderIntegration:
    """Integration tests for Context Builder Service."""

    @pytest.fixture
    def context_builder(self):
        """Create a ContextBuilderService instance for testing."""
        return ContextBuilderService()

    @pytest.mark.asyncio
    async def test_build_trading_context_insufficient_data(self, context_builder):
        """Test building trading context with insufficient data."""
        # Mock the data availability check to return invalid
        mock_validation = ContextValidationResult(
            is_valid=False,
            missing_data=["No market data"],
            stale_data=[],
            warnings=[],
            data_age_seconds=0,
        )

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
        # Mock the data availability check to return invalid
        mock_validation = ContextValidationResult(
            is_valid=False,
            missing_data=["Limited data"],
            stale_data=[],
            warnings=[],
            data_age_seconds=0,
        )

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
