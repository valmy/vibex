"""
Integration tests for the updated Decision Engine.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app
from app.models.account import Account, User
from app.models.strategy import Strategy
from app.schemas.trading_decision import (
    DecisionResult,
    TechnicalIndicators,
    TechnicalIndicatorsSet,
    TradingContext,
    TradingDecision,
)
from app.services.llm.decision_engine import get_decision_engine


@pytest.fixture
def client():
    """Create a TestClient instance for testing."""
    return TestClient(app)


@pytest.mark.asyncio
async def test_generate_decision_with_new_context(client, db_session):
    """Test the /api/v1/decisions/generate endpoint with the new context."""
    # Create a test user, strategy and account
    admin_user = User(address="adminuser", is_admin=True)
    strategy = Strategy(
        strategy_id="test_strategy",
        strategy_name="Test Strategy",
        strategy_type="long_short",
        prompt_template="Test prompt",
        timeframe_preference='["5m", "1h"]',
        risk_parameters='{"max_risk_per_trade": 0.01}',
    )
    account = Account(
        user=admin_user,
        name="test_account",
        description="Test Account",
        status="active",
        leverage=1,
        max_position_size_usd=1000,
        risk_per_trade=0.01,
        is_paper_trading=True,
    )
    db_session.add(admin_user)
    db_session.add(strategy)
    db_session.add(account)
    await db_session.commit()


    # Create mock TradingContext with the new TechnicalIndicators structure
    mock_context = Mock(spec=TradingContext)
    mock_context.symbol = "BTCUSDT"
    mock_context.account_id = 1
    mock_context.market_data = Mock()
    mock_context.account_state = Mock()
    mock_context.recent_trades = []
    mock_context.risk_metrics = Mock()
    mock_context.timestamp = datetime.now(timezone.utc)
    mock_context.market_data.technical_indicators = TechnicalIndicators(
        interval=TechnicalIndicatorsSet(ema_20=list(range(10))),
        long_interval=TechnicalIndicatorsSet(ema_20=list(range(10))),
    )

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
    mock_result = DecisionResult(
        decision=mock_decision,
        context=mock_context,
        validation_passed=True,
        validation_errors=[],
        processing_time_ms=100.0,
        model_used="test_model",
        api_cost=0.0,
    )

    # Mock DecisionEngine
    mock_engine = AsyncMock()
    mock_engine.make_trading_decision.return_value = mock_result

    # Override the dependency
    app.dependency_overrides[get_decision_engine] = lambda: mock_engine

    # Call the endpoint
    access_token = create_access_token(data={"sub": admin_user.address})
    headers = {"Authorization": f"Bearer {access_token}"}
    response = client.post(
        "/api/v1/decisions/generate",
        json={"symbol": "BTCUSDT", "account_id": 1},
        headers=headers,
    )

    # Verify the response
    assert response.status_code == 200
    response_json = response.json()
    assert "decision" in response_json
    assert "context" in response_json
    assert "technical_indicators" in response_json["context"]["market_data"]
    assert "interval" in response_json["context"]["market_data"]["technical_indicators"]
    assert "long_interval" in response_json["context"]["market_data"]["technical_indicators"]
    assert "ema_20" in response_json["context"]["market_data"]["technical_indicators"]["interval"]

    # Clean up the dependency override
    app.dependency_overrides = {}
