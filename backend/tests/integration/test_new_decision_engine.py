"""
Integration tests for the updated Decision Engine.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.trading_decision import (
    DecisionResult,
    TechnicalIndicators,
    TechnicalIndicatorsSet,
    TradingContext,
    TradingDecision,
)
from app.core.security import get_current_user
from app.middleware import AdminOnlyMiddleware
from app.models.account import User
from app.services.llm import decision_engine as decision_engine_module
from app.services.llm.decision_engine import get_decision_engine


@pytest.fixture(autouse=True)
def reset_decision_engine_singleton():
    """Reset the decision engine singleton before each test."""
    decision_engine_module._decision_engine = None


@pytest.fixture
def mock_get_current_user():
    """Fixture to mock the get_current_user dependency."""
    mock_user = User(address="0x1234567890123456789012345678901234567890", is_admin=True)

    async def _mock_get_current_user():
        return mock_user

    return _mock_get_current_user


@pytest.fixture
def client(mock_get_current_user):
    """Create a TestClient instance for testing."""
    app.dependency_overrides[get_current_user] = mock_get_current_user
    original_middleware = app.user_middleware
    app.user_middleware = [
        middleware
        for middleware in app.user_middleware
        if middleware.cls is not AdminOnlyMiddleware
    ]
    yield TestClient(app)
    app.dependency_overrides = {}
    app.user_middleware = original_middleware


def test_generate_decision_with_new_context(client, monkeypatch):
    """Test the /api/v1/decisions/generate endpoint with the new context."""
    # Create mock DecisionResult
    mock_decision = TradingDecision(
        asset="BTCUSDT",
        action="buy",
        allocation_usd=1000.0,
        tp_price=50000.0,
        sl_price=45000.0,
        exit_plan="Test",
        rationale="Test",
        confidence=85.0,
        risk_level="medium",
    )
    # Create a mock TradingContext with the expected structure
    mock_context = Mock(spec=TradingContext)
    mock_context.symbol = "BTCUSDT"
    mock_context.account_id = 1
    mock_context.market_data = {
        "technical_indicators": {
            "interval": {"ema_20": list(range(10))},
            "long_interval": {"ema_20": list(range(10))},
        }
    }
    mock_result = DecisionResult(
        decision=mock_decision,
        context=mock_context,
        validation_passed=True,
        validation_errors=[],
        processing_time_ms=100.0,
        model_used="test_model",
        api_cost=0.0,
    )

    # Mock the make_trading_decision method
    async def mock_make_trading_decision(*args, **kwargs):
        return mock_result

    monkeypatch.setattr(
        decision_engine_module.DecisionEngine,
        "make_trading_decision",
        mock_make_trading_decision,
    )

    # Call the endpoint
    response = client.post(
        "/api/v1/decisions/generate",
        json={"symbol": "BTCUSDT", "account_id": 1},
    )

    # Verify the response
    assert response.status_code == 200
    response_json = response.json()
    assert "context" in response_json
    assert "technical_indicators" in response_json["context"]["market_data"]
    assert "interval" in response_json["context"]["market_data"]["technical_indicators"]
    assert "long_interval" in response_json["context"]["market_data"]["technical_indicators"]
    assert "ema_20" in response_json["context"]["market_data"]["technical_indicators"]["interval"]

    # Clean up the dependency override
    app.dependency_overrides = {}
