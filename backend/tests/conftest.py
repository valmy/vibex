"""
Test configuration and fixtures.

Provides common fixtures and setup for all tests.
"""

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from dotenv import load_dotenv

# Load .env.local if it exists (for local testing with localhost database)
env_local = Path(__file__).parent.parent / ".env.local"
if env_local.exists():
    load_dotenv(env_local, override=True)
else:
    load_dotenv()

# Set testing environment before importing app modules
os.environ["ENVIRONMENT"] = "testing"

from app.db.session import close_db, get_async_engine, get_session_factory, init_db
from httpx import ASGITransport, AsyncClient
from eth_account import Account
from eth_account.messages import encode_defunct
from app.main import app


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Create a database session for testing."""
    # Close any existing database connection from a different event loop
    try:
        engine = get_async_engine()
        await close_db()
    except RuntimeError:
        # No existing engine, that's fine
        pass

    # Initialize database on the current event loop
    try:
        await init_db()
        session_factory = get_session_factory()
    except Exception as e:
        pytest.skip(f"Database not available: {e}")

    try:
        async with session_factory() as session:
            yield session
    except Exception as e:
        pytest.skip(f"Database not available: {e}")


def create_mock_context():
    """Create a mock trading context for testing."""
    from app.schemas.trading_decision import (
        AccountContext,
        MarketContext,
        PerformanceMetrics,
        RiskMetrics,
        StrategyRiskParameters,
        TechnicalIndicators,
        TradingContext,
        TradingStrategy,
    )

    # Create mock technical indicators
    indicators = TechnicalIndicators(
        ema_20=48000.0,
        ema_50=47000.0,
        rsi=65.0,
        macd=100.0,
        macd_signal=90.0,
        bb_upper=49000.0,
        bb_lower=46000.0,
        bb_middle=47500.0,
        atr=500.0,
    )

    # Create mock market context
    market_context = MarketContext(
        current_price=48000.0,
        price_change_24h=1000.0,
        volume_24h=1000000.0,
        funding_rate=0.01,
        open_interest=50000000.0,
        volatility=0.02,
        technical_indicators=indicators,
        price_history=[],
    )

    # Create mock strategy
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
        timeframe_preference=["4h", "1d"],
        max_positions=3,
        is_active=True,
    )

    # Create mock performance metrics
    performance = PerformanceMetrics(
        total_pnl=1000.0,
        win_rate=60.0,
        avg_win=150.0,
        avg_loss=-75.0,
        max_drawdown=-200.0,
        sharpe_ratio=1.5,
    )

    # Create mock account context
    account_context = AccountContext(
        account_id=1,
        balance_usd=10000.0,
        available_balance=8000.0,
        total_position_value_usd=2000.0,
        leverage=1.0,
        margin_ratio=0.2,
        total_pnl=1000.0,
        recent_performance=performance,
        risk_exposure=20.0,
        max_position_size=2000.0,
        active_strategy=strategy,
        open_positions=[],
    )

    # Create mock risk metrics
    risk_metrics = RiskMetrics(
        var_95=500.0,
        max_drawdown=1000.0,
        correlation_risk=15.0,
        concentration_risk=25.0,
    )

    # Create mock trading context
    return TradingContext(
        symbol="BTCUSDT",
        account_id=1,
        market_data=market_context,
        account_state=account_context,
        risk_metrics=risk_metrics,
    )


@pytest.fixture
def mock_llm_service():
    """Create a mock LLM service for testing."""
    from app.schemas.trading_decision import DecisionResult, TradingDecision
    from app.services.llm.llm_service import LLMService

    mock_service = AsyncMock(spec=LLMService)

    # Mock successful decision generation
    mock_decision = TradingDecision(
        asset="BTCUSDT",
        action="buy",
        allocation_usd=1000.0,
        tp_price=50000.0,
        sl_price=46000.0,
        exit_plan="Take profit at resistance",
        rationale="Strong bullish momentum with good technical indicators",
        confidence=85,
        risk_level="medium",
        position_adjustment=None,
        order_adjustment=None,
    )

    # Create mock context
    mock_context = create_mock_context()

    mock_result = DecisionResult(
        decision=mock_decision,
        context=mock_context,
        validation_passed=True,
        validation_errors=[],
        processing_time_ms=250.0,
        model_used="test-model",
    )

    mock_service.generate_trading_decision.return_value = mock_result
    return mock_service


@pytest.fixture
def mock_context_builder():
    """Create a mock context builder for testing."""
    from app.services.llm.context_builder import ContextBuilderService

    mock_builder = AsyncMock(spec=ContextBuilderService)

    # Create mock trading context
    mock_context = create_mock_context()
    mock_builder.build_trading_context.return_value = mock_context
    return mock_builder


@pytest.fixture
def test_wallet():
    """Create a test wallet for authentication."""
    # Create a new test wallet (DO NOT use in production!)
    account = Account.create()
    return {
        "address": account.address,
        "private_key": account.key.hex(),
    }


@pytest_asyncio.fixture
async def async_client():
    """Create async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def authenticated_client(async_client, test_wallet):
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

    # Step 4: Add token to client headers
    async_client.headers["Authorization"] = f"Bearer {token}"
    return async_client
