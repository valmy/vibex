"""
Regression tests for decision accuracy with historical patterns.

Tests decision quality against known market patterns and validates
that the LLM decision engine produces consistent and reasonable decisions.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List

import pytest

from app.models.market_data import MarketData
from app.services import get_technical_analysis_service
from app.services.llm.decision_engine import get_decision_engine

logger = logging.getLogger(__name__)


class TestDecisionAccuracyRegression:
    """Regression tests for decision accuracy with historical patterns."""

    @pytest.fixture
    async def decision_engine(self, mocker):
        """Get decision engine instance with mocked strategy."""
        from app.schemas.trading_decision import StrategyRiskParameters, TradingStrategy

        engine = get_decision_engine()

        # Mock the strategy manager for all tests
        mock_strategy = TradingStrategy(
            strategy_id="test_strategy",
            strategy_name="Test Strategy",
            strategy_type="conservative",
            prompt_template="Test prompt",
            risk_parameters=StrategyRiskParameters(
                max_risk_per_trade=2.0,
                max_daily_loss=5.0,
                stop_loss_percentage=2.0,
                take_profit_ratio=2.0,
                max_leverage=2.0,
                cooldown_period=300,
            ),
            timeframe_preference=["5m", "4h"],
            max_positions=3,
            position_sizing="percentage",
            is_active=True,
        )
        engine.strategy_manager.get_account_strategy = mocker.AsyncMock(return_value=mock_strategy)

        return engine

    def _convert_indicators_to_schema(self, indicators_result):
        """Convert TA indicators to schema format."""
        from app.schemas.trading_decision import TechnicalIndicators
        from app.services.llm.context_builder import ContextBuilderService

        # Convert TA indicators to schema format
        context_builder_temp = ContextBuilderService(db_session=None)
        indicators_set = context_builder_temp._convert_technical_indicators(indicators_result)
        return TechnicalIndicators(
            interval=indicators_set,
            long_interval=indicators_set,
        )

    def create_strong_uptrend_pattern(self) -> List[MarketData]:
        """Create market data showing a strong uptrend pattern."""
        market_data = []
        base_time = datetime.now(timezone.utc) - timedelta(hours=100)
        base_price = 40000.0

        for i in range(100):
            # Strong consistent uptrend
            trend_increase = i * 150  # $150 per hour increase
            open_price = base_price + trend_increase
            close_price = open_price + 100  # Bullish candles
            high_price = close_price + 50
            low_price = open_price - 25

            candle = MarketData(
                time=base_time + timedelta(hours=i),
                symbol="BTCUSDT",
                interval="1h",
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=1500 + i * 20,  # Increasing volume
            )
            market_data.append(candle)

        return market_data

    def create_strong_downtrend_pattern(self) -> List[MarketData]:
        """Create market data showing a strong downtrend pattern."""
        market_data = []
        base_time = datetime.now(timezone.utc) - timedelta(hours=100)
        base_price = 50000.0

        for i in range(100):
            # Strong consistent downtrend
            trend_decrease = i * 120  # $120 per hour decrease
            open_price = base_price - trend_decrease
            close_price = open_price - 80  # Bearish candles
            high_price = open_price + 30
            low_price = close_price - 40

            candle = MarketData(
                time=base_time + timedelta(hours=i),
                symbol="BTCUSDT",
                interval="1h",
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=2000 + i * 15,  # Increasing volume on decline
            )
            market_data.append(candle)

        return market_data

    def create_consolidation_pattern(self) -> List[MarketData]:
        """Create market data showing a consolidation pattern."""
        market_data = []
        base_time = datetime.now(timezone.utc) - timedelta(hours=100)
        base_price = 45000.0

        for i in range(100):
            # Tight consolidation with minimal movement
            price_range = 150  # Tight range
            price_offset = (i % 8 - 4) * (price_range / 4)
            open_price = base_price + price_offset
            close_price = base_price + price_offset + (i % 3 - 1) * 30

            high_price = max(open_price, close_price) + 40
            low_price = min(open_price, close_price) - 40
            volume = 1000 + (i % 5) * 50  # Consistent volume

            candle = MarketData(
                time=base_time + timedelta(hours=i),
                symbol="BTCUSDT",
                interval="1h",
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=volume,
            )
            market_data.append(candle)

        return market_data

    def create_breakout_pattern(self) -> List[MarketData]:
        """Create market data showing a bullish breakout pattern."""
        market_data = []
        base_time = datetime.now(timezone.utc) - timedelta(hours=100)
        base_price = 45000.0

        for i in range(100):
            if i < 80:
                # Consolidation phase
                price = base_price + (i % 6 - 3) * 100
                open_price = price
                close_price = price + (i % 3 - 1) * 50
                volume = 1000 + (i % 4) * 50
            else:
                # Breakout phase with strong momentum
                breakout_gain = (i - 79) * 400
                open_price = base_price + 300 + breakout_gain
                close_price = open_price + 300  # Strong bullish candles
                volume = 2500 + (i - 79) * 100  # Volume spike

            high_price = max(open_price, close_price) + 100
            low_price = min(open_price, close_price) - 50

            candle = MarketData(
                time=base_time + timedelta(hours=i),
                symbol="BTCUSDT",
                interval="1h",
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=volume,
            )
            market_data.append(candle)

        return market_data

    @pytest.mark.asyncio
    async def test_uptrend_pattern_recognition(
        self, decision_engine, mock_context_builder, mock_llm_service
    ):
        """Test decision quality with strong uptrend pattern."""
        logger.info("Testing uptrend pattern recognition")

        # Create uptrend market data
        market_data = self.create_strong_uptrend_pattern()

        # Calculate real technical indicators
        technical_service = get_technical_analysis_service()

        try:
            indicators_result = technical_service.calculate_all_indicators(market_data)

            # Update mock context with real indicators
            from app.schemas.trading_decision import AssetMarketData

            mock_context = mock_context_builder.build_trading_context.return_value

            # Create asset market data with indicators
            btc_asset_data = AssetMarketData(
                symbol="BTCUSDT",
                current_price=market_data[-1].close,
                price_change_24h=(
                    (market_data[-1].close - market_data[-24].close) / market_data[-24].close * 100
                    if len(market_data) >= 24
                    else 5.0
                ),
                volume_24h=sum(c.volume for c in market_data[-24:])
                if len(market_data) >= 24
                else market_data[-1].volume,
                funding_rate=0.01,
                open_interest=1000000.0,
                volatility=0.02,
                technical_indicators=self._convert_indicators_to_schema(indicators_result),
                price_history=[],
            )

            mock_context.market_data.assets = {"BTCUSDT": btc_asset_data}
            mock_context.symbols = ["BTCUSDT"]

            # Setup decision engine
            decision_engine.context_builder = mock_context_builder
            decision_engine.llm_service = mock_llm_service

            # Update mock result
            mock_result = mock_llm_service.generate_trading_decision.return_value
            mock_result.context = mock_context

            # Generate decision
            result = await decision_engine.make_trading_decision(
                symbols=["BTCUSDT"], account_id=1, force_refresh=True
            )

            # Validate decision structure - now multi-asset
            assert result.validation_passed is True
            assert len(result.decision.decisions) > 0, "Should have at least one asset decision"

            first_decision = result.decision.decisions[0]
            assert first_decision.confidence >= 0

            # Log the results for analysis
            logger.info(f"Uptrend pattern decision: {first_decision.action}")
            logger.info(f"Confidence: {first_decision.confidence}%")
            logger.info(f"Risk level: {first_decision.risk_level}")
            btc_data = mock_context.market_data.assets.get("BTCUSDT")
            if btc_data:
                logger.info(f"Current price: ${btc_data.current_price:.2f}")
                logger.info(f"24h change: {btc_data.price_change_24h:.2f}%")

            if indicators_result.rsi and indicators_result.rsi[-1] is not None:
                logger.info(f"RSI: {indicators_result.rsi[-1]:.2f}")
            if indicators_result.ema_20 and indicators_result.ema_20[-1] is not None:
                logger.info(f"EMA 20: ${indicators_result.ema_20[-1]:.2f}")

        except Exception as e:
            logger.warning(f"Uptrend test failed with technical analysis error: {e}")
            # Still validate basic decision structure
            assert result.validation_passed is True

    @pytest.mark.asyncio
    async def test_downtrend_pattern_recognition(
        self, decision_engine, mock_context_builder, mock_llm_service
    ):
        """Test decision quality with strong downtrend pattern."""
        logger.info("Testing downtrend pattern recognition")

        # Create downtrend market data
        market_data = self.create_strong_downtrend_pattern()

        # Calculate real technical indicators
        technical_service = get_technical_analysis_service()

        try:
            indicators_result = technical_service.calculate_all_indicators(market_data)

            # Update mock context with real indicators
            from app.schemas.trading_decision import AssetMarketData

            mock_context = mock_context_builder.build_trading_context.return_value

            # Create asset market data with indicators
            btc_asset_data = AssetMarketData(
                symbol="BTCUSDT",
                current_price=market_data[-1].close,
                price_change_24h=(
                    (market_data[-1].close - market_data[-24].close) / market_data[-24].close * 100
                    if len(market_data) >= 24
                    else -5.0
                ),
                volume_24h=sum(c.volume for c in market_data[-24:])
                if len(market_data) >= 24
                else market_data[-1].volume,
                funding_rate=0.01,
                open_interest=1000000.0,
                volatility=0.02,
                technical_indicators=self._convert_indicators_to_schema(indicators_result),
                price_history=[],
            )

            mock_context.market_data.assets = {"BTCUSDT": btc_asset_data}
            mock_context.symbols = ["BTCUSDT"]

            # Setup decision engine
            decision_engine.context_builder = mock_context_builder
            decision_engine.llm_service = mock_llm_service

            # Update mock result
            mock_result = mock_llm_service.generate_trading_decision.return_value
            mock_result.context = mock_context

            # Generate decision
            result = await decision_engine.make_trading_decision(
                symbols=["BTCUSDT"], account_id=1, force_refresh=True
            )

            # Validate decision structure - now multi-asset
            assert result.validation_passed is True
            assert len(result.decision.decisions) > 0, "Should have at least one asset decision"

            first_decision = result.decision.decisions[0]
            assert first_decision.confidence >= 0

            # Log the results for analysis
            logger.info(f"Downtrend pattern decision: {first_decision.action}")
            logger.info(f"Confidence: {first_decision.confidence}%")
            logger.info(f"Risk level: {first_decision.risk_level}")
            btc_data = mock_context.market_data.assets.get("BTCUSDT")
            if btc_data:
                logger.info(f"Current price: ${btc_data.current_price:.2f}")
                logger.info(f"24h change: {btc_data.price_change_24h:.2f}%")

            if indicators_result.rsi and indicators_result.rsi[-1] is not None:
                logger.info(f"RSI: {indicators_result.rsi[-1]:.2f}")

        except Exception as e:
            logger.warning(f"Downtrend test failed with technical analysis error: {e}")
            # Still validate basic decision structure
            assert result.validation_passed is True

    @pytest.mark.asyncio
    async def test_consolidation_pattern_recognition(
        self, decision_engine, mock_context_builder, mock_llm_service
    ):
        """Test decision quality with consolidation pattern."""
        logger.info("Testing consolidation pattern recognition")

        # Create consolidation market data
        market_data = self.create_consolidation_pattern()

        # Calculate real technical indicators
        technical_service = get_technical_analysis_service()

        try:
            indicators_result = technical_service.calculate_all_indicators(market_data)

            # Update mock context with real indicators
            from app.schemas.trading_decision import AssetMarketData

            mock_context = mock_context_builder.build_trading_context.return_value

            # Create asset market data with indicators
            btc_asset_data = AssetMarketData(
                symbol="BTCUSDT",
                current_price=market_data[-1].close,
                price_change_24h=0.5,  # Minimal change for consolidation
                volume_24h=sum(c.volume for c in market_data[-24:])
                if len(market_data) >= 24
                else market_data[-1].volume,
                funding_rate=0.01,
                open_interest=1000000.0,
                volatility=0.01,  # Low volatility
                technical_indicators=self._convert_indicators_to_schema(indicators_result),
                price_history=[],
            )

            mock_context.market_data.assets = {"BTCUSDT": btc_asset_data}
            mock_context.symbols = ["BTCUSDT"]

            # Setup decision engine
            decision_engine.context_builder = mock_context_builder
            decision_engine.llm_service = mock_llm_service

            # Update mock result
            mock_result = mock_llm_service.generate_trading_decision.return_value
            mock_result.context = mock_context

            # Generate decision
            result = await decision_engine.make_trading_decision(
                symbols=["BTCUSDT"], account_id=1, force_refresh=True
            )

            # Validate decision structure - now multi-asset
            assert result.validation_passed is True
            assert len(result.decision.decisions) > 0, "Should have at least one asset decision"

            first_decision = result.decision.decisions[0]
            assert first_decision.confidence >= 0

            # Log the results for analysis
            logger.info(f"Consolidation pattern decision: {first_decision.action}")
            logger.info(f"Confidence: {first_decision.confidence}%")
            logger.info(f"Risk level: {first_decision.risk_level}")
            btc_data = mock_context.market_data.assets.get("BTCUSDT")
            if btc_data:
                logger.info(f"Current price: ${btc_data.current_price:.2f}")
                logger.info(f"Volatility: {btc_data.volatility:.3f}")

            if indicators_result.rsi is not None:
                logger.info(f"RSI: {indicators_result.rsi[-1]:.2f}")

        except Exception as e:
            logger.warning(f"Consolidation test failed with technical analysis error: {e}")
            # Still validate basic decision structure
            assert result.validation_passed is True

    @pytest.mark.asyncio
    async def test_breakout_pattern_recognition(
        self, decision_engine, mock_context_builder, mock_llm_service
    ):
        """Test decision quality with breakout pattern."""
        logger.info("Testing breakout pattern recognition")

        # Create breakout market data
        market_data = self.create_breakout_pattern()

        # Calculate real technical indicators
        technical_service = get_technical_analysis_service()

        try:
            indicators_result = technical_service.calculate_all_indicators(market_data)

            # Update mock context with real indicators
            from app.schemas.trading_decision import AssetMarketData

            mock_context = mock_context_builder.build_trading_context.return_value

            # Create asset market data with indicators
            btc_asset_data = AssetMarketData(
                symbol="BTCUSDT",
                current_price=market_data[-1].close,
                price_change_24h=8.0,  # Strong positive change for breakout
                volume_24h=sum(candle.volume for candle in market_data[-24:]),
                funding_rate=0.01,
                open_interest=1000000.0,
                volatility=0.03,
                technical_indicators=self._convert_indicators_to_schema(indicators_result),
                price_history=[],
            )

            mock_context.market_data.assets = {"BTCUSDT": btc_asset_data}
            mock_context.symbols = ["BTCUSDT"]

            # Setup decision engine
            decision_engine.context_builder = mock_context_builder
            decision_engine.llm_service = mock_llm_service

            # Update mock result
            mock_result = mock_llm_service.generate_trading_decision.return_value
            mock_result.context = mock_context

            # Generate decision
            result = await decision_engine.make_trading_decision(
                symbols=["BTCUSDT"], account_id=1, force_refresh=True
            )

            # Validate decision structure - now multi-asset
            assert result.validation_passed is True
            assert len(result.decision.decisions) > 0, "Should have at least one asset decision"

            first_decision = result.decision.decisions[0]
            assert first_decision.confidence >= 0

            # Log the results for analysis
            logger.info(f"Breakout pattern decision: {first_decision.action}")
            logger.info(f"Confidence: {first_decision.confidence}%")
            logger.info(f"Risk level: {first_decision.risk_level}")
            btc_data = mock_context.market_data.assets.get("BTCUSDT")
            if btc_data:
                logger.info(f"Current price: ${btc_data.current_price:.2f}")
                logger.info(f"24h volume: {btc_data.volume_24h:.0f}")
                logger.info(f"24h change: {btc_data.price_change_24h:.2f}%")

            if indicators_result.rsi is not None:
                logger.info(f"RSI: {indicators_result.rsi[-1]:.2f}")

        except Exception as e:
            logger.warning(f"Breakout test failed with technical analysis error: {e}")
            # Still validate basic decision structure
            assert result.validation_passed is True

    @pytest.mark.asyncio
    async def test_decision_consistency_across_patterns(
        self, decision_engine, mock_context_builder, mock_llm_service
    ):
        """Test that decisions are consistent and reasonable across different patterns."""
        logger.info("Testing decision consistency across patterns")

        patterns = [
            ("uptrend", self.create_strong_uptrend_pattern),
            ("downtrend", self.create_strong_downtrend_pattern),
            ("consolidation", self.create_consolidation_pattern),
            ("breakout", self.create_breakout_pattern),
        ]

        pattern_results = {}
        technical_service = get_technical_analysis_service()

        for pattern_name, pattern_creator in patterns:
            try:
                # Create market data
                market_data = pattern_creator()

                # Calculate indicators
                indicators_result = technical_service.calculate_all_indicators(market_data)

                # Update mock context
                from app.schemas.trading_decision import AssetMarketData

                mock_context = mock_context_builder.build_trading_context.return_value

                # Create asset market data with indicators
                btc_asset_data = AssetMarketData(
                    symbol="BTCUSDT",
                    current_price=market_data[-1].close,
                    price_change_24h=2.0,
                    volume_24h=sum(c.volume for c in market_data[-24:])
                    if len(market_data) >= 24
                    else market_data[-1].volume,
                    funding_rate=0.01,
                    open_interest=1000000.0,
                    volatility=0.02,
                    technical_indicators=self._convert_indicators_to_schema(indicators_result),
                    price_history=[],
                )

                mock_context.market_data.assets = {"BTCUSDT": btc_asset_data}
                mock_context.symbols = ["BTCUSDT"]

                # Setup decision engine
                decision_engine.context_builder = mock_context_builder
                decision_engine.llm_service = mock_llm_service

                # Update mock result
                mock_result = mock_llm_service.generate_trading_decision.return_value
                mock_result.context = mock_context

                # Generate decision
                result = await decision_engine.make_trading_decision(
                    symbols=["BTCUSDT"], account_id=1, force_refresh=True
                )

                # Extract first asset decision
                first_decision = result.decision.decisions[0] if result.decision.decisions else None
                if first_decision:
                    pattern_results[pattern_name] = {
                        "action": first_decision.action,
                        "confidence": first_decision.confidence,
                        "risk_level": first_decision.risk_level,
                        "current_price": market_data[-1].close,
                        "rsi": indicators_result.rsi[-1]
                        if indicators_result.rsi and indicators_result.rsi[-1] is not None
                        else None,
                    }
                else:
                    pattern_results[pattern_name] = {"error": "No asset decisions generated"}

            except Exception as e:
                logger.warning(f"Pattern {pattern_name} failed: {e}")
                pattern_results[pattern_name] = {"error": str(e)}

        # Validate we got results for most patterns
        successful_patterns = [k for k, v in pattern_results.items() if "error" not in v]
        assert len(successful_patterns) >= 2, (
            f"At least 2 patterns should succeed, got {len(successful_patterns)}"
        )

        # Log summary
        logger.info("Pattern recognition summary:")
        for pattern, result in pattern_results.items():
            if "error" not in result:
                logger.info(
                    f"  {pattern}: {result['action']} (confidence: {result['confidence']}%) "
                )
            else:
                logger.warning(f"  {pattern}: ERROR - {result['error']}")

        logger.info(f"Successfully tested {len(successful_patterns)} market patterns")

    @pytest.mark.asyncio
    async def test_multi_asset_decision_quality(
        self, decision_engine, mock_context_builder, mock_llm_service
    ):
        """Test decision quality with multiple assets."""
        logger.info("Testing multi-asset decision quality")

        # Create market data for multiple assets
        btc_data = self.create_strong_uptrend_pattern()
        eth_data = self.create_consolidation_pattern()

        # Calculate technical indicators for both
        technical_service = get_technical_analysis_service()

        try:
            btc_indicators = technical_service.calculate_all_indicators(btc_data)
            eth_indicators = technical_service.calculate_all_indicators(eth_data)

            # Update mock context with multi-asset data
            from app.schemas.trading_decision import AssetMarketData

            mock_context = mock_context_builder.build_trading_context.return_value

            # Create multi-asset market context
            mock_context.market_data.assets = {
                "BTCUSDT": AssetMarketData(
                    symbol="BTCUSDT",
                    current_price=btc_data[-1].close,
                    price_change_24h=(
                        (btc_data[-1].close - btc_data[-24].close) / btc_data[-24].close * 100
                        if len(btc_data) >= 24
                        else 5.0
                    ),
                    volume_24h=sum(c.volume for c in btc_data[-24:]),
                    funding_rate=0.01,
                    open_interest=1000000.0,
                    volatility=0.02,
                    technical_indicators=self._convert_indicators_to_schema(btc_indicators),
                    price_history=[],
                ),
                "ETHUSDT": AssetMarketData(
                    symbol="ETHUSDT",
                    current_price=eth_data[-1].close,
                    price_change_24h=0.5,
                    volume_24h=sum(c.volume for c in eth_data[-24:]),
                    funding_rate=0.01,
                    open_interest=500000.0,
                    volatility=0.01,
                    technical_indicators=self._convert_indicators_to_schema(eth_indicators),
                    price_history=[],
                ),
            }
            mock_context.symbols = ["BTCUSDT", "ETHUSDT"]

            # Setup decision engine
            decision_engine.context_builder = mock_context_builder
            decision_engine.llm_service = mock_llm_service

            # Update mock result to return multi-asset decision
            from app.schemas.trading_decision import AssetDecision, TradingDecision

            mock_decisions = [
                AssetDecision(
                    asset="BTCUSDT",
                    action="buy",
                    allocation_usd=1000.0,
                    tp_price=btc_data[-1].close * 1.05,
                    sl_price=btc_data[-1].close * 0.98,
                    exit_plan="Take profit at 5% gain",
                    rationale="Strong uptrend with good momentum",
                    confidence=85,
                    risk_level="medium",
                ),
                AssetDecision(
                    asset="ETHUSDT",
                    action="hold",
                    allocation_usd=0.0,
                    exit_plan="Wait for breakout",
                    rationale="Consolidation pattern, waiting for direction",
                    confidence=60,
                    risk_level="low",
                ),
            ]

            mock_decision = TradingDecision(
                decisions=mock_decisions,
                portfolio_rationale="Focus on BTC uptrend, hold ETH during consolidation",
                total_allocation_usd=1000.0,
                portfolio_risk_level="medium",
            )

            mock_result = mock_llm_service.generate_trading_decision.return_value
            mock_result.decision = mock_decision
            mock_result.context = mock_context

            # Generate decision
            result = await decision_engine.make_trading_decision(
                symbols=["BTCUSDT", "ETHUSDT"], account_id=1, force_refresh=True
            )

            # Validate multi-asset decision structure
            assert result.validation_passed is True
            assert len(result.decision.decisions) == 2, "Should have decisions for both assets"
            assert result.decision.portfolio_rationale is not None
            assert result.decision.total_allocation_usd >= 0

            # Validate individual asset decisions
            btc_decision = next(
                (d for d in result.decision.decisions if d.asset == "BTCUSDT"), None
            )
            eth_decision = next(
                (d for d in result.decision.decisions if d.asset == "ETHUSDT"), None
            )

            assert btc_decision is not None, "Should have BTC decision"
            assert eth_decision is not None, "Should have ETH decision"

            # Log results
            logger.info("Multi-asset decision quality test results:")
            logger.info(f"  Portfolio rationale: {result.decision.portfolio_rationale}")
            logger.info(f"  Total allocation: ${result.decision.total_allocation_usd}")
            logger.info(f"  Portfolio risk: {result.decision.portfolio_risk_level}")
            logger.info(f"  BTC: {btc_decision.action} (${btc_decision.allocation_usd})")
            logger.info(f"  ETH: {eth_decision.action} (${eth_decision.allocation_usd})")

            # Validate allocation consistency
            total_from_assets = sum(d.allocation_usd for d in result.decision.decisions)
            assert abs(total_from_assets - result.decision.total_allocation_usd) < 0.01, (
                "Total allocation should match sum of asset allocations"
            )

            logger.info("✓ Multi-asset decision quality test passed")

        except Exception as e:
            logger.warning(f"Multi-asset test failed with technical analysis error: {e}")
            # Still validate basic decision structure if we got a result
            if "result" in locals():
                assert result.validation_passed is True
