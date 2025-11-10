"""
Test configuration and fixtures.

Provides common fixtures and setup for all tests.
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio



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
    client = AsyncClient(transport=transport, base_url="http://test")
    try:
        yield client
    finally:
        # Properly close the client to avoid event loop issues
        try:
            await client.aclose()
        except Exception:
            pass


@pytest_asyncio.fixture
async def authenticated_client(async_client, test_wallet):
    """Create authenticated HTTP client with JWT token."""
    try:
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
        yield async_client
    finally:
        # Ensure proper cleanup
        try:
            await async_client.aclose()
        except Exception:
            pass


@pytest_asyncio.fixture
async def test_account_with_data(test_wallet):
    """Create a test account with real market data for E2E testing."""
    from app.db.session import get_session_factory
    from app.models.account import Account, User
    from app.models.market_data import MarketData
    from sqlalchemy import select

    session_factory = get_session_factory()
    async with session_factory() as db:
        try:
            # Step 1: Create or get test user
            result = await db.execute(
                select(User).where(User.address == test_wallet["address"].lower())
            )
            user = result.scalar_one_or_none()
            if not user:
                user = User(address=test_wallet["address"].lower(), is_admin=False)
                db.add(user)
                await db.flush()

            # Step 2: Create test account
            account = Account(
                user_id=user.id,
                name=f"Test Account {test_wallet['address'][:8]}",
                description="Test account for E2E testing",
                status="active",
                leverage=1.0,
                max_position_size_usd=5000.0,
                risk_per_trade=0.02,
                is_paper_trading=True,
                is_multi_account=False,
                is_enabled=True,
            )
            db.add(account)
            await db.flush()

            # Step 3: Create market data for BTCUSDT (100 candles, 5-minute intervals)
            now = datetime.now(timezone.utc)
            for i in range(100):
                timestamp = now - timedelta(minutes=5 * i)
                market_data = MarketData(
                    time=timestamp,
                    symbol="BTCUSDT",
                    interval="5m",
                    open=50000.0 + i * 10,
                    high=50500.0 + i * 10,
                    low=49500.0 + i * 10,
                    close=50250.0 + i * 10,
                    volume=1000.0 + i * 10,
                    quote_asset_volume=50000000.0 + i * 100000,
                    number_of_trades=100.0 + i,
                    taker_buy_base_asset_volume=500.0 + i * 5,
                    taker_buy_quote_asset_volume=25000000.0 + i * 50000,
                    funding_rate=0.0001,
                )
                db.add(market_data)

            # Step 4: Create market data for ETHUSDT (100 candles)
            for i in range(100):
                timestamp = now - timedelta(minutes=5 * i)
                market_data = MarketData(
                    time=timestamp,
                    symbol="ETHUSDT",
                    interval="5m",
                    open=3000.0 + i * 1,
                    high=3050.0 + i * 1,
                    low=2950.0 + i * 1,
                    close=3025.0 + i * 1,
                    volume=10000.0 + i * 100,
                    quote_asset_volume=30000000.0 + i * 100000,
                    number_of_trades=200.0 + i,
                    taker_buy_base_asset_volume=5000.0 + i * 50,
                    taker_buy_quote_asset_volume=15000000.0 + i * 50000,
                    funding_rate=0.00005,
                )
                db.add(market_data)

            await db.commit()
            await db.refresh(account)
            return account
        except Exception as e:
            await db.rollback()
            raise e
