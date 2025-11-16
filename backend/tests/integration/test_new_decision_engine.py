"""
Integration tests for the updated Decision Engine.
"""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.middleware import AdminOnlyMiddleware
from app.models.account import User
from app.schemas.trading_decision import (
    DecisionResult,
    TradingContext,
    TradingDecision,
)
from app.services.llm import decision_engine as decision_engine_module


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
    """Test the /api/v1/decisions/generate endpoint with multi-asset support."""
    from app.schemas.trading_decision import AssetDecision

    # Create mock multi-asset DecisionResult
    mock_asset_decisions = [
        AssetDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=1000.0,
            tp_price=50000.0,
            sl_price=45000.0,
            exit_plan="Test BTC",
            rationale="Test BTC rationale",
            confidence=85.0,
            risk_level="medium",
        ),
        AssetDecision(
            asset="ETHUSDT",
            action="hold",
            allocation_usd=0.0,
            exit_plan="Wait for better entry",
            rationale="Test ETH rationale",
            confidence=60.0,
            risk_level="low",
        ),
    ]

    mock_decision = TradingDecision(
        decisions=mock_asset_decisions,
        portfolio_rationale="Test portfolio strategy",
        total_allocation_usd=1000.0,
        portfolio_risk_level="medium",
    )

    # Create a mock TradingContext with the expected multi-asset structure
    mock_context = Mock(spec=TradingContext)
    mock_context.symbols = ["BTCUSDT", "ETHUSDT"]
    mock_context.account_id = 1
    mock_context.market_data = {
        "assets": {
            "BTCUSDT": {
                "technical_indicators": {
                    "interval": {"ema_20": list(range(10))},
                    "long_interval": {"ema_20": list(range(10))},
                }
            },
            "ETHUSDT": {
                "technical_indicators": {
                    "interval": {"ema_20": list(range(10))},
                    "long_interval": {"ema_20": list(range(10))},
                }
            },
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

    # Test 1: Call endpoint with explicit symbols list
    response = client.post(
        "/api/v1/decisions/generate",
        json={"symbols": ["BTCUSDT", "ETHUSDT"], "account_id": 1},
    )

    # Verify the response
    assert response.status_code == 200
    response_json = response.json()
    assert "decision" in response_json
    assert "decisions" in response_json["decision"]
    assert len(response_json["decision"]["decisions"]) == 2
    assert response_json["decision"]["portfolio_rationale"] == "Test portfolio strategy"
    assert response_json["decision"]["total_allocation_usd"] == 1000.0

    # Test 2: Call endpoint without symbols (should default to ASSETS env var)
    response = client.post(
        "/api/v1/decisions/generate",
        json={"account_id": 1},
    )

    # Verify the response
    assert response.status_code == 200
    response_json = response.json()
    assert "decision" in response_json
    assert "decisions" in response_json["decision"]

    # Clean up the dependency override
    app.dependency_overrides = {}
