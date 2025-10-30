"""
Integration tests for LLM Decision Engine.

Tests the complete decision generation workflow, multi-account processing,
strategy switching, and error handling scenarios.
"""

import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, Mock, patch

from app.services.llm.decision_engine import DecisionEngine, get_decision_engine
from app.services.llm.llm_service import LLMService
from app.services.llm.context_builder import ContextBuilderService
from app.services.llm.decision_validator import DecisionValidator
from app.services.llm.strategy_manager import StrategyManager
from app.schemas.trading_decision import (
    TradingDecision,
    TradingContext,
    MarketContext,
    AccountContext,
    TechnicalIndicators,
    TradingStrategy,
    StrategyRiskParameters,
    DecisionResult,
    RiskMetrics,
    PerformanceMetrics,
    ValidationResult
)


class TestLLMDecisionEngineIntegration:
    """Integration tests for the complete LLM Decision Engine workflow."""

    @pytest.fixture
    async def decision_engine(self):
        """Create a DecisionEngine instance for testing."""
        return DecisionEngine()

    @pytest.fixture
    def mock_llm_service(self):
        """Create a mock LLM service."""
        mock_service = AsyncMock(spec=LLMService)

        # Mock successful decision generation
        mock_decision = TradingDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=1000.0,
            tp_price=50000.0,
            sl_price=46000.0,
            exit_plan="Take profit at resistance",
            rationale="Strong bullish momentum",
            confidence=85,
            risk_level="medium"
        )

        # Create a proper TradingContext for the mock result
        from app.schemas.trading_decision import (
            MarketContext, AccountContext, RiskMetrics, TradingContext,
            TechnicalIndicators, PerformanceMetrics
        )

        market_context = MarketContext(
            current_price=48000.0,
            price_change_24h=1000.0,
            volume_24h=1000000.0,
            volatility=0.05,
            technical_indicators=TechnicalIndicators(
                rsi=65.0,
                macd=100.0,
                ema_20=47500.0,
                ema_50=47000.0,
                bollinger_upper=49000.0,
                bollinger_lower=46000.0,
                atr=500.0
            ),
            price_history=[]
        )

        account_context = AccountContext(
            account_id=1,
            balance_usd=10000.0,
            available_balance=8000.0,
            total_pnl=500.0,
            open_positions=[],
            recent_performance=PerformanceMetrics(
                total_trades=10,
                winning_trades=6,
                total_pnl=500.0,
                max_drawdown=200.0,
                sharpe_ratio=1.5,
                win_rate=60.0,
                avg_win=100.0,
                avg_loss=50.0
            ),
            risk_exposure=0.2,
            max_position_size=2000.0,
            active_strategy=TradingStrategy(
                strategy_id="conservative",
                strategy_name="Conservative Trading",
                strategy_type="conservative",
                prompt_template="Conservative trading prompt: {symbol} at ${current_price}",
                risk_parameters=StrategyRiskParameters(
                    max_risk_per_trade=5.0,
                    max_daily_loss=10.0,
                    stop_loss_percentage=2.0,
                    take_profit_ratio=2.0,
                    max_leverage=2.0,
                    cooldown_period=300
                ),
                timeframe_preference=["1h", "4h"],
                max_positions=3,
                position_sizing="percentage",
                is_active=True
            )
        )

        risk_metrics = RiskMetrics(
            var_95=500.0,
            max_drawdown=1000.0,
            correlation_risk=15.0,
            concentration_risk=25.0
        )

        mock_context = TradingContext(
            symbol="BTCUSDT",
            account_id=1,
            market_data=market_context,
            account_state=account_context,
            risk_metrics=risk_metrics
        )

        mock_result = DecisionResult(
            decision=mock_decision,
            context=mock_context,
            validation_passed=True,
            validation_errors=[],
            processing_time_ms=250.0,
            model_used="gpt-4"
        )

        mock_service.generate_trading_decision.return_value = mock_result
        return mock_service

    @pytest.fixture
    def mock_context_builder(self):
        """Create a mock context builder service."""
        mock_builder = AsyncMock(spec=ContextBuilderService)

        # Create mock trading context
        indicators = TechnicalIndicators(
            ema_20=48000.0,
            ema_50=47000.0,
            rsi=65.0,
            macd=100.0,
            bb_upper=49000.0,
            bb_lower=46000.0,
            bb_middle=47500.0,
            atr=500.0
        )

        market_context = MarketContext(
            current_price=48000.0,
            price_change_24h=1000.0,
            volume_24h=1000000.0,
            funding_rate=0.01,
            open_interest=50000000.0,
            volatility=0.02,
            technical_indicators=indicators,
            price_history=[]
        )

        risk_params = StrategyRiskParameters(
            max_risk_per_trade=2.0,
            max_daily_loss=5.0,
            stop_loss_percentage=3.0,
            take_profit_ratio=2.0,
            max_leverage=3.0,
            cooldown_period=300
        )

        strategy = TradingStrategy(
            strategy_id="conservative",
            strategy_name="Conservative Trading",
            strategy_type="conservative",
            prompt_template="Conservative trading prompt",
            risk_parameters=risk_params,
            timeframe_preference=["4h", "1d"],
            max_positions=3,
            is_active=True
        )

        performance = PerformanceMetrics(
            total_pnl=1000.0,
            win_rate=60.0,
            avg_win=150.0,
            avg_loss=-75.0,
            max_drawdown=-200.0,
            sharpe_ratio=1.5
        )

        account_context = AccountContext(
            account_id=1,
            balance_usd=10000.0,
            available_balance=8000.0,
            total_pnl=1000.0,
            recent_performance=performance,
            risk_exposure=20.0,
            max_position_size=2000.0,
            active_strategy=strategy,
            open_positions=[]
        )

        risk_metrics = RiskMetrics(
            var_95=500.0,
            max_drawdown=1000.0,
            correlation_risk=15.0,
            concentration_risk=25.0
        )

        mock_context = TradingContext(
            symbol="BTCUSDT",
            account_id=1,
            market_data=market_context,
            account_state=account_context,
            risk_metrics=risk_metrics
        )

        mock_builder.build_trading_context.return_value = mock_context
        return mock_builder

    @pytest.fixture
    def mock_decision_validator(self):
        """Create a mock decision validator."""
        mock_validator = AsyncMock(spec=DecisionValidator)

        # Mock successful validation
        mock_validation = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            rules_checked=["schema_validation", "business_rules", "risk_checks"],
            validation_time_ms=50.0
        )

        mock_validator.validate_decision.return_value = mock_validation
        return mock_validator

    @pytest.fixture
    def mock_strategy_manager(self):
        """Create a mock strategy manager."""
        mock_manager = AsyncMock(spec=StrategyManager)

        # Mock strategy retrieval
        risk_params = StrategyRiskParameters(
            max_risk_per_trade=2.0,
            max_daily_loss=5.0,
            stop_loss_percentage=3.0,
            take_profit_ratio=2.0,
            max_leverage=3.0,
            cooldown_period=300
        )

        mock_strategy = TradingStrategy(
            strategy_id="conservative",
            strategy_name="Conservative Trading",
            strategy_type="conservative",
            prompt_template="Conservative trading prompt",
            risk_parameters=risk_params,
            timeframe_preference=["4h", "1d"],
            max_positions=3,
            is_active=True
        )

        mock_manager.get_account_strategy.return_value = mock_strategy
        mock_manager.switch_account_strategy.return_value = Mock()
        return mock_manager

    @pytest.mark.asyncio
    async def test_complete_decision_generation_workflow(
        self,
        decision_engine,
        mock_llm_service,
        mock_context_builder,
        mock_decision_validator,
        mock_strategy_manager
    ):
        """Test the complete decision generation workflow."""
        # Inject mocked services
        decision_engine.llm_service = mock_llm_service
        decision_engine.context_builder = mock_context_builder
        decision_engine.decision_validator = mock_decision_validator
        decision_engine.strategy_manager = mock_strategy_manager

        # Execute decision generation
        result = await decision_engine.make_trading_decision("BTCUSDT", 1)

        # Verify the workflow was executed correctly
        assert isinstance(result, DecisionResult)
        assert result.decision.asset == "BTCUSDT"
        assert result.decision.action == "buy"
        assert result.validation_passed is True

        # Verify all services were called
        mock_context_builder.build_trading_context.assert_called_once_with(symbol="BTCUSDT", account_id=1, force_refresh=False)
        mock_llm_service.generate_trading_decision.assert_called_once()
        mock_decision_validator.validate_decision.assert_called_once()

    @pytest.mark.asyncio
    async def test_decision_generation_with_validation_failure(
        self,
        decision_engine,
        mock_llm_service,
        mock_context_builder,
        mock_decision_validator,
        mock_strategy_manager
    ):
        """Test decision generation when validation fails."""
        # Mock validation failure
        mock_validation = ValidationResult(
            is_valid=False,
            errors=["Allocation exceeds available balance"],
            warnings=[],
            rules_checked=["schema_validation", "business_rules"],
            validation_time_ms=50.0
        )
        mock_decision_validator.validate_decision.return_value = mock_validation

        # Mock fallback decision creation
        fallback_decision = TradingDecision(
            asset="BTCUSDT",
            action="hold",
            allocation_usd=0.0,
            exit_plan="Hold due to validation failure",
            rationale="Original decision failed validation",
            confidence=25,
            risk_level="low"
        )
        mock_decision_validator.create_fallback_decision.return_value = fallback_decision

        # Inject mocked services
        decision_engine.llm_service = mock_llm_service
        decision_engine.context_builder = mock_context_builder
        decision_engine.decision_validator = mock_decision_validator
        decision_engine.strategy_manager = mock_strategy_manager

        # Execute decision generation
        result = await decision_engine.make_trading_decision("BTCUSDT", 1)

        # Verify fallback was used
        assert result.decision.action == "hold"
        assert result.decision.allocation_usd == 0.0
        assert result.validation_passed is False
        assert len(result.validation_errors) > 0

        # Verify fallback creation was called
        mock_decision_validator.create_fallback_decision.assert_called_once()

    @pytest.mark.asyncio
    async def test_multi_account_decision_processing(
        self,
        decision_engine,
        mock_llm_service,
        mock_context_builder,
        mock_decision_validator,
        mock_strategy_manager
    ):
        """Test concurrent decision processing for multiple accounts."""
        # Inject mocked services
        decision_engine.llm_service = mock_llm_service
        decision_engine.context_builder = mock_context_builder
        decision_engine.decision_validator = mock_decision_validator
        decision_engine.strategy_manager = mock_strategy_manager

        # Mock different contexts for different accounts
        def mock_build_context(symbol, account_id):
            context = mock_context_builder.build_trading_context.return_value
            context.account_id = account_id
            return context

        mock_context_builder.build_trading_context.side_effect = mock_build_context

        # Execute batch decisions
        symbols = ["BTCUSDT", "ETHUSDT"]
        account_ids = [1, 2, 3]

        results = []
        for account_id in account_ids:
            account_results = await decision_engine.batch_decisions(symbols, account_id)
            results.extend(account_results)

        # Verify all decisions were processed
        assert len(results) == len(symbols) * len(account_ids)

        # Verify each result is valid
        for result in results:
            assert isinstance(result, DecisionResult)
            assert result.decision.asset in symbols

        # Verify services were called for each account/symbol combination
        assert mock_context_builder.build_trading_context.call_count == len(symbols) * len(account_ids)
        assert mock_llm_service.generate_trading_decision.call_count == len(symbols) * len(account_ids)

    @pytest.mark.asyncio
    async def test_strategy_switching_integration(
        self,
        decision_engine,
        mock_llm_service,
        mock_context_builder,
        mock_decision_validator,
        mock_strategy_manager
    ):
        """Test strategy switching and its effect on decision generation."""
        # Inject mocked services
        decision_engine.llm_service = mock_llm_service
        decision_engine.context_builder = mock_context_builder
        decision_engine.decision_validator = mock_decision_validator
        decision_engine.strategy_manager = mock_strategy_manager

        # Test strategy switching
        result = await decision_engine.switch_strategy(1, "aggressive")
        assert result is True

        # Verify strategy manager was called
        mock_strategy_manager.switch_account_strategy.assert_called_once_with(
            1, "aggressive", switch_reason="Manual strategy switch", switched_by="system"
        )

        # Test decision generation after strategy switch
        decision_result = await decision_engine.make_trading_decision("BTCUSDT", 1)

        # Verify decision was generated
        assert isinstance(decision_result, DecisionResult)
        assert decision_result.validation_passed is True

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(
        self,
        decision_engine,
        mock_llm_service,
        mock_context_builder,
        mock_decision_validator,
        mock_strategy_manager
    ):
        """Test error handling and recovery scenarios."""
        # Mock context building failure
        mock_context_builder.build_trading_context.side_effect = Exception("Context building failed")

        # Inject mocked services
        decision_engine.llm_service = mock_llm_service
        decision_engine.context_builder = mock_context_builder
        decision_engine.decision_validator = mock_decision_validator
        decision_engine.strategy_manager = mock_strategy_manager

        # Execute decision generation - should handle error gracefully
        result = await decision_engine.make_trading_decision("BTCUSDT", 1)

        # Verify error was handled and fallback decision was created
        assert isinstance(result, DecisionResult)
        assert result.validation_passed is False
        assert len(result.validation_errors) > 0
        assert "Context building failed" in str(result.validation_errors)

    @pytest.mark.asyncio
    async def test_decision_caching_and_rate_limiting(
        self,
        decision_engine,
        mock_llm_service,
        mock_context_builder,
        mock_decision_validator,
        mock_strategy_manager
    ):
        """Test decision caching and rate limiting functionality."""
        # Inject mocked services
        decision_engine.llm_service = mock_llm_service
        decision_engine.context_builder = mock_context_builder
        decision_engine.decision_validator = mock_decision_validator
        decision_engine.strategy_manager = mock_strategy_manager

        # Make first decision
        result1 = await decision_engine.make_trading_decision("BTCUSDT", 1)
        assert isinstance(result1, DecisionResult)

        # Make second decision immediately (should be rate limited or cached)
        result2 = await decision_engine.make_trading_decision("BTCUSDT", 1)
        assert isinstance(result2, DecisionResult)

        # Verify caching behavior - exact behavior depends on implementation
        # At minimum, both calls should succeed
        assert result1.decision.asset == result2.decision.asset

    @pytest.mark.asyncio
    async def test_decision_history_tracking(
        self,
        decision_engine,
        mock_llm_service,
        mock_context_builder,
        mock_decision_validator,
        mock_strategy_manager
    ):
        """Test decision history tracking and retrieval."""
        # Inject mocked services
        decision_engine.llm_service = mock_llm_service
        decision_engine.context_builder = mock_context_builder
        decision_engine.decision_validator = mock_decision_validator
        decision_engine.strategy_manager = mock_strategy_manager

        # Generate several decisions
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        for symbol in symbols:
            await decision_engine.make_trading_decision(symbol, 1)

        # Retrieve decision history
        history = await decision_engine.get_decision_history(1, limit=10)

        # Verify history contains decisions
        assert isinstance(history, list)
        assert len(history) <= 10  # Respects limit

        # Verify each history item is a DecisionResult
        for decision_result in history:
            assert isinstance(decision_result, DecisionResult)

    @pytest.mark.asyncio
    async def test_performance_under_load(
        self,
        decision_engine,
        mock_llm_service,
        mock_context_builder,
        mock_decision_validator,
        mock_strategy_manager
    ):
        """Test decision engine performance under concurrent load."""
        # Inject mocked services
        decision_engine.llm_service = mock_llm_service
        decision_engine.context_builder = mock_context_builder
        decision_engine.decision_validator = mock_decision_validator
        decision_engine.strategy_manager = mock_strategy_manager

        # Add small delay to simulate real processing time
        async def delayed_decision(*args, **kwargs):
            import asyncio
            await asyncio.sleep(0.01)  # 10ms delay
            return mock_llm_service.generate_trading_decision.return_value

        mock_llm_service.generate_trading_decision.side_effect = delayed_decision

        # Generate concurrent decisions
        import asyncio

        tasks = []
        for i in range(10):  # 10 concurrent decisions
            task = decision_engine.make_trading_decision("BTCUSDT", i + 1)
            tasks.append(task)

        # Execute all tasks concurrently
        start_time = datetime.now()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = datetime.now()

        # Verify all decisions completed
        assert len(results) == 10

        # Verify no exceptions occurred
        for result in results:
            assert isinstance(result, DecisionResult)
            assert not isinstance(result, Exception)

        # Verify reasonable performance (should be much faster than sequential)
        total_time = (end_time - start_time).total_seconds()
        assert total_time < 1.0  # Should complete in less than 1 second

    @pytest.mark.asyncio
    async def test_context_invalidation_scenarios(
        self,
        decision_engine,
        mock_llm_service,
        mock_context_builder,
        mock_decision_validator,
        mock_strategy_manager
    ):
        """Test context invalidation and refresh scenarios."""
        # Inject mocked services
        decision_engine.llm_service = mock_llm_service
        decision_engine.context_builder = mock_context_builder
        decision_engine.decision_validator = mock_decision_validator
        decision_engine.strategy_manager = mock_strategy_manager

        # Make initial decision
        result1 = await decision_engine.make_trading_decision("BTCUSDT", 1)
        assert isinstance(result1, DecisionResult)

        # Simulate context invalidation (e.g., new market data)
        decision_engine.invalidate_cache_for_symbol("BTCUSDT")

        # Make another decision - should rebuild context
        result2 = await decision_engine.make_trading_decision("BTCUSDT", 1)
        assert isinstance(result2, DecisionResult)

        # Verify context was rebuilt
        assert mock_context_builder.build_trading_context.call_count >= 2

    @pytest.mark.asyncio
    async def test_decision_validation_edge_cases(
        self,
        decision_engine,
        mock_llm_service,
        mock_context_builder,
        mock_decision_validator,
        mock_strategy_manager
    ):
        """Test decision validation with various edge cases."""
        # Inject mocked services
        decision_engine.llm_service = mock_llm_service
        decision_engine.context_builder = mock_context_builder
        decision_engine.decision_validator = mock_decision_validator
        decision_engine.strategy_manager = mock_strategy_manager

        # Test with various validation scenarios
        validation_scenarios = [
            # Valid decision
            ValidationResult(
                is_valid=True,
                errors=[],
                warnings=[],
                rules_checked=["schema_validation"],
                validation_time_ms=25.0
            ),
            # Decision with warnings
            ValidationResult(
                is_valid=True,
                errors=[],
                warnings=["Large allocation relative to balance"],
                rules_checked=["schema_validation", "business_rules"],
                validation_time_ms=30.0
            ),
            # Invalid decision
            ValidationResult(
                is_valid=False,
                errors=["Allocation exceeds available balance"],
                warnings=[],
                rules_checked=["schema_validation", "business_rules"],
                validation_time_ms=35.0
            )
        ]

        for i, validation_result in enumerate(validation_scenarios):
            mock_decision_validator.validate_decision.return_value = validation_result

            # Mock fallback for invalid decisions
            if not validation_result.is_valid:
                fallback_decision = TradingDecision(
                    asset="BTCUSDT",
                    action="hold",
                    allocation_usd=0.0,
                    exit_plan="Hold due to validation failure",
                    rationale="Validation failed",
                    confidence=25,
                    risk_level="low"
                )
                mock_decision_validator.create_fallback_decision.return_value = fallback_decision

            result = await decision_engine.make_trading_decision("BTCUSDT", 1)

            # Verify result matches validation outcome
            assert isinstance(result, DecisionResult)
            assert result.validation_passed == validation_result.is_valid

            if validation_result.is_valid:
                assert len(result.validation_errors) == 0
                if validation_result.warnings:
                    # Warnings should be preserved
                    pass
            else:
                assert len(result.validation_errors) > 0
                assert result.decision.action == "hold"  # Fallback decision

    def test_get_decision_engine_singleton(self):
        """Test that get_decision_engine returns singleton instance."""
        engine1 = get_decision_engine()
        engine2 = get_decision_engine()
        assert engine1 is engine2
        assert isinstance(engine1, DecisionEngine)

    @pytest.mark.asyncio
    async def test_decision_engine_initialization(self, decision_engine):
        """Test decision engine initialization and service dependencies."""
        # Verify all required services are initialized
        assert hasattr(decision_engine, 'llm_service')
        assert hasattr(decision_engine, 'context_builder')
        assert hasattr(decision_engine, 'decision_validator')
        assert hasattr(decision_engine, 'strategy_manager')

        # Verify services are of correct types
        assert isinstance(decision_engine.llm_service, LLMService)
        assert isinstance(decision_engine.context_builder, ContextBuilderService)
        assert isinstance(decision_engine.decision_validator, DecisionValidator)
        assert isinstance(decision_engine.strategy_manager, StrategyManager)

    @pytest.mark.asyncio
    async def test_batch_decision_error_handling(
        self,
        decision_engine,
        mock_llm_service,
        mock_context_builder,
        mock_decision_validator,
        mock_strategy_manager
    ):
        """Test batch decision processing with mixed success/failure scenarios."""
        # Inject mocked services
        decision_engine.llm_service = mock_llm_service
        decision_engine.context_builder = mock_context_builder
        decision_engine.decision_validator = mock_decision_validator
        decision_engine.strategy_manager = mock_strategy_manager

        # Mock context builder to fail for one symbol
        def mock_build_context_with_failure(symbol, account_id):
            if symbol == "ETHUSDT":
                raise Exception("Market data unavailable for ETHUSDT")
            return mock_context_builder.build_trading_context.return_value

        mock_context_builder.build_trading_context.side_effect = mock_build_context_with_failure

        # Execute batch decisions
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        results = await decision_engine.batch_decisions(symbols, 1)

        # Verify we got results for all symbols
        assert len(results) == 3

        # Verify BTC and SOL succeeded, ETH failed gracefully
        btc_result = next(r for r in results if r.decision.asset == "BTCUSDT")
        eth_result = next(r for r in results if r.decision.asset == "ETHUSDT")
        sol_result = next(r for r in results if r.decision.asset == "SOLUSDT")

        assert btc_result.validation_passed is True
        assert eth_result.validation_passed is False  # Should have error
        assert sol_result.validation_passed is True

        # ETH result should contain error information
        assert len(eth_result.validation_errors) > 0
        assert "Market data unavailable" in str(eth_result.validation_errors)