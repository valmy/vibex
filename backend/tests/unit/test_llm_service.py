"""
Unit tests for LLM Service.

Tests LLM API integration, decision generation, model switching,
error handling, and A/B testing functionality.
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.schemas.trading_decision import (
    AccountContext,
    DecisionResult,
    MarketContext,
    PerformanceMetrics,
    RiskMetrics,
    StrategyRiskParameters,
    TechnicalIndicators,
    TechnicalIndicatorsSet,
    TradingContext,
    TradingDecision,
    TradingStrategy,
)
from app.services.llm.llm_exceptions import LLMAPIError, ModelSwitchError, ValidationError
from app.services.llm.llm_service import LLMService, get_llm_service


class TestLLMService:
    """Test cases for LLMService."""

    @pytest.fixture
    def llm_service(self):
        """Create a fresh LLMService instance for each test."""
        return LLMService()

    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 150

        mock_client.chat.completions.create.return_value = mock_response
        return mock_client

    @pytest.fixture
    def sample_market_data(self):
        """Create sample market data for testing."""
        return {
            "symbol": "BTCUSDT",
            "close": 48000.0,
            "high": 49000.0,
            "low": 47000.0,
            "volume": 1000000.0,
            "open": 47500.0,
            "change_percent": 2.5,
            "rsi": 65.0,
            "macd": 100.0,
        }

    @pytest.fixture
    def sample_trading_context(self):
        """Create a sample multi-asset trading context."""
        from app.schemas.trading_decision import AssetMarketData

        indicators = TechnicalIndicators(
            interval=TechnicalIndicatorsSet(
                ema_20=[48000.0],
                ema_50=[47000.0],
                rsi=[65.0],
                macd=[100.0],
                macd_signal=[95.0],
                bb_upper=[49000.0],
                bb_lower=[46000.0],
                bb_middle=[47500.0],
                atr=[500.0],
            ),
            long_interval=TechnicalIndicatorsSet(
                ema_20=[48500.0],
                ema_50=[47500.0],
                rsi=[60.0],
                macd=[150.0],
                macd_signal=[145.0],
                bb_upper=[49500.0],
                bb_lower=[46500.0],
                bb_middle=[48000.0],
                atr=[550.0],
            ),
        )

        # Create AssetMarketData for BTCUSDT
        btc_asset_data = AssetMarketData(
            symbol="BTCUSDT",
            current_price=48000.0,
            price_change_24h=1000.0,
            volume_24h=1000000.0,
            funding_rate=0.01,
            open_interest=50000000.0,
            volatility=0.02,
            technical_indicators=indicators,
            price_history=[],
        )

        # Create multi-asset MarketContext
        market_context = MarketContext(
            assets={"BTCUSDT": btc_asset_data},
            market_sentiment="bullish",
            timestamp=datetime.now(timezone.utc),
        )

        risk_params = StrategyRiskParameters(
            max_risk_per_trade=2.0,
            max_daily_loss=5.0,
            stop_loss_percentage=3.0,
            take_profit_ratio=2.0,
            max_leverage=3.0,
            cooldown_period=300,
        )

        strategy = TradingStrategy(
            strategy_id="conservative",
            strategy_name="Conservative Trading",
            strategy_type="conservative",
            prompt_template="Conservative trading prompt: {symbol} at ${current_price:.2f}",
            risk_parameters=risk_params,
            timeframe_preference=["4h", "1d"],
            max_positions=3,
            is_active=True,
        )

        performance = PerformanceMetrics(
            total_pnl=1000.0,
            win_rate=60.0,
            avg_win=150.0,
            avg_loss=-75.0,
            max_drawdown=-200.0,
            sharpe_ratio=1.5,
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
            open_positions=[],
        )

        risk_metrics = RiskMetrics(
            var_95=500.0, max_drawdown=1000.0, correlation_risk=15.0, concentration_risk=25.0
        )

        return TradingContext(
            symbols=["BTCUSDT"],
            account_id=1,
            timeframes=["4h", "1d"],
            market_data=market_context,
            account_state=account_context,
            recent_trades={"BTCUSDT": []},
            risk_metrics=risk_metrics,
            timestamp=datetime.now(timezone.utc),
        )

    def test_service_initialization(self, llm_service):
        """Test LLMService initialization."""
        assert llm_service.model is not None
        assert llm_service.api_key is not None
        assert llm_service.base_url is not None
        assert llm_service.max_retries == 3
        assert llm_service.base_delay == 1.0
        assert len(llm_service.supported_models) > 0
        assert "gpt-4" in llm_service.supported_models
        assert "grok-beta" in llm_service.supported_models

    def test_get_llm_service_singleton(self):
        """Test that get_llm_service returns singleton instance."""
        service1 = get_llm_service()
        service2 = get_llm_service()
        assert service1 is service2
        assert isinstance(service1, LLMService)

    @pytest.mark.asyncio
    async def test_analyze_market_success(
        self, llm_service, mock_openai_client, sample_market_data
    ):
        """Test successful market analysis."""
        llm_service._client = mock_openai_client
        result = await llm_service.analyze_market("BTCUSDT", sample_market_data)

        assert result["symbol"] == "BTCUSDT"
        assert "timestamp" in result
        assert "analysis" in result
        assert result["model"] == llm_service.model
        assert "usage" in result
        assert result["usage"]["total_tokens"] == 150

        # Verify API call was made correctly
        mock_openai_client.chat.completions.create.assert_called_once()
        call_args = mock_openai_client.chat.completions.create.call_args
        assert call_args[1]["model"] == llm_service.model
        assert len(call_args[1]["messages"]) == 2
        assert "BTCUSDT" in call_args[1]["messages"][1]["content"]

    @pytest.mark.asyncio
    async def test_analyze_market_with_additional_context(
        self, llm_service, mock_openai_client, sample_market_data
    ):
        """Test market analysis with additional context."""
        additional_context = "Market showing strong bullish momentum"

        llm_service._client = mock_openai_client
        result = await llm_service.analyze_market("BTCUSDT", sample_market_data, additional_context)

        assert result["symbol"] == "BTCUSDT"

        # Verify additional context was included in prompt
        call_args = mock_openai_client.chat.completions.create.call_args
        prompt = call_args[1]["messages"][1]["content"]
        assert additional_context in prompt

    @pytest.mark.asyncio
    async def test_get_trading_signal_json_response(
        self, llm_service, mock_openai_client, sample_market_data
    ):
        """Test trading signal generation with JSON response."""
        json_response = '{"signal": "BUY", "confidence": 85, "reason": "Strong bullish momentum"}'
        mock_openai_client.chat.completions.create.return_value.choices[
            0
        ].message.content = json_response

        llm_service._client = mock_openai_client
        result = await llm_service.get_trading_signal("BTCUSDT", sample_market_data)

        assert result["symbol"] == "BTCUSDT"
        assert result["signal"] == "BUY"
        assert result["confidence"] == 85
        assert result["reason"] == "Strong bullish momentum"
        assert result["model"] == llm_service.model

    @pytest.mark.asyncio
    async def test_get_trading_signal_text_response(
        self, llm_service, mock_openai_client, sample_market_data
    ):
        """Test trading signal generation with non-JSON response."""
        text_response = "I recommend buying BTC due to strong momentum"
        mock_openai_client.chat.completions.create.return_value.choices[
            0
        ].message.content = text_response

        llm_service._client = mock_openai_client
        result = await llm_service.get_trading_signal("BTCUSDT", sample_market_data)

        assert result["symbol"] == "BTCUSDT"
        assert result["signal"] == "HOLD"  # Default when JSON parsing fails
        assert result["confidence"] == 50  # Default confidence
        assert result["reason"] == text_response

    @pytest.mark.asyncio
    async def test_summarize_market_conditions(self, llm_service, mock_openai_client):
        """Test market conditions summary."""
        market_data_list = [
            {"symbol": "BTCUSDT", "close": 48000.0, "change_percent": 2.5},
            {"symbol": "ETHUSDT", "close": 3000.0, "change_percent": -1.2},
            {"symbol": "SOLUSDT", "close": 100.0, "change_percent": 5.0},
        ]

        llm_service._client = mock_openai_client
        result = await llm_service.summarize_market_conditions(market_data_list)

        assert "timestamp" in result
        assert "summary" in result
        assert result["symbols_analyzed"] == 3
        assert result["model"] == llm_service.model

        # Verify all symbols were included in prompt
        call_args = mock_openai_client.chat.completions.create.call_args
        prompt = call_args[1]["messages"][1]["content"]
        assert "BTCUSDT" in prompt
        assert "ETHUSDT" in prompt
        assert "SOLUSDT" in prompt

    @pytest.mark.asyncio
    async def test_generate_trading_decision_success(
        self, llm_service, mock_openai_client, sample_trading_context
    ):
        """Test successful multi-asset trading decision generation."""
        # Multi-asset decision JSON structure
        decision_json = {
            "decisions": [
                {
                    "asset": "BTCUSDT",
                    "action": "buy",
                    "allocation_usd": 1000.0,
                    "tp_price": 50000.0,
                    "sl_price": 46000.0,
                    "exit_plan": "Take profit at resistance",
                    "rationale": "Strong bullish momentum with good risk/reward",
                    "confidence": 85,
                    "risk_level": "medium",
                }
            ],
            "portfolio_rationale": "Overall bullish market conditions favor long positions",
            "total_allocation_usd": 1000.0,
            "portfolio_risk_level": "medium",
        }

        mock_openai_client.chat.completions.create.return_value.choices[
            0
        ].message.content = json.dumps(decision_json)

        llm_service._client = mock_openai_client
        with patch.object(llm_service.metrics_tracker, "record_api_call"):
            # Updated to pass list of symbols
            result = await llm_service.generate_trading_decision(
                ["BTCUSDT"], sample_trading_context
            )

            assert isinstance(result, DecisionResult)
            assert result.validation_passed is True
            assert len(result.validation_errors) == 0
            assert result.processing_time_ms > 0
            assert result.model_used == llm_service.model

            decision = result.decision
            # Now decision is a TradingDecision with decisions list
            assert len(decision.decisions) == 1
            assert decision.decisions[0].asset == "BTCUSDT"
            assert decision.decisions[0].action == "buy"
            assert decision.decisions[0].allocation_usd == 1000.0
            assert decision.decisions[0].confidence == 85
            assert decision.portfolio_rationale is not None
            assert decision.total_allocation_usd == 1000.0

    @pytest.mark.asyncio
    async def test_generate_trading_decision_insufficient_context(
        self, llm_service, sample_trading_context
    ):
        """Test multi-asset decision generation with insufficient context."""
        # Make context insufficient - remove asset data
        sample_trading_context.market_data.assets = {}

        result = await llm_service.generate_trading_decision(["BTCUSDT"], sample_trading_context)

        assert isinstance(result, DecisionResult)
        assert result.validation_passed is False
        assert len(result.validation_errors) > 0
        assert "Insufficient context" in result.validation_errors[0]

        # Should return fallback decision with hold actions
        assert len(result.decision.decisions) > 0
        assert result.decision.decisions[0].action == "hold"
        assert result.decision.decisions[0].allocation_usd == 0.0

    @pytest.mark.asyncio
    async def test_generate_trading_decision_api_failure(
        self, llm_service, mock_openai_client, sample_trading_context
    ):
        """Test multi-asset decision generation with API failure."""
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")

        llm_service._client = mock_openai_client
        with patch.object(llm_service.metrics_tracker, "record_api_call"):
            result = await llm_service.generate_trading_decision(
                ["BTCUSDT"], sample_trading_context
            )

            assert isinstance(result, DecisionResult)
            assert result.validation_passed is False
            assert len(result.validation_errors) > 0

            # Should return fallback decision with hold actions
            assert len(result.decision.decisions) > 0
            assert result.decision.decisions[0].action == "hold"
            assert result.decision.decisions[0].confidence == 0

    @pytest.mark.asyncio
    async def test_generate_trading_decision_invalid_json(
        self, llm_service, mock_openai_client, sample_trading_context
    ):
        """Test multi-asset decision generation with invalid JSON response."""
        mock_openai_client.chat.completions.create.return_value.choices[
            0
        ].message.content = "Invalid JSON response"

        llm_service._client = mock_openai_client
        with patch.object(llm_service.metrics_tracker, "record_api_call"):
            result = await llm_service.generate_trading_decision(
                ["BTCUSDT"], sample_trading_context
            )

            assert isinstance(result, DecisionResult)
            assert result.validation_passed is False
            assert len(result.validation_errors) > 0

            # Should return fallback decision with hold actions
            assert len(result.decision.decisions) > 0
            assert result.decision.decisions[0].action == "hold"

    @pytest.mark.asyncio
    async def test_switch_model_success(self, llm_service, mock_openai_client):
        """Test successful model switching."""
        original_model = llm_service.model

        # Mock successful connection test
        mock_openai_client.chat.completions.create.return_value.choices[0].message.content = "OK"

        llm_service._client = mock_openai_client
        result = await llm_service.switch_model("gpt-4")

        assert result is True
        assert llm_service.model == llm_service.supported_models["gpt-4"]
        assert llm_service.model != original_model

    @pytest.mark.asyncio
    async def test_switch_model_unsupported(self, llm_service):
        """Test switching to unsupported model."""
        with pytest.raises(ModelSwitchError, match="not supported"):
            await llm_service.switch_model("unsupported-model")

    @pytest.mark.asyncio
    async def test_switch_model_connection_failure(self, llm_service, mock_openai_client):
        """Test model switching with connection failure."""
        original_model = llm_service.model

        # Mock failed connection test
        mock_openai_client.chat.completions.create.side_effect = Exception("Connection failed")

        llm_service._client = mock_openai_client
        with pytest.raises(ModelSwitchError, match="Failed to connect"):
            await llm_service.switch_model("gpt-4")

        # Should revert to original model
        assert llm_service.model == original_model

    @pytest.mark.asyncio
    async def test_validate_api_health(self, llm_service):
        """Test API health validation."""
        with patch.object(llm_service.metrics_tracker, "get_health_status") as mock_health:
            mock_health.return_value = Mock(
                is_healthy=True,
                consecutive_failures=0,
                circuit_breaker_open=False,
                avg_response_time_ms=100.0,
                last_successful_call=datetime.now(timezone.utc),
            )

            health_status = await llm_service.validate_api_health()

            assert health_status.is_healthy is True
            assert health_status.consecutive_failures == 0
            assert health_status.circuit_breaker_open is False

    @pytest.mark.asyncio
    async def test_validate_api_health_with_failures(self, llm_service, mock_openai_client):
        """Test API health validation with consecutive failures."""
        with patch.object(llm_service.metrics_tracker, "get_health_status") as mock_health:
            mock_health.return_value = Mock(
                is_healthy=True,
                consecutive_failures=5,  # High failure count
                circuit_breaker_open=False,
                avg_response_time_ms=100.0,
                last_successful_call=datetime.now(timezone.utc),
            )

            # Mock failed connection test
            mock_openai_client.chat.completions.create.side_effect = Exception("Connection failed")

            llm_service._client = mock_openai_client
            health_status = await llm_service.validate_api_health()

            assert health_status.is_healthy is False

    def test_get_usage_metrics(self, llm_service):
        """Test usage metrics retrieval."""
        mock_metrics = Mock()
        mock_metrics.total_calls = 100
        mock_metrics.successful_calls = 95
        mock_metrics.failed_calls = 5
        mock_metrics.avg_response_time_ms = 250.0
        mock_metrics.total_cost = 10.0
        mock_metrics.error_rate = 5.0

        with patch.object(
            llm_service.metrics_tracker, "get_usage_metrics", return_value=mock_metrics
        ):
            metrics = llm_service.get_usage_metrics(24)

            assert metrics.total_requests == 100
            assert metrics.successful_requests == 95
            assert metrics.failed_requests == 5
            assert metrics.avg_response_time_ms == 250.0

    def test_ab_testing_methods(self, llm_service):
        """Test A/B testing functionality."""
        # Test starting A/B test
        with patch.object(llm_service.ab_test_manager, "start_ab_test", return_value=True):
            result = llm_service.start_ab_test("test1", "gpt-4", "grok-beta", 0.5, 24)
            assert result is True

        # Test getting A/B test model
        with patch.object(
            llm_service.ab_test_manager, "get_model_for_decision", return_value="gpt-4"
        ):
            model = llm_service.get_ab_test_model("test1", 123)
            assert model == "gpt-4"

        # Test ending A/B test
        mock_result = Mock()
        with patch.object(llm_service.ab_test_manager, "end_ab_test", return_value=mock_result):
            result = llm_service.end_ab_test("test1")
            assert result is mock_result

        # Test getting active tests
        mock_tests = {"test1": Mock()}
        with patch.object(llm_service.ab_test_manager, "get_active_tests", return_value=mock_tests):
            tests = llm_service.get_active_ab_tests()
            assert tests == mock_tests

    @pytest.mark.asyncio
    async def test_generate_decision_with_ab_test(
        self, llm_service, mock_openai_client, sample_trading_context
    ):
        """Test multi-asset decision generation with A/B testing."""
        decision_json = {
            "decisions": [
                {
                    "asset": "BTCUSDT",
                    "action": "buy",
                    "allocation_usd": 1000.0,
                    "exit_plan": "Test exit plan",
                    "rationale": "Test rationale",
                    "confidence": 85,
                    "risk_level": "medium",
                }
            ],
            "portfolio_rationale": "Test portfolio rationale",
            "total_allocation_usd": 1000.0,
            "portfolio_risk_level": "medium",
        }

        mock_openai_client.chat.completions.create.return_value.choices[
            0
        ].message.content = json.dumps(decision_json)

        llm_service._client = mock_openai_client
        with patch.object(llm_service, "get_ab_test_model", return_value="gpt-4"):
            with patch.object(llm_service.ab_test_manager, "record_decision_performance"):
                with patch.object(llm_service.metrics_tracker, "record_api_call"):
                    result = await llm_service.generate_trading_decision(
                        ["BTCUSDT"], sample_trading_context, ab_test_name="test1"
                    )

                    assert isinstance(result, DecisionResult)
                    assert result.validation_passed is True

    def test_validate_context(self, llm_service, sample_trading_context):
        """Test multi-asset context validation."""
        # Valid context should pass
        assert llm_service._validate_context(sample_trading_context) is True

        # Invalid balance should fail
        sample_trading_context.account_state.balance_usd = 0
        assert llm_service._validate_context(sample_trading_context) is False

        # Reset balance
        sample_trading_context.account_state.balance_usd = 10000.0

        # Invalid available balance should fail
        sample_trading_context.account_state.available_balance = 0
        assert llm_service._validate_context(sample_trading_context) is False

        # Reset available balance
        sample_trading_context.account_state.available_balance = 8000.0

        # Empty assets should fail
        sample_trading_context.market_data.assets = {}
        assert llm_service._validate_context(sample_trading_context) is False

    def test_build_multi_asset_decision_prompt(self, llm_service, sample_trading_context):
        """Test multi-asset decision prompt building."""
        # Use only symbols that exist in the sample context
        symbols = ["BTCUSDT"]
        prompt = llm_service._build_multi_asset_decision_prompt(symbols, sample_trading_context)

        # Check that prompt contains the symbol
        assert "BTCUSDT" in prompt

        # Check that prompt contains key sections
        assert "MULTI-ASSET PORTFOLIO ANALYSIS" in prompt
        assert "MARKET DATA FOR ALL ASSETS" in prompt
        assert "ACCOUNT INFO" in prompt
        assert "RISK METRICS" in prompt
        assert "STRATEGY PARAMETERS" in prompt

        # Check that prompt contains account info
        assert "Balance:" in prompt
        assert "Available:" in prompt

        # Check that prompt contains portfolio-level instructions
        assert "portfolio" in prompt.lower()

        # Check that prompt mentions the number of assets
        assert "1 perpetual futures" in prompt

    def test_build_multi_asset_decision_prompt_with_strategy_override(
        self, llm_service, sample_trading_context
    ):
        """Test multi-asset decision prompt building with strategy override."""
        symbols = ["BTCUSDT"]
        prompt = llm_service._build_multi_asset_decision_prompt(
            symbols, sample_trading_context, strategy_override="conservative"
        )

        # Check that prompt was generated
        assert len(prompt) > 0
        assert "BTCUSDT" in prompt

    def test_parse_multi_asset_decision_response_valid_json(self, llm_service):
        """Test parsing valid multi-asset JSON decision response."""
        decision_json = {
            "decisions": [
                {
                    "asset": "BTCUSDT",
                    "action": "buy",
                    "allocation_usd": 1000.0,
                    "exit_plan": "Take profit at resistance",
                    "rationale": "Strong momentum",
                    "confidence": 85,
                    "risk_level": "medium",
                }
            ],
            "portfolio_rationale": "Overall bullish market conditions",
            "total_allocation_usd": 1000.0,
            "portfolio_risk_level": "medium",
        }

        response_data = {"content": json.dumps(decision_json)}

        decision = llm_service._parse_multi_asset_decision_response(response_data, ["BTCUSDT"])

        assert isinstance(decision, TradingDecision)
        assert len(decision.decisions) == 1
        assert decision.decisions[0].asset == "BTCUSDT"
        assert decision.decisions[0].action == "buy"
        assert decision.decisions[0].allocation_usd == 1000.0
        assert decision.decisions[0].confidence == 85
        assert decision.portfolio_rationale is not None
        assert decision.total_allocation_usd == 1000.0

    def test_parse_multi_asset_decision_response_invalid_json(self, llm_service):
        """Test parsing invalid JSON decision response."""
        response_data = {"content": "This is not valid JSON"}

        with pytest.raises(ValidationError, match="No valid JSON found"):
            llm_service._parse_multi_asset_decision_response(response_data, ["BTCUSDT"])

    def test_parse_multi_asset_decision_response_missing_decisions(self, llm_service):
        """Test parsing decision response with missing decisions field."""
        decision_json = {
            "portfolio_rationale": "Test rationale",
            "total_allocation_usd": 1000.0,
            "portfolio_risk_level": "medium",
        }

        response_data = {"content": json.dumps(decision_json)}

        # Should raise validation error for missing decisions
        with pytest.raises(ValidationError):
            llm_service._parse_multi_asset_decision_response(response_data, ["BTCUSDT"])

    def test_extract_json_from_text(self, llm_service):
        """Test extracting multi-asset JSON from text response."""
        text_with_json = """
        Here is my analysis:
        {"decisions": [{"asset": "BTCUSDT", "action": "buy", "allocation_usd": 1000.0, "exit_plan": "test", "rationale": "test", "confidence": 85, "risk_level": "medium"}], "portfolio_rationale": "test", "total_allocation_usd": 1000.0, "portfolio_risk_level": "medium"}
        That's my recommendation.
        """

        result = llm_service._extract_json_from_text(text_with_json)

        assert "decisions" in result
        assert len(result["decisions"]) == 1
        assert result["decisions"][0]["asset"] == "BTCUSDT"
        assert result["decisions"][0]["action"] == "buy"
        assert result["decisions"][0]["allocation_usd"] == 1000.0
        assert result["portfolio_rationale"] == "test"

    def test_extract_json_from_text_no_json(self, llm_service):
        """Test extracting JSON from text with no valid JSON."""
        text_without_json = "This text contains no valid JSON at all."

        with pytest.raises(ValidationError, match="No valid JSON found"):
            llm_service._extract_json_from_text(text_without_json)

    def test_create_multi_asset_fallback_decision(self, llm_service):
        """Test creating multi-asset fallback decision."""
        fallback = llm_service._create_multi_asset_fallback_decision(["BTCUSDT", "ETHUSDT"])

        assert isinstance(fallback, TradingDecision)
        assert len(fallback.decisions) == 2
        assert fallback.decisions[0].asset == "BTCUSDT"
        assert fallback.decisions[0].action == "hold"
        assert fallback.decisions[0].allocation_usd == 0.0
        assert fallback.decisions[0].confidence == 0
        assert fallback.decisions[0].risk_level == "low"
        assert "analysis failed" in fallback.decisions[0].rationale.lower()
        assert fallback.decisions[1].asset == "ETHUSDT"
        assert fallback.total_allocation_usd == 0.0
        assert fallback.portfolio_risk_level == "low"

    def test_get_strategy_template(self, llm_service):
        """Test getting strategy templates."""
        conservative_template = llm_service._get_strategy_template("conservative")
        aggressive_template = llm_service._get_strategy_template("aggressive")
        unknown_template = llm_service._get_strategy_template("unknown")

        assert "Conservative Strategy Rules" in conservative_template
        assert "Aggressive Strategy Rules" in aggressive_template
        assert unknown_template == conservative_template  # Should default to conservative

    @pytest.mark.asyncio
    async def test_test_model_connection_success(self, llm_service, mock_openai_client):
        """Test successful model connection test."""
        mock_openai_client.chat.completions.create.return_value.choices[0].message.content = "OK"

        llm_service._client = mock_openai_client
        result = await llm_service._test_model_connection()

        assert result is True

    @pytest.mark.asyncio
    async def test_test_model_connection_failure(self, llm_service, mock_openai_client):
        """Test failed model connection test."""
        mock_openai_client.chat.completions.create.side_effect = Exception("Connection failed")

        llm_service._client = mock_openai_client
        result = await llm_service._test_model_connection()

        assert result is False

    @pytest.mark.asyncio
    async def test_call_llm_for_decision_success(self, llm_service, mock_openai_client):
        """Test successful LLM API call for decision."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_openai_client.chat.completions.create.return_value = mock_response

        llm_service._client = mock_openai_client
        with patch.object(llm_service.metrics_tracker, "record_api_call"):
            with patch.object(llm_service.metrics_tracker, "_calculate_cost", return_value=0.01):
                result = await llm_service._call_llm_for_decision("Test prompt")

                assert result["content"] == "Test response"
                assert result["usage"] == mock_response.usage
                assert result["cost"] == 0.01

    @pytest.mark.asyncio
    async def test_call_llm_for_decision_with_retries(self, llm_service, mock_openai_client):
        """Test LLM API call with retries on failure."""
        # First two calls fail, third succeeds
        mock_openai_client.chat.completions.create.side_effect = [
            Exception("First failure"),
            Exception("Second failure"),
            Mock(
                choices=[Mock(message=Mock(content="Success"))],
                usage=Mock(prompt_tokens=100, completion_tokens=50),
            ),
        ]

        llm_service._client = mock_openai_client
        with patch.object(llm_service.metrics_tracker, "record_api_call"):
            with patch.object(llm_service.metrics_tracker, "_calculate_cost", return_value=0.01):
                result = await llm_service._call_llm_for_decision("Test prompt")

                assert result["content"] == "Success"
                # Should have made 3 attempts
                assert mock_openai_client.chat.completions.create.call_count == 3

    @pytest.mark.asyncio
    async def test_call_llm_for_decision_max_retries_exceeded(
        self, llm_service, mock_openai_client
    ):
        """Test LLM API call when max retries are exceeded."""
        mock_openai_client.chat.completions.create.side_effect = Exception("Persistent failure")

        llm_service._client = mock_openai_client
        with patch.object(llm_service.metrics_tracker, "record_api_call"):
            with pytest.raises(LLMAPIError, match="failed after 3 attempts"):
                await llm_service._call_llm_for_decision("Test prompt")

            # Should have made max_retries attempts
            assert mock_openai_client.chat.completions.create.call_count == llm_service.max_retries

    def test_get_decision_system_prompt(self, llm_service):
        """Test getting decision system prompt."""
        prompt = llm_service._get_decision_system_prompt()

        assert "expert cryptocurrency trading advisor" in prompt.lower()
        assert "JSON format" in prompt
        assert "allocation_usd" in prompt
        assert "confidence" in prompt
        assert "rationale" in prompt

    @pytest.mark.asyncio
    async def test_api_error_handling(self, llm_service, mock_openai_client, sample_market_data):
        """Test API error handling in various methods."""
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")

        llm_service._client = mock_openai_client
        # Test analyze_market error handling
        with pytest.raises(Exception, match="API Error"):
            await llm_service.analyze_market("BTCUSDT", sample_market_data)

        # Test get_trading_signal error handling
        with pytest.raises(Exception, match="API Error"):
            await llm_service.get_trading_signal("BTCUSDT", sample_market_data)

        # Test summarize_market_conditions error handling
        with pytest.raises(Exception, match="API Error"):
            await llm_service.summarize_market_conditions([sample_market_data])

    def test_prompt_building_methods(self, llm_service, sample_market_data):
        """Test various prompt building methods."""
        # Test analysis prompt
        analysis_prompt = llm_service._build_analysis_prompt("BTCUSDT", sample_market_data)
        assert "BTCUSDT" in analysis_prompt
        assert "48000.00" in analysis_prompt
        assert "Current trend analysis" in analysis_prompt

        # Test analysis prompt with additional context
        context = "Strong bullish momentum"
        analysis_prompt_with_context = llm_service._build_analysis_prompt(
            "BTCUSDT", sample_market_data, context
        )
        assert context in analysis_prompt_with_context

        # Test signal prompt
        signal_prompt = llm_service._build_signal_prompt("BTCUSDT", sample_market_data)
        assert "BTCUSDT" in signal_prompt
        assert "JSON format" in signal_prompt
        assert "BUY|SELL|HOLD" in signal_prompt

        # Test signal prompt with account info
        account_info = {"balance": 10000.0}
        signal_prompt_with_account = llm_service._build_signal_prompt(
            "BTCUSDT", sample_market_data, account_info
        )
        assert "10000.00" in signal_prompt_with_account

        # Test summary prompt
        market_data_list = [
            sample_market_data,
            {"symbol": "ETHUSDT", "close": 3000.0, "change_percent": -1.0},
        ]
        summary_prompt = llm_service._build_summary_prompt(market_data_list)
        assert "BTCUSDT" in summary_prompt
        assert "ETHUSDT" in summary_prompt
        assert "Overall market sentiment" in summary_prompt
