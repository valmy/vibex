"""
E2E tests for Decision Engine HTTP API endpoints.

Tests the complete HTTP API workflow for decision generation including:
- POST /api/v1/decisions/generate
- Request validation
- Response structure
- Error handling
- Integration with real services
"""

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.schemas.trading_decision import (
    DecisionResult,
    TradingDecision,
    TradingContext,
    MarketContext,
    AccountContext,
    TechnicalIndicators,
    PerformanceMetrics,
    RiskMetrics,
    StrategyRiskParameters,
    TradingStrategy,
)


class TestDecisionGenerateAPIE2E:
    """E2E tests for /api/v1/decisions/generate endpoint."""

    @pytest.fixture
    async def async_client(self):
        """Create async HTTP client for testing."""
        # Bypass AdminOnlyMiddleware for testing by mocking the dispatch method
        from app.middleware import AdminOnlyMiddleware

        async def mock_dispatch(self, request, call_next):
            """Mock dispatch that bypasses authentication."""
            return await call_next(request)

        # Temporarily replace the dispatch method
        original_dispatch = AdminOnlyMiddleware.dispatch
        AdminOnlyMiddleware.dispatch = mock_dispatch

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                yield client
        finally:
            # Restore original dispatch
            AdminOnlyMiddleware.dispatch = original_dispatch

    @pytest.fixture
    def mock_decision_result(self):
        """Create a mock decision result for testing."""
        # Create technical indicators
        indicators = TechnicalIndicators(
            ema_20=101000.0,
            ema_50=100000.0,
            rsi=65.0,
            macd=150.0,
            macd_signal=120.0,
            bb_upper=102000.0,
            bb_lower=100000.0,
            bb_middle=101000.0,
            atr=500.0,
        )

        # Create market context
        market_context = MarketContext(
            current_price=101465.3,
            price_change_24h=1465.3,
            volume_24h=1000000.0,
            funding_rate=0.0001,
            open_interest=50000000.0,
            volatility=1.5,
            technical_indicators=indicators,
            price_history=[],
        )

        # Create strategy
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
            prompt_template="Conservative trading prompt",
            risk_parameters=risk_params,
            timeframe_preference=["5m", "4h"],
            max_positions=3,
            is_active=True,
        )

        # Create performance metrics
        performance = PerformanceMetrics(
            total_pnl=1000.0,
            win_rate=60.0,
            avg_win=150.0,
            avg_loss=-75.0,
            max_drawdown=-200.0,
            sharpe_ratio=1.5,
        )

        # Create account context
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

        # Create risk metrics
        risk_metrics = RiskMetrics(
            var_95=500.0,
            max_drawdown=1000.0,
            correlation_risk=15.0,
            concentration_risk=25.0,
        )

        # Create trading context
        context = TradingContext(
            symbol="BTCUSDT",
            account_id=1,
            market_data=market_context,
            account_state=account_context,
            risk_metrics=risk_metrics,
        )

        # Create trading decision
        decision = TradingDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=1000.0,
            tp_price=103000.0,
            sl_price=100000.0,
            exit_plan="Take profit at resistance level of 103000, stop loss at 100000",
            rationale="Strong bullish momentum with RSI at 65, MACD crossover, and price above EMA20",
            confidence=85.0,
            risk_level="medium",
            position_adjustment=None,
            order_adjustment=None,
        )

        # Create decision result
        return DecisionResult(
            decision=decision,
            context=context,
            validation_passed=True,
            validation_errors=[],
            processing_time_ms=250.0,
            model_used="x-ai/grok-4",
            api_cost=0.05,
        )

    @pytest.mark.asyncio
    async def test_generate_decision_success(self, async_client, mock_decision_result):
        """Test successful decision generation via HTTP API."""
        # Mock the decision engine
        with patch("app.api.routes.decision_engine.get_decision_engine") as mock_get_engine:
            mock_engine = AsyncMock()
            mock_engine.make_trading_decision.return_value = mock_decision_result
            mock_get_engine.return_value = mock_engine

            # Make request
            response = await async_client.post(
                "/api/v1/decisions/generate",
                json={
                    "symbol": "BTCUSDT",
                    "account_id": 1,
                    "force_refresh": False,
                },
            )

            # Verify response
            assert response.status_code == 200
            data = response.json()

            # Verify decision structure
            assert "decision" in data
            assert data["decision"]["asset"] == "BTCUSDT"
            assert data["decision"]["action"] == "buy"
            assert data["decision"]["allocation_usd"] == 1000.0
            assert data["decision"]["confidence"] == 85.0
            assert data["decision"]["risk_level"] == "medium"

            # Verify context
            assert "context" in data
            assert data["context"]["symbol"] == "BTCUSDT"
            assert data["context"]["account_id"] == 1

            # Verify metadata
            assert data["validation_passed"] is True
            assert data["model_used"] == "x-ai/grok-4"
            assert data["processing_time_ms"] == 250.0

            # Verify the engine was called correctly
            mock_engine.make_trading_decision.assert_called_once_with(
                symbol="BTCUSDT",
                account_id=1,
                strategy_override=None,
                force_refresh=False,
                ab_test_name=None,
            )

    @pytest.mark.asyncio
    async def test_generate_decision_with_strategy_override(self, async_client, mock_decision_result):
        """Test decision generation with strategy override."""
        with patch("app.api.routes.decision_engine.get_decision_engine") as mock_get_engine:
            mock_engine = AsyncMock()
            mock_engine.make_trading_decision.return_value = mock_decision_result
            mock_get_engine.return_value = mock_engine

            # Make request with strategy override
            response = await async_client.post(
                "/api/v1/decisions/generate",
                json={
                    "symbol": "ETHUSDT",
                    "account_id": 2,
                    "strategy_override": "aggressive",
                    "force_refresh": True,
                    "ab_test_name": "test_experiment",
                },
            )

            # Verify response
            assert response.status_code == 200

            # Verify the engine was called with correct parameters
            mock_engine.make_trading_decision.assert_called_once_with(
                symbol="ETHUSDT",
                account_id=2,
                strategy_override="aggressive",
                force_refresh=True,
                ab_test_name="test_experiment",
            )

    @pytest.mark.asyncio
    async def test_generate_decision_validation_error(self, async_client):
        """Test decision generation with invalid request data."""
        # Missing required field 'symbol'
        response = await async_client.post(
            "/api/v1/decisions/generate",
            json={
                "account_id": 1,
            },
        )

        # Should return 422 Unprocessable Entity for validation error
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_generate_decision_rate_limit_error(self, async_client):
        """Test decision generation with rate limit exceeded."""
        from app.services.llm.decision_engine import RateLimitExceededError

        with patch("app.api.routes.decision_engine.get_decision_engine") as mock_get_engine:
            mock_engine = AsyncMock()
            mock_engine.make_trading_decision.side_effect = RateLimitExceededError(
                "Rate limit exceeded: 60 requests per minute"
            )
            mock_get_engine.return_value = mock_engine

            # Make request
            response = await async_client.post(
                "/api/v1/decisions/generate",
                json={
                    "symbol": "BTCUSDT",
                    "account_id": 1,
                },
            )

            # Should return 429 Too Many Requests
            assert response.status_code == 429
            data = response.json()
            assert "detail" in data
            assert "Rate limit exceeded" in data["detail"]

    @pytest.mark.asyncio
    async def test_generate_decision_engine_error(self, async_client):
        """Test decision generation with decision engine error."""
        from app.services.llm.decision_engine import DecisionEngineError

        with patch("app.api.routes.decision_engine.get_decision_engine") as mock_get_engine:
            mock_engine = AsyncMock()
            mock_engine.make_trading_decision.side_effect = DecisionEngineError(
                "Failed to build trading context"
            )
            mock_get_engine.return_value = mock_engine

            # Make request
            response = await async_client.post(
                "/api/v1/decisions/generate",
                json={
                    "symbol": "BTCUSDT",
                    "account_id": 1,
                },
            )

            # Should return 400 Bad Request
            assert response.status_code == 400
            data = response.json()
            assert "detail" in data
            assert "Failed to build trading context" in data["detail"]

    @pytest.mark.asyncio
    async def test_generate_decision_internal_error(self, async_client):
        """Test decision generation with unexpected internal error."""
        with patch("app.api.routes.decision_engine.get_decision_engine") as mock_get_engine:
            mock_engine = AsyncMock()
            mock_engine.make_trading_decision.side_effect = Exception("Unexpected error")
            mock_get_engine.return_value = mock_engine

            # Make request
            response = await async_client.post(
                "/api/v1/decisions/generate",
                json={
                    "symbol": "BTCUSDT",
                    "account_id": 1,
                },
            )

            # Should return 500 Internal Server Error
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert "Internal server error" in data["detail"]

    @pytest.mark.asyncio
    async def test_generate_decision_multiple_symbols(self, async_client, mock_decision_result):
        """Test decision generation for multiple symbols."""
        with patch("app.api.routes.decision_engine.get_decision_engine") as mock_get_engine:
            mock_engine = AsyncMock()
            mock_engine.make_trading_decision.return_value = mock_decision_result
            mock_get_engine.return_value = mock_engine

            # Test different symbols
            symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
            for symbol in symbols:
                response = await async_client.post(
                    "/api/v1/decisions/generate",
                    json={
                        "symbol": symbol,
                        "account_id": 1,
                    },
                )

                assert response.status_code == 200
                data = response.json()
                assert "decision" in data
                assert data["validation_passed"] is True

    @pytest.mark.asyncio
    async def test_generate_decision_response_structure(self, async_client, mock_decision_result):
        """Test that response has correct structure and all required fields."""
        with patch("app.api.routes.decision_engine.get_decision_engine") as mock_get_engine:
            mock_engine = AsyncMock()
            mock_engine.make_trading_decision.return_value = mock_decision_result
            mock_get_engine.return_value = mock_engine

            response = await async_client.post(
                "/api/v1/decisions/generate",
                json={
                    "symbol": "BTCUSDT",
                    "account_id": 1,
                },
            )

            assert response.status_code == 200
            data = response.json()

            # Verify top-level structure
            assert "decision" in data
            assert "context" in data
            assert "validation_passed" in data
            assert "validation_errors" in data
            assert "processing_time_ms" in data
            assert "model_used" in data

            # Verify decision structure
            decision = data["decision"]
            assert "asset" in decision
            assert "action" in decision
            assert "allocation_usd" in decision
            assert "confidence" in decision
            assert "risk_level" in decision
            assert "rationale" in decision
            assert "exit_plan" in decision

            # Verify context structure
            context = data["context"]
            assert "symbol" in context
            assert "account_id" in context
            assert "market_data" in context
            assert "account_state" in context
            assert "risk_metrics" in context

    @pytest.mark.asyncio
    async def test_generate_decision_invalid_symbol_format(self, async_client):
        """Test decision generation with invalid symbol format."""
        with patch("app.api.routes.decision_engine.get_decision_engine") as mock_get_engine:
            from app.services.llm.decision_engine import DecisionEngineError

            mock_engine = AsyncMock()
            mock_engine.make_trading_decision.side_effect = DecisionEngineError(
                "Invalid symbol format"
            )
            mock_get_engine.return_value = mock_engine

            response = await async_client.post(
                "/api/v1/decisions/generate",
                json={
                    "symbol": "",  # Empty symbol
                    "account_id": 1,
                },
            )

            # Should return 400 for decision engine error
            assert response.status_code == 400
            data = response.json()
            assert "detail" in data

    @pytest.mark.asyncio
    async def test_generate_decision_invalid_account_id(self, async_client):
        """Test decision generation with invalid account ID."""
        with patch("app.api.routes.decision_engine.get_decision_engine") as mock_get_engine:
            from app.services.llm.decision_engine import DecisionEngineError

            mock_engine = AsyncMock()
            mock_engine.make_trading_decision.side_effect = DecisionEngineError(
                "Invalid account ID"
            )
            mock_get_engine.return_value = mock_engine

            response = await async_client.post(
                "/api/v1/decisions/generate",
                json={
                    "symbol": "BTCUSDT",
                    "account_id": -1,  # Invalid negative account ID
                },
            )

            # Should return 400 for decision engine error
            assert response.status_code == 400
            data = response.json()
            assert "detail" in data

