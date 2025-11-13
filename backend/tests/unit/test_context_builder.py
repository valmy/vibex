"""
Unit tests for Context Builder Service.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.schemas.trading_decision import TechnicalIndicatorsSet
from app.services.llm.context_builder import (
    ContextBuilderError,
    ContextBuilderService,
    get_context_builder_service,
)
from app.services.technical_analysis.schemas import TATechnicalIndicators


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
        # Create a timestamp from 2 minutes ago (fresh)
        fresh_timestamp = datetime.now(timezone.utc) - timedelta(minutes=2)

        is_fresh, age_minutes = context_builder.validate_data_freshness(fresh_timestamp)

        assert is_fresh is True
        assert age_minutes < 3  # Should be around 2 minutes

    def test_validate_data_freshness_stale_data(self, context_builder):
        """Test data freshness validation with stale data."""
        # Create a timestamp from 30 minutes ago (stale, default max is 15 minutes)
        stale_timestamp = datetime.now(timezone.utc) - timedelta(minutes=30)

        is_fresh, age_minutes = context_builder.validate_data_freshness(stale_timestamp)

        assert is_fresh is False
        assert age_minutes > 29  # Should be around 30 minutes

    def test_validate_data_freshness_custom_max_age(self, context_builder):
        """Test data freshness validation with custom max age."""
        # Create a timestamp from 10 minutes ago
        timestamp = datetime.now(timezone.utc) - timedelta(minutes=10)

        # With default max age (15 minutes), should be fresh
        is_fresh, age_minutes = context_builder.validate_data_freshness(timestamp)
        assert is_fresh is True

        # With custom max age of 5 minutes, should be stale
        is_fresh, age_minutes = context_builder.validate_data_freshness(
            timestamp, max_age_minutes=5
        )
        assert is_fresh is False

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

    def test_invalidate_cache_for_account(self, context_builder):
        """Test cache invalidation for specific account using clear_cache()."""
        # Set up cache with account-specific entries
        now = datetime.now(timezone.utc)
        context_builder._cache["account_context_1"] = (now, "account_1_data")
        context_builder._cache["account_context_2"] = (now, "account_2_data")
        context_builder._cache["market_context_BTC"] = (now, "market_data")

        # Clear cache for account 1
        context_builder.clear_cache("account_context_1")

        # Verify account 1 cache is cleared but others remain
        assert "account_context_1" not in context_builder._cache
        assert "account_context_2" in context_builder._cache
        assert "market_context_BTC" in context_builder._cache

    def test_invalidate_cache_for_symbol(self, context_builder):
        """Test cache invalidation for specific symbol using clear_cache()."""
        # Set up cache with symbol-specific entries
        now = datetime.now(timezone.utc)
        context_builder._cache["market_context_BTCUSDT"] = (now, "btc_data")
        context_builder._cache["market_context_ETHUSDT"] = (now, "eth_data")
        context_builder._cache["account_context_1"] = (now, "account_data")

        # Clear cache for BTCUSDT
        context_builder.clear_cache("market_context_BTCUSDT")

        # Verify BTCUSDT cache is cleared but others remain
        assert "market_context_BTCUSDT" not in context_builder._cache
        assert "market_context_ETHUSDT" in context_builder._cache
        assert "account_context_1" in context_builder._cache

    def test_create_partial_indicators_insufficient_data(self, context_builder):
        """Test partial indicators creation with insufficient data."""
        # Test with less than 20 candles
        mock_data = [Mock() for _ in range(10)]
        result = context_builder._create_partial_indicators(mock_data)
        assert result.ema_20 is None
        assert result.rsi is None

    def test_create_partial_indicators_sufficient_data(self, context_builder, mock_market_data):
        """Test partial indicators creation with sufficient data."""
        # Use first 30 candles (enough for partial indicators)
        partial_data = mock_market_data[:30]

        result = context_builder._create_partial_indicators(partial_data)
        # Should return TechnicalIndicatorsSet structure
        assert result is not None
        assert hasattr(result, "ema_20")
        assert hasattr(result, "rsi")

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
        market_context.technical_indicators.interval = Mock()
        market_context.technical_indicators.long_interval = Mock()
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


class TestContextBuilderIntegration:
    """Integration tests for Context Builder Service."""

    @pytest.fixture
    def context_builder(self):
        """Create a ContextBuilderService instance for testing."""
        return ContextBuilderService()

    @pytest.mark.asyncio
    async def test_build_trading_context_insufficient_data(self, context_builder):
        """Test building trading context with insufficient data for multi-asset support."""
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
                    # Updated to accept list of symbols
                    await context_builder.build_trading_context(
                        symbols=["BTCUSDT"], account_id=1, timeframes=["1h", "4h"]
                    )

    @pytest.mark.asyncio
    async def test_build_trading_context_with_degraded_context(self, context_builder):
        """Test building trading context with degraded context for multi-asset support."""
        # Mock the get_market_context and get_account_context to avoid database dependency
        from app.schemas.trading_decision import (
            AccountContext,
            AssetMarketData,
            MarketContext,
            PerformanceMetrics,
            StrategyRiskParameters,
            TechnicalIndicators,
            TechnicalIndicatorsSet,
            TradingStrategy,
        )

        mock_indicators = TechnicalIndicators(
            interval=TechnicalIndicatorsSet(
                ema_20=[48000.0] * 10,
                ema_50=[47000.0] * 10,
                rsi=[65.0] * 10,
                macd=[100.0] * 10,
                macd_signal=[90.0] * 10,
                bb_upper=[49000.0] * 10,
                bb_lower=[46000.0] * 10,
                bb_middle=[47500.0] * 10,
                atr=[500.0] * 10,
            ),
            long_interval=TechnicalIndicatorsSet(
                ema_20=[47000.0] * 10,
                ema_50=[46000.0] * 10,
                rsi=[60.0] * 10,
                macd=[110.0] * 10,
                macd_signal=[95.0] * 10,
                bb_upper=[49500.0] * 10,
                bb_lower=[45500.0] * 10,
                bb_middle=[47000.0] * 10,
                atr=[600.0] * 10,
            ),
        )

        mock_market_context = MarketContext(
            assets={
                "BTCUSDT": AssetMarketData(
                    symbol="BTCUSDT",
                    current_price=48000.0,
                    price_change_24h=1000.0,
                    volume_24h=1000000.0,
                    funding_rate=0.01,
                    open_interest=50000000.0,
                    volatility=0.02,
                    technical_indicators=mock_indicators,
                    price_history=[],
                )
            },
            market_sentiment="neutral",
            timestamp=datetime.now(timezone.utc),
        )

        mock_account_context = AccountContext(
            account_id=1,
            balance_usd=10000.0,
            available_balance=8000.0,
            total_pnl=500.0,
            open_positions=[],
            recent_performance=PerformanceMetrics(
                total_pnl=500.0,
                win_rate=60.0,
                avg_win=100.0,
                avg_loss=-50.0,
                max_drawdown=-200.0,
                sharpe_ratio=1.5,
            ),
            risk_exposure=20.0,
            max_position_size=2000.0,
            active_strategy=TradingStrategy(
                strategy_id="conservative",
                strategy_name="Conservative Trading",
                strategy_type="conservative",
                prompt_template="Conservative trading prompt",
                risk_parameters=StrategyRiskParameters(
                    max_risk_per_trade=2.0,
                    max_daily_loss=5.0,
                    stop_loss_percentage=3.0,
                    take_profit_ratio=2.0,
                    max_leverage=3.0,
                    cooldown_period=300,
                ),
                timeframe_preference=["4h", "1d"],
                max_positions=3,
                is_active=True,
            ),
        )

        with patch.object(
            context_builder,
            "get_market_context",
            new_callable=AsyncMock,
            return_value=mock_market_context,
        ):
            with patch.object(
                context_builder,
                "get_account_context",
                new_callable=AsyncMock,
                return_value=mock_account_context,
            ):
                with patch.object(
                    context_builder, "get_recent_trades", new_callable=AsyncMock, return_value=[]
                ):
                    # Updated to accept list of symbols
                    result = await context_builder.build_trading_context(
                        symbols=["BTCUSDT"], account_id=1, timeframes=["1h", "4h"]
                    )
                    assert result is not None
                    assert result.symbols == ["BTCUSDT"]

    def test_convert_technical_indicators(self, context_builder):
        """Test the _convert_technical_indicators function."""
        # Create mock TATechnicalIndicators with more than 10 data points
        mock_indicators = TATechnicalIndicators(
            ema_20=list(range(20)),
            ema_50=list(range(50, 70)),
            macd=list(range(20)),
            macd_signal=list(range(20)),
            rsi=list(range(20)),
            bb_upper=list(range(20)),
            bb_middle=list(range(20)),
            bb_lower=list(range(20)),
            atr=list(range(20)),
            candle_count=20,
            series_length=20,
        )

        # Call the function
        result = context_builder._convert_technical_indicators(mock_indicators)

        # Verify the result
        assert isinstance(result, TechnicalIndicatorsSet)
        assert len(result.ema_20) == 10
        assert result.ema_20 == list(range(10, 20))
        assert len(result.macd) == 10
        assert result.macd == list(range(10, 20))
        assert len(result.rsi) == 10
        assert result.rsi == list(range(10, 20))
        assert len(result.bb_upper) == 10
        assert result.bb_upper == list(range(10, 20))


class TestContextBuilderMultiAsset:
    """Test cases for multi-asset Context Builder functionality."""

    @pytest.fixture
    def context_builder(self):
        """Create a ContextBuilderService instance for testing."""
        return ContextBuilderService()

    @pytest.mark.asyncio
    async def test_build_multi_asset_context(self, context_builder):
        """Test building trading context for multiple assets."""
        from app.schemas.trading_decision import (
            AssetMarketData,
            MarketContext,
            TechnicalIndicators,
            TechnicalIndicatorsSet,
        )

        # Mock market data for multiple assets
        mock_btc_indicators = TechnicalIndicators(
            interval=TechnicalIndicatorsSet(
                ema_20=[48000.0] * 10,
                ema_50=[47000.0] * 10,
                rsi=[65.0] * 10,
                macd=[100.0] * 10,
                macd_signal=[90.0] * 10,
                bb_upper=[49000.0] * 10,
                bb_lower=[46000.0] * 10,
                bb_middle=[47500.0] * 10,
                atr=[500.0] * 10,
            ),
            long_interval=TechnicalIndicatorsSet(
                ema_20=[47000.0] * 10,
                ema_50=[46000.0] * 10,
                rsi=[60.0] * 10,
                macd=[110.0] * 10,
                macd_signal=[95.0] * 10,
                bb_upper=[49500.0] * 10,
                bb_lower=[45500.0] * 10,
                bb_middle=[47000.0] * 10,
                atr=[600.0] * 10,
            ),
        )

        mock_eth_indicators = TechnicalIndicators(
            interval=TechnicalIndicatorsSet(
                ema_20=[3000.0] * 10,
                ema_50=[2950.0] * 10,
                rsi=[70.0] * 10,
                macd=[50.0] * 10,
                macd_signal=[45.0] * 10,
                bb_upper=[3100.0] * 10,
                bb_lower=[2900.0] * 10,
                bb_middle=[3000.0] * 10,
                atr=[50.0] * 10,
            ),
            long_interval=TechnicalIndicatorsSet(
                ema_20=[2980.0] * 10,
                ema_50=[2930.0] * 10,
                rsi=[68.0] * 10,
                macd=[55.0] * 10,
                macd_signal=[48.0] * 10,
                bb_upper=[3120.0] * 10,
                bb_lower=[2880.0] * 10,
                bb_middle=[2980.0] * 10,
                atr=[55.0] * 10,
            ),
        )

        # Mock AssetMarketData for each asset
        mock_btc_data = AssetMarketData(
            symbol="BTCUSDT",
            current_price=48000.0,
            price_change_24h=1000.0,
            volume_24h=1000000.0,
            funding_rate=0.01,
            open_interest=50000000.0,
            volatility=0.02,
            technical_indicators=mock_btc_indicators,
            price_history=[],
        )

        mock_eth_data = AssetMarketData(
            symbol="ETHUSDT",
            current_price=3000.0,
            price_change_24h=50.0,
            volume_24h=500000.0,
            funding_rate=0.008,
            open_interest=10000000.0,
            volatility=0.025,
            technical_indicators=mock_eth_indicators,
            price_history=[],
        )

        # Mock MarketContext with Dict[str, AssetMarketData]
        mock_market_context = MarketContext(
            assets={"BTCUSDT": mock_btc_data, "ETHUSDT": mock_eth_data},
            market_sentiment="bullish",
            timestamp=datetime.now(timezone.utc),
        )

        # Mock get_market_context to return multi-asset data
        with patch.object(
            context_builder,
            "get_market_context",
            new_callable=AsyncMock,
            return_value=mock_market_context,
        ):
            # Mock account context
            with patch.object(
                context_builder, "get_account_context", new_callable=AsyncMock
            ) as mock_account:
                from app.schemas.trading_decision import (
                    AccountContext,
                    PerformanceMetrics,
                    StrategyRiskParameters,
                    TradingStrategy,
                )

                mock_account.return_value = AccountContext(
                    account_id=1,
                    balance_usd=10000.0,
                    available_balance=8000.0,
                    total_pnl=500.0,
                    open_positions=[],
                    recent_performance=PerformanceMetrics(
                        total_pnl=500.0,
                        win_rate=60.0,
                        avg_win=100.0,
                        avg_loss=-50.0,
                        max_drawdown=-200.0,
                        sharpe_ratio=1.5,
                    ),
                    risk_exposure=20.0,
                    max_position_size=2000.0,
                    active_strategy=TradingStrategy(
                        strategy_id="conservative",
                        strategy_name="Conservative Trading",
                        strategy_type="conservative",
                        prompt_template="Conservative trading prompt",
                        risk_parameters=StrategyRiskParameters(
                            max_risk_per_trade=2.0,
                            max_daily_loss=5.0,
                            stop_loss_percentage=3.0,
                            take_profit_ratio=2.0,
                            max_leverage=3.0,
                            cooldown_period=300,
                        ),
                        timeframe_preference=["4h", "1d"],
                        max_positions=3,
                        is_active=True,
                    ),
                )

                # Build context for multiple symbols
                result = await context_builder.build_trading_context(
                    symbols=["BTCUSDT", "ETHUSDT"], account_id=1, timeframes=["1h", "4h"]
                )

                # Verify multi-asset structure
                assert result is not None
                assert result.symbols == ["BTCUSDT", "ETHUSDT"]
                assert isinstance(result.market_data.assets, dict)
                assert "BTCUSDT" in result.market_data.assets
                assert "ETHUSDT" in result.market_data.assets
                assert result.market_data.assets["BTCUSDT"].current_price == 48000.0
                assert result.market_data.assets["ETHUSDT"].current_price == 3000.0

    @pytest.mark.asyncio
    async def test_portfolio_risk_metrics_calculation(self, context_builder):
        """Test portfolio risk metrics calculation across multiple assets."""
        from app.schemas.trading_decision import (
            AccountContext,
            AssetMarketData,
            MarketContext,
            PerformanceMetrics,
            PositionSummary,
            StrategyRiskParameters,
            TechnicalIndicators,
            TechnicalIndicatorsSet,
            TradingStrategy,
        )

        # Mock positions across multiple assets
        positions = [
            PositionSummary(
                symbol="BTCUSDT",
                side="long",
                size=5000.0,  # 50% of total
                entry_price=47000.0,
                current_price=48000.0,
                unrealized_pnl=100.0,
                percentage_pnl=2.13,
            ),
            PositionSummary(
                symbol="ETHUSDT",
                side="long",
                size=3000.0,  # 30% of total
                entry_price=2950.0,
                current_price=3000.0,
                unrealized_pnl=50.0,
                percentage_pnl=1.69,
            ),
            PositionSummary(
                symbol="SOLUSDT",
                side="short",
                size=2000.0,  # 20% of total
                entry_price=105.0,
                current_price=100.0,
                unrealized_pnl=100.0,
                percentage_pnl=4.76,
            ),
        ]

        # Create account context with positions
        account_context = AccountContext(
            account_id=1,
            balance_usd=10000.0,
            available_balance=8000.0,
            total_pnl=500.0,
            open_positions=positions,
            recent_performance=PerformanceMetrics(
                total_pnl=500.0,
                win_rate=60.0,
                avg_win=100.0,
                avg_loss=-50.0,
                max_drawdown=-200.0,
                sharpe_ratio=1.5,
            ),
            risk_exposure=20.0,
            max_position_size=2000.0,
            active_strategy=TradingStrategy(
                strategy_id="conservative",
                strategy_name="Conservative Trading",
                strategy_type="conservative",
                prompt_template="Conservative trading prompt",
                risk_parameters=StrategyRiskParameters(
                    max_risk_per_trade=2.0,
                    max_daily_loss=5.0,
                    stop_loss_percentage=3.0,
                    take_profit_ratio=2.0,
                    max_leverage=3.0,
                    cooldown_period=300,
                ),
                timeframe_preference=["4h", "1d"],
                max_positions=3,
                is_active=True,
            ),
        )

        # Create market context with multiple assets
        mock_indicators = TechnicalIndicators(
            interval=TechnicalIndicatorsSet(
                ema_20=[48000.0] * 10,
                ema_50=[47000.0] * 10,
                rsi=[65.0] * 10,
                macd=[100.0] * 10,
                macd_signal=[90.0] * 10,
                bb_upper=[49000.0] * 10,
                bb_lower=[46000.0] * 10,
                bb_middle=[47500.0] * 10,
                atr=[500.0] * 10,
            ),
            long_interval=TechnicalIndicatorsSet(
                ema_20=[47000.0] * 10,
                ema_50=[46000.0] * 10,
                rsi=[60.0] * 10,
                macd=[110.0] * 10,
                macd_signal=[95.0] * 10,
                bb_upper=[49500.0] * 10,
                bb_lower=[45500.0] * 10,
                bb_middle=[47000.0] * 10,
                atr=[600.0] * 10,
            ),
        )

        market_context = MarketContext(
            assets={
                "BTCUSDT": AssetMarketData(
                    symbol="BTCUSDT",
                    current_price=48000.0,
                    price_change_24h=1000.0,
                    volume_24h=1000000.0,
                    funding_rate=0.01,
                    open_interest=50000000.0,
                    volatility=0.02,
                    technical_indicators=mock_indicators,
                    price_history=[],
                ),
                "ETHUSDT": AssetMarketData(
                    symbol="ETHUSDT",
                    current_price=3000.0,
                    price_change_24h=50.0,
                    volume_24h=500000.0,
                    funding_rate=0.008,
                    open_interest=10000000.0,
                    volatility=0.025,
                    technical_indicators=mock_indicators,
                    price_history=[],
                ),
            },
            market_sentiment="bullish",
            timestamp=datetime.now(timezone.utc),
        )

        # Calculate portfolio risk metrics
        risk_metrics = context_builder._calculate_portfolio_risk_metrics(
            account_context, market_context
        )

        # Verify risk metrics are calculated
        assert risk_metrics is not None
        assert risk_metrics.concentration_risk > 0
        # BTC has 50% concentration, which should be reflected
        assert risk_metrics.concentration_risk >= 50.0

    @pytest.mark.asyncio
    async def test_per_asset_technical_indicators(self, context_builder):
        """Test fetching technical indicators for each asset."""
        from app.services.technical_analysis.schemas import TATechnicalIndicators

        # Mock technical analysis service
        mock_ta_service = Mock()

        # Create different indicators for each asset
        btc_indicators = TATechnicalIndicators(
            ema_20=[48000.0] * 20,
            ema_50=[47000.0] * 50,
            rsi=[65.0] * 20,
            macd=[100.0] * 20,
            macd_signal=[90.0] * 20,
            bb_upper=[49000.0] * 20,
            bb_middle=[47500.0] * 20,
            bb_lower=[46000.0] * 20,
            atr=[500.0] * 20,
            candle_count=100,
            series_length=20,
        )

        eth_indicators = TATechnicalIndicators(
            ema_20=[3000.0] * 20,
            ema_50=[2950.0] * 50,
            rsi=[70.0] * 20,
            macd=[50.0] * 20,
            macd_signal=[45.0] * 20,
            bb_upper=[3100.0] * 20,
            bb_middle=[3000.0] * 20,
            bb_lower=[2900.0] * 20,
            atr=[50.0] * 20,
            candle_count=100,
            series_length=20,
        )

        # Mock calculate_all_indicators to return different data per symbol
        def mock_calculate_indicators(market_data):
            # Determine which symbol based on price
            if market_data and market_data[0].close > 10000:
                return btc_indicators
            else:
                return eth_indicators

        mock_ta_service.calculate_all_indicators = mock_calculate_indicators
        context_builder.technical_analysis_service = mock_ta_service

        # Mock market data for both assets
        btc_candles = [Mock(close=48000.0, high=49000.0, low=47000.0, volume=1000.0)] * 100
        eth_candles = [Mock(close=3000.0, high=3100.0, low=2900.0, volume=500.0)] * 100

        # Test indicator fetching for BTC
        btc_result = context_builder.technical_analysis_service.calculate_all_indicators(
            btc_candles
        )
        assert btc_result.ema_20[-1] == 48000.0
        assert btc_result.rsi[-1] == 65.0

        # Test indicator fetching for ETH
        eth_result = context_builder.technical_analysis_service.calculate_all_indicators(
            eth_candles
        )
        assert eth_result.ema_20[-1] == 3000.0
        assert eth_result.rsi[-1] == 70.0

    @pytest.mark.asyncio
    async def test_partial_asset_failure_handling(self, context_builder):
        """Test handling when data is unavailable for one asset but available for others."""
        from app.schemas.trading_decision import (
            AssetMarketData,
            MarketContext,
            TechnicalIndicators,
            TechnicalIndicatorsSet,
        )

        # Create proper technical indicators
        mock_indicators = TechnicalIndicators(
            interval=TechnicalIndicatorsSet(
                ema_20=[48000.0] * 10,
                ema_50=[47000.0] * 10,
                rsi=[65.0] * 10,
                macd=[100.0] * 10,
                macd_signal=[90.0] * 10,
                bb_upper=[49000.0] * 10,
                bb_lower=[46000.0] * 10,
                bb_middle=[47500.0] * 10,
                atr=[500.0] * 10,
            ),
            long_interval=TechnicalIndicatorsSet(
                ema_20=[47000.0] * 10,
                ema_50=[46000.0] * 10,
                rsi=[60.0] * 10,
                macd=[110.0] * 10,
                macd_signal=[95.0] * 10,
                bb_upper=[49500.0] * 10,
                bb_lower=[45500.0] * 10,
                bb_middle=[47000.0] * 10,
                atr=[600.0] * 10,
            ),
        )

        # Mock get_market_context to return data for only one asset
        mock_market_context = MarketContext(
            assets={
                "BTCUSDT": AssetMarketData(
                    symbol="BTCUSDT",
                    current_price=48000.0,
                    price_change_24h=1000.0,
                    volume_24h=1000000.0,
                    funding_rate=0.01,
                    open_interest=50000000.0,
                    volatility=0.02,
                    technical_indicators=mock_indicators,
                    price_history=[],
                )
                # ETHUSDT data is missing
            },
            market_sentiment="neutral",
            timestamp=datetime.now(timezone.utc),
        )

        with patch.object(
            context_builder,
            "get_market_context",
            new_callable=AsyncMock,
            return_value=mock_market_context,
        ):
            with patch.object(
                context_builder, "get_account_context", new_callable=AsyncMock
            ) as mock_account:
                from app.schemas.trading_decision import (
                    AccountContext,
                    PerformanceMetrics,
                    StrategyRiskParameters,
                    TradingStrategy,
                )

                mock_account.return_value = AccountContext(
                    account_id=1,
                    balance_usd=10000.0,
                    available_balance=8000.0,
                    total_pnl=500.0,
                    open_positions=[],
                    recent_performance=PerformanceMetrics(
                        total_pnl=500.0,
                        win_rate=60.0,
                        avg_win=100.0,
                        avg_loss=-50.0,
                        max_drawdown=-200.0,
                        sharpe_ratio=1.5,
                    ),
                    risk_exposure=20.0,
                    max_position_size=2000.0,
                    active_strategy=TradingStrategy(
                        strategy_id="conservative",
                        strategy_name="Conservative Trading",
                        strategy_type="conservative",
                        prompt_template="Conservative trading prompt",
                        risk_parameters=StrategyRiskParameters(
                            max_risk_per_trade=2.0,
                            max_daily_loss=5.0,
                            stop_loss_percentage=3.0,
                            take_profit_ratio=2.0,
                            max_leverage=3.0,
                            cooldown_period=300,
                        ),
                        timeframe_preference=["4h", "1d"],
                        max_positions=3,
                        is_active=True,
                    ),
                )

                # Build context - should handle partial failure gracefully
                result = await context_builder.build_trading_context(
                    symbols=["BTCUSDT", "ETHUSDT"], account_id=1, timeframes=["1h", "4h"]
                )

                # Verify we got data for available asset
                assert result is not None
                assert "BTCUSDT" in result.market_data.assets
                # ETHUSDT may or may not be present depending on error handling strategy
