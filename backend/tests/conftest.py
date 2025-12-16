"""
Test configuration and fixtures.

Provides common fixtures and setup for all tests.
"""

import os
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

# Set testing environment before importing app modules
os.environ["ENVIRONMENT"] = "testing"

from app.db.session import close_db, get_async_engine, get_session_factory, init_db
from app.db import session as db_session_module


@pytest_asyncio.fixture(scope="function")
async def db_session_factory():
    """Create a database session factory for testing."""
    # Safety check: If global engine is set, it's from a previous loop.
    # We cannot await close_db() on it because the loop is likely closed.
    # So we just forcibly reset the global variables.
    if db_session_module.async_engine is not None:
        db_session_module.async_engine = None
        db_session_module.AsyncSessionLocal = None

    # Initialize database on the current event loop
    try:
        await init_db()
        yield get_session_factory()
    except Exception as e:
        pytest.skip(f"Database not available: {e}")
    finally:
        # Clean up at the end of the test
        await close_db()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_session_factory):
    """Create a database session for testing."""
    try:
        async with db_session_factory() as session:
            yield session
    except Exception as e:
        pytest.skip(f"Database not available: {e}")


def create_mock_context(symbols=None):
    """Create a mock trading context for testing.

    Args:
        symbols: List of symbols to include in context. Defaults to ["BTCUSDT"]
    """
    from app.schemas.trading_decision import (
        AccountContext,
        AssetMarketData,
        MarketContext,
        PerformanceMetrics,
        RiskMetrics,
        StrategyRiskParameters,
        TechnicalIndicators,
        TechnicalIndicatorsSet,
        TradingContext,
        TradingStrategy,
    )

    if symbols is None:
        symbols = ["BTCUSDT"]

    # Create mock technical indicators
    indicators = TechnicalIndicators(
        interval=TechnicalIndicatorsSet(
            ema_20=[48000.0],
            ema_50=[47000.0],
            rsi=[65.0],
            macd=[100.0],
            macd_signal=[90.0],
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
            macd_signal=[140.0],
            bb_upper=[49500.0],
            bb_lower=[46500.0],
            bb_middle=[48000.0],
            atr=[550.0],
        ),
    )

    # Create asset market data for each symbol
    assets = {}
    base_prices = {"BTCUSDT": 48000.0, "ETHUSDT": 3200.0, "SOLUSDT": 120.0}

    for symbol in symbols:
        base_price = base_prices.get(symbol, 50000.0)
        assets[symbol] = AssetMarketData(
            symbol=symbol,
            current_price=base_price,
            price_change_24h=base_price * 0.02,  # 2% change
            volume_24h=1000000.0,
            funding_rate=0.01,
            open_interest=50000000.0,
            volatility=0.02,
            technical_indicators=indicators,
            price_history=[],
        )

    # Create mock market context with multi-asset support
    market_context = MarketContext(
        assets=assets,
        market_sentiment="neutral",
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

    # Create mock trading context with multi-asset support
    return TradingContext(
        symbols=symbols,
        account_id=1,
        timeframes=["5m", "4h"],
        market_data=market_context,
        account_state=account_context,
        risk_metrics=risk_metrics,
        recent_trades={symbol: [] for symbol in symbols},
    )


@pytest.fixture
def mock_llm_service():
    """Create a mock LLM service for testing."""
    from app.schemas.trading_decision import (
        AssetDecision,
        DecisionResult,
        TradingDecision,
    )
    from app.services.llm.llm_service import LLMService

    mock_service = AsyncMock(spec=LLMService)

    # Mock successful multi-asset decision generation
    asset_decisions = [
        AssetDecision(
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
    ]

    mock_decision = TradingDecision(
        decisions=asset_decisions,
        portfolio_rationale="Focus on BTC with strong momentum",
        total_allocation_usd=1000.0,
        portfolio_risk_level="medium",
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

    # Create mock trading context (single asset by default)
    mock_context = create_mock_context()
    mock_builder.build_trading_context.return_value = mock_context

    # Also mock get_market_context for multi-asset tests
    mock_builder.get_market_context.return_value = mock_context.market_data

    return mock_builder
