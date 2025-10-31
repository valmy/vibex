"""
Test configuration and fixtures.

Provides common fixtures and setup for all tests.
"""

import asyncio
import os
import pytest
from unittest.mock import AsyncMock, Mock

# Set testing environment before importing app modules
os.environ["ENVIRONMENT"] = "testing"

from app.core.config import config
from app.db.session import init_db, close_db, AsyncSessionLocal


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    """Initialize database for testing session."""
    # Initialize database
    await init_db()

    yield

    # Cleanup
    await close_db()


@pytest.fixture
async def db_session():
    """Create a database session for testing."""
    if AsyncSessionLocal is None:
        await init_db()

    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()  # Rollback any changes made during test


def create_mock_context():
    """Create a mock trading context for testing."""
    from app.schemas.trading_decision import (
        TradingContext, MarketContext, AccountContext,
        TechnicalIndicators, PerformanceMetrics, RiskMetrics,
        TradingStrategy, StrategyRiskParameters
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
    from app.services.llm.llm_service import LLMService
    from app.schemas.trading_decision import DecisionResult, TradingDecision

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