"""
E2E tests for Decision/Generate API with real authentication.

This test suite validates the complete end-to-end flow of the
/api/v1/decisions/generate endpoint including:
- Wallet-based authentication (challenge-response)
- Request validation
- Decision generation
- Response structure
- Error handling
- Integration with real services

Test Plan: docs/E2E_TEST_PLAN_DECISION_API.md

NOTE: These tests require a running database. If database is not available,
tests will be skipped. To run with database:
1. Start PostgreSQL: podman-compose up -d postgres
2. Run tests: uv run pytest tests/e2e/test_decision_generate_api_e2e.py
"""

import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from eth_account import Account
from eth_account.messages import encode_defunct
from unittest.mock import AsyncMock, patch

from app.main import app
from app.db.session import init_db, close_db
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


class TestDecisionGenerateAPIWithAuth:
    """E2E tests for /api/v1/decisions/generate with real authentication."""

    @pytest_asyncio.fixture(scope="class", autouse=True)
    async def setup_database(self):
        """Initialize database for E2E tests."""
        try:
            # Initialize database connection
            await init_db()
            yield
        except Exception as e:
            pytest.skip(f"Database not available: {e}")
        finally:
            # Cleanup
            try:
                await close_db()
            except Exception:
                pass

    @pytest.fixture
    def test_wallet(self):
        """Create a test wallet for authentication."""
        # Create a new test wallet (DO NOT use in production!)
        account = Account.create()
        return {
            "address": account.address,
            "private_key": account.key.hex(),
        }

    @pytest_asyncio.fixture
    async def async_client(self):
        """Create async HTTP client for testing."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

    @pytest_asyncio.fixture
    async def authenticated_client(self, async_client, test_wallet):
        """Create authenticated HTTP client with JWT token."""
        # Step 1: Request challenge
        challenge_response = await async_client.post(
            f"/api/v1/auth/challenge?address={test_wallet['address']}"
        )
        assert challenge_response.status_code == 200
        challenge = challenge_response.json()["challenge"]

        # Step 2: Sign challenge
        message = encode_defunct(text=challenge)
        signed_message = Account.sign_message(message, private_key=test_wallet["private_key"])
        signature = signed_message.signature.hex()
        if not signature.startswith("0x"):
            signature = f"0x{signature}"

        # Step 3: Login to get JWT
        login_response = await async_client.post(
            f"/api/v1/auth/login?challenge={challenge}&signature={signature}&address={test_wallet['address']}"
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        # Return client with auth headers
        async_client.headers.update({"Authorization": f"Bearer {token}"})
        return async_client

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
            is_active=True,
        )

        # Create performance metrics
        performance = PerformanceMetrics(
            total_pnl=1000.0,
            win_rate=65.0,
            avg_win=150.0,
            avg_loss=-80.0,
            max_drawdown=500.0,
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
            max_drawdown=500.0,
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
            exit_plan="Take profit at resistance, stop loss at support",
            rationale="Strong bullish momentum with good technical indicators",
            confidence=85,
            risk_level="medium",
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

    # ========================================================================
    # Authentication Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_authentication_flow_success(self, async_client, test_wallet):
        """Test 1.1: Successful authentication flow."""
        # Request challenge
        challenge_response = await async_client.post(
            f"/api/v1/auth/challenge?address={test_wallet['address']}"
        )
        assert challenge_response.status_code == 200
        challenge = challenge_response.json()["challenge"]
        assert challenge is not None

        # Sign challenge
        message = encode_defunct(text=challenge)
        signed_message = Account.sign_message(message, private_key=test_wallet["private_key"])
        signature = signed_message.signature.hex()
        if not signature.startswith("0x"):
            signature = f"0x{signature}"

        # Login
        login_response = await async_client.post(
            f"/api/v1/auth/login?challenge={challenge}&signature={signature}&address={test_wallet['address']}"
        )
        assert login_response.status_code == 200
        data = login_response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_missing_authentication_token(self, async_client, mock_decision_result):
        """Test 1.2: Missing authentication token."""
        with patch("app.api.routes.decision_engine.get_decision_engine") as mock_get_engine:
            mock_engine = AsyncMock()
            mock_engine.make_trading_decision.return_value = mock_decision_result
            mock_get_engine.return_value = mock_engine

            response = await async_client.post(
                "/api/v1/decisions/generate",
                json={"symbol": "BTCUSDT", "account_id": 1},
            )

            # Should return 401 Unauthorized
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_jwt_token(self, async_client, mock_decision_result):
        """Test 1.3: Invalid JWT token."""
        with patch("app.api.routes.decision_engine.get_decision_engine") as mock_get_engine:
            mock_engine = AsyncMock()
            mock_engine.make_trading_decision.return_value = mock_decision_result
            mock_get_engine.return_value = mock_engine

            # Use invalid token
            async_client.headers.update({"Authorization": "Bearer invalid_token_here"})

            response = await async_client.post(
                "/api/v1/decisions/generate",
                json={"symbol": "BTCUSDT", "account_id": 1},
            )

            # Should return 401 or 403
            assert response.status_code in [401, 403]

    # ========================================================================
    # Request Validation Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_valid_request_minimal_fields(self, authenticated_client, mock_decision_result):
        """Test 2.1: Valid request with minimal fields."""
        with patch("app.api.routes.decision_engine.get_decision_engine") as mock_get_engine:
            mock_engine = AsyncMock()
            mock_engine.make_trading_decision.return_value = mock_decision_result
            mock_get_engine.return_value = mock_engine

            response = await authenticated_client.post(
                "/api/v1/decisions/generate",
                json={"symbol": "BTCUSDT", "account_id": 1},
            )

            assert response.status_code == 200
            data = response.json()
            assert "decision" in data
            assert "context" in data

    @pytest.mark.asyncio
    async def test_valid_request_all_fields(self, authenticated_client, mock_decision_result):
        """Test 2.2: Valid request with all fields."""
        with patch("app.api.routes.decision_engine.get_decision_engine") as mock_get_engine:
            mock_engine = AsyncMock()
            mock_engine.make_trading_decision.return_value = mock_decision_result
            mock_get_engine.return_value = mock_engine

            response = await authenticated_client.post(
                "/api/v1/decisions/generate",
                json={
                    "symbol": "BTCUSDT",
                    "account_id": 1,
                    "strategy_override": "aggressive",
                    "force_refresh": True,
                    "ab_test_name": "variant_a",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "decision" in data

    @pytest.mark.asyncio
    async def test_missing_required_fields(self, authenticated_client):
        """Test 2.5: Missing required fields."""
        response = await authenticated_client.post(
            "/api/v1/decisions/generate",
            json={"symbol": "BTCUSDT"},  # Missing account_id
        )

        # Should return 422 Unprocessable Entity
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_data_types(self, authenticated_client):
        """Test 2.6: Invalid data types."""
        response = await authenticated_client.post(
            "/api/v1/decisions/generate",
            json={"symbol": 123, "account_id": "abc"},  # Wrong types
        )

        # Should return 422 Unprocessable Entity
        assert response.status_code == 422

    # ========================================================================
    # Success Scenarios
    # ========================================================================

    @pytest.mark.asyncio
    async def test_generate_decision_btc(self, authenticated_client, mock_decision_result):
        """Test 3.1: Generate decision for BTC."""
        with patch("app.api.routes.decision_engine.get_decision_engine") as mock_get_engine:
            mock_engine = AsyncMock()
            mock_engine.make_trading_decision.return_value = mock_decision_result
            mock_get_engine.return_value = mock_engine

            response = await authenticated_client.post(
                "/api/v1/decisions/generate",
                json={"symbol": "BTCUSDT", "account_id": 1},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["decision"]["asset"] == "BTCUSDT"

    @pytest.mark.asyncio
    async def test_generate_decision_eth(self, authenticated_client, mock_decision_result):
        """Test 3.2: Generate decision for ETH."""
        with patch("app.api.routes.decision_engine.get_decision_engine") as mock_get_engine:
            mock_engine = AsyncMock()
            # Update mock for ETH
            eth_result = mock_decision_result.model_copy(deep=True)
            eth_result.decision.asset = "ETHUSDT"
            eth_result.context.symbol = "ETHUSDT"
            mock_engine.make_trading_decision.return_value = eth_result
            mock_get_engine.return_value = mock_engine

            response = await authenticated_client.post(
                "/api/v1/decisions/generate",
                json={"symbol": "ETHUSDT", "account_id": 1},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["decision"]["asset"] == "ETHUSDT"

    @pytest.mark.asyncio
    async def test_strategy_override(self, authenticated_client, mock_decision_result):
        """Test 3.4: Strategy override."""
        with patch("app.api.routes.decision_engine.get_decision_engine") as mock_get_engine:
            mock_engine = AsyncMock()
            mock_engine.make_trading_decision.return_value = mock_decision_result
            mock_get_engine.return_value = mock_engine

            response = await authenticated_client.post(
                "/api/v1/decisions/generate",
                json={
                    "symbol": "BTCUSDT",
                    "account_id": 1,
                    "strategy_override": "aggressive",
                },
            )

            assert response.status_code == 200
            # Verify strategy_override was passed to engine
            mock_engine.make_trading_decision.assert_called_once()
            call_kwargs = mock_engine.make_trading_decision.call_args.kwargs
            assert call_kwargs["strategy_override"] == "aggressive"

    @pytest.mark.asyncio
    async def test_force_refresh(self, authenticated_client, mock_decision_result):
        """Test 3.5: Force refresh."""
        with patch("app.api.routes.decision_engine.get_decision_engine") as mock_get_engine:
            mock_engine = AsyncMock()
            mock_engine.make_trading_decision.return_value = mock_decision_result
            mock_get_engine.return_value = mock_engine

            response = await authenticated_client.post(
                "/api/v1/decisions/generate",
                json={"symbol": "BTCUSDT", "account_id": 1, "force_refresh": True},
            )

            assert response.status_code == 200
            # Verify force_refresh was passed to engine
            call_kwargs = mock_engine.make_trading_decision.call_args.kwargs
            assert call_kwargs["force_refresh"] is True

    # ========================================================================
    # Error Handling Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self, authenticated_client):
        """Test 4.1: Rate limit exceeded."""
        from app.services.llm.decision_engine import RateLimitExceededError

        with patch("app.api.routes.decision_engine.get_decision_engine") as mock_get_engine:
            mock_engine = AsyncMock()
            mock_engine.make_trading_decision.side_effect = RateLimitExceededError(
                "Rate limit exceeded: 60 requests per minute"
            )
            mock_get_engine.return_value = mock_engine

            response = await authenticated_client.post(
                "/api/v1/decisions/generate",
                json={"symbol": "BTCUSDT", "account_id": 1},
            )

            # Should return 429 Too Many Requests
            assert response.status_code == 429
            data = response.json()
            assert "detail" in data

    @pytest.mark.asyncio
    async def test_decision_engine_error(self, authenticated_client):
        """Test 4.2: Decision engine error."""
        from app.services.llm.decision_engine import DecisionEngineError

        with patch("app.api.routes.decision_engine.get_decision_engine") as mock_get_engine:
            mock_engine = AsyncMock()
            mock_engine.make_trading_decision.side_effect = DecisionEngineError(
                "Failed to generate decision"
            )
            mock_get_engine.return_value = mock_engine

            response = await authenticated_client.post(
                "/api/v1/decisions/generate",
                json={"symbol": "BTCUSDT", "account_id": 1},
            )

            # Should return 400 Bad Request
            assert response.status_code == 400
            data = response.json()
            assert "detail" in data

    @pytest.mark.asyncio
    async def test_internal_server_error(self, authenticated_client):
        """Test 4.3: Internal server error."""
        with patch("app.api.routes.decision_engine.get_decision_engine") as mock_get_engine:
            mock_engine = AsyncMock()
            mock_engine.make_trading_decision.side_effect = Exception("Unexpected error")
            mock_get_engine.return_value = mock_engine

            response = await authenticated_client.post(
                "/api/v1/decisions/generate",
                json={"symbol": "BTCUSDT", "account_id": 1},
            )

            # Should return 500 Internal Server Error
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data

    # ========================================================================
    # Response Validation Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_response_structure_validation(self, authenticated_client, mock_decision_result):
        """Test 5.1: Response structure validation."""
        with patch("app.api.routes.decision_engine.get_decision_engine") as mock_get_engine:
            mock_engine = AsyncMock()
            mock_engine.make_trading_decision.return_value = mock_decision_result
            mock_get_engine.return_value = mock_engine

            response = await authenticated_client.post(
                "/api/v1/decisions/generate",
                json={"symbol": "BTCUSDT", "account_id": 1},
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

    @pytest.mark.asyncio
    async def test_decision_object_validation(self, authenticated_client, mock_decision_result):
        """Test 5.2: Decision object validation."""
        with patch("app.api.routes.decision_engine.get_decision_engine") as mock_get_engine:
            mock_engine = AsyncMock()
            mock_engine.make_trading_decision.return_value = mock_decision_result
            mock_get_engine.return_value = mock_engine

            response = await authenticated_client.post(
                "/api/v1/decisions/generate",
                json={"symbol": "BTCUSDT", "account_id": 1},
            )

            assert response.status_code == 200
            data = response.json()

            # Verify decision structure
            decision = data["decision"]
            assert "asset" in decision
            assert "action" in decision
            assert decision["action"] in ["buy", "sell", "hold"]
            assert "allocation_usd" in decision
            assert decision["allocation_usd"] > 0
            assert "confidence" in decision
            assert 0 <= decision["confidence"] <= 100
            assert "risk_level" in decision
            assert "rationale" in decision
            assert len(decision["rationale"]) > 0

    @pytest.mark.asyncio
    async def test_context_object_validation(self, authenticated_client, mock_decision_result):
        """Test 5.3: Context object validation."""
        with patch("app.api.routes.decision_engine.get_decision_engine") as mock_get_engine:
            mock_engine = AsyncMock()
            mock_engine.make_trading_decision.return_value = mock_decision_result
            mock_get_engine.return_value = mock_engine

            response = await authenticated_client.post(
                "/api/v1/decisions/generate",
                json={"symbol": "BTCUSDT", "account_id": 1},
            )

            assert response.status_code == 200
            data = response.json()

            # Verify context structure
            context = data["context"]
            assert "symbol" in context
            assert "account_id" in context
            assert "market_data" in context
            assert "account_state" in context
            assert "risk_metrics" in context

            # Verify market_data
            market_data = context["market_data"]
            assert "current_price" in market_data
            assert "technical_indicators" in market_data

            # Verify account_state
            account_state = context["account_state"]
            assert "balance_usd" in account_state
            assert "available_balance" in account_state

