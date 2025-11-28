"""
Integration tests for the updated Decision Engine.
"""

from unittest.mock import Mock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app
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


@pytest_asyncio.fixture
async def admin_user(db_session):
    """Create an admin user for testing."""
    user = User(address="0x1234567890123456789012345678901234567890", is_admin=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    yield user
    # Cleanup
    await db_session.delete(user)
    await db_session.commit()


@pytest.fixture
def auth_headers(admin_user):
    """Generate authentication headers with JWT token."""
    token = create_access_token(data={"sub": admin_user.address})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client():
    """Create a TestClient instance for testing."""
    yield TestClient(app)


@pytest.mark.asyncio
async def test_generate_decision_with_new_context(client, auth_headers, monkeypatch):
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

    # Create proper MarketContext object to avoid Pydantic serialization warnings
    from app.schemas.trading_decision import (
        MarketContext,
        AssetMarketData,
        TechnicalIndicators,
        TechnicalIndicatorsSet
    )

    mock_context.market_data = MarketContext(
        assets={
            "BTCUSDT": AssetMarketData(
                symbol="BTCUSDT",
                current_price=50000.0,
                price_change_24h=2.5,
                volume_24h=1000000.0,
                volatility=0.02,
                technical_indicators=TechnicalIndicators(
                    interval=TechnicalIndicatorsSet(ema_20=list(range(10))),
                    long_interval=TechnicalIndicatorsSet(ema_20=list(range(10)))
                )
            ),
            "ETHUSDT": AssetMarketData(
                symbol="ETHUSDT",
                current_price=3000.0,
                price_change_24h=1.5,
                volume_24h=500000.0,
                volatility=0.03,
                technical_indicators=TechnicalIndicators(
                    interval=TechnicalIndicatorsSet(ema_20=list(range(10))),
                    long_interval=TechnicalIndicatorsSet(ema_20=list(range(10)))
                )
            )
        }
    )

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
        headers=auth_headers,
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
        headers=auth_headers,
    )

    # Verify the response
    assert response.status_code == 200
    response_json = response.json()
    assert "decision" in response_json
    assert "decisions" in response_json["decision"]
