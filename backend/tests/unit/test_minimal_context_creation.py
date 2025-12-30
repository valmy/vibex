"""
Unit tests for minimal context creation methods.

Validates that all helper methods in DecisionEngine create valid Pydantic models
that satisfy all schema constraints.
"""

import pytest
from datetime import datetime

from src.app.services.llm.decision_engine import DecisionEngine
from src.app.schemas.trading_decision import (
    AccountContext,
    MarketContext,
    PerformanceMetrics,
    RiskMetrics,
    StrategyRiskParameters,
    TradingContext,
    TradingStrategy,
)


class TestMinimalContextCreation:
    """Test that all minimal context creation methods produce valid instances."""

    @pytest.fixture
    def decision_engine(self):
        """Create a DecisionEngine instance for testing."""
        # Pass None for session_factory since we don't need DB for these tests
        return DecisionEngine(session_factory=None)

    def test_create_minimal_performance_metrics(self, decision_engine):
        """Test that minimal PerformanceMetrics satisfies all constraints."""
        metrics = decision_engine._create_minimal_performance_metrics()

        assert isinstance(metrics, PerformanceMetrics)
        assert metrics.total_pnl == 0.0
        assert metrics.win_rate == 0.0
        assert 0 <= metrics.win_rate <= 100  # Constraint: ge=0, le=100
        assert metrics.avg_win == 0.0
        assert metrics.avg_loss == 0.0
        assert metrics.max_drawdown == 0.0
        assert metrics.sharpe_ratio is None

    def test_create_minimal_strategy_risk_parameters(self, decision_engine):
        """Test that minimal StrategyRiskParameters satisfies all constraints."""
        params = decision_engine._create_minimal_strategy_risk_parameters()

        assert isinstance(params, StrategyRiskParameters)
        assert 0 <= params.max_risk_per_trade <= 100  # Constraint: ge=0, le=100
        assert 0 <= params.max_daily_loss <= 100  # Constraint: ge=0, le=100
        assert 0 <= params.stop_loss_percentage <= 50  # Constraint: ge=0, le=50
        assert params.take_profit_ratio >= 1.0  # Constraint: ge=1.0
        assert 1.0 <= params.max_leverage <= 20.0  # Constraint: ge=1.0, le=20.0
        assert params.cooldown_period >= 0  # Constraint: ge=0
        assert params.max_funding_rate_bps >= 0  # Constraint: ge=0
        assert params.liquidation_buffer >= 0  # Constraint: ge=0

    def test_create_minimal_trading_strategy(self, decision_engine):
        """Test that minimal TradingStrategy satisfies all constraints."""
        strategy = decision_engine._create_minimal_trading_strategy()

        assert isinstance(strategy, TradingStrategy)
        assert strategy.strategy_id == "unknown"
        assert strategy.strategy_name == "Unknown Strategy"
        assert strategy.strategy_type == "conservative"
        assert strategy.prompt_template == "No template available"
        assert isinstance(strategy.risk_parameters, StrategyRiskParameters)
        assert strategy.max_positions >= 1  # Constraint: ge=1
        assert strategy.funding_rate_threshold >= 0  # Constraint: ge=0
        assert strategy.is_active is False

    def test_create_minimal_account_context(self, decision_engine):
        """Test that minimal AccountContext satisfies all constraints."""
        account_id = 123
        context = decision_engine._create_minimal_account_context(account_id)

        assert isinstance(context, AccountContext)
        assert context.account_id == account_id
        assert context.balance_usd >= 0  # Constraint: ge=0
        assert context.available_balance >= 0  # Constraint: ge=0
        assert 0 <= context.risk_exposure <= 100  # Constraint: ge=0, le=100
        assert context.max_position_size > 0  # Constraint: gt=0 (CRITICAL!)
        assert context.maker_fee_bps >= 0  # Constraint: ge=0
        assert context.taker_fee_bps >= 0  # Constraint: ge=0
        assert isinstance(context.recent_performance, PerformanceMetrics)
        assert isinstance(context.active_strategy, TradingStrategy)

    def test_create_minimal_risk_metrics(self, decision_engine):
        """Test that minimal RiskMetrics satisfies all constraints."""
        metrics = decision_engine._create_minimal_risk_metrics()

        assert isinstance(metrics, RiskMetrics)
        assert isinstance(metrics.var_95, float)
        assert isinstance(metrics.max_drawdown, float)
        assert 0 <= metrics.correlation_risk <= 100  # Constraint: ge=0, le=100
        assert 0 <= metrics.concentration_risk <= 100  # Constraint: ge=0, le=100

    def test_create_minimal_context(self, decision_engine):
        """Test that minimal TradingContext satisfies all constraints."""
        account_id = 456
        timestamp = datetime.utcnow()
        context = decision_engine._create_minimal_context(account_id, timestamp)

        assert isinstance(context, TradingContext)
        assert context.account_id == account_id
        assert context.timestamp == timestamp
        assert context.symbols == []
        assert context.timeframes == []
        assert isinstance(context.market_data, MarketContext)
        assert isinstance(context.account_state, AccountContext)
        assert isinstance(context.risk_metrics, RiskMetrics)
        assert context.recent_trades == {}
        assert len(context.errors) > 0  # Should have error about historical context
        assert "Historical decision" in context.errors[0]

    def test_all_minimal_objects_are_pydantic_valid(self, decision_engine):
        """
        Integration test: Ensure all nested objects validate correctly.

        This test creates a full minimal context and validates the entire
        object graph, ensuring no Pydantic validation errors occur.
        """
        account_id = 789
        timestamp = datetime.utcnow()

        # This should not raise any ValidationError
        context = decision_engine._create_minimal_context(account_id, timestamp)

        # Test that we can serialize and deserialize without errors
        context_dict = context.model_dump()
        assert isinstance(context_dict, dict)

        # Recreate from dict to ensure round-trip validation
        recreated = TradingContext(**context_dict)
        assert recreated.account_id == account_id
        assert isinstance(recreated.account_state.max_position_size, float)
        assert recreated.account_state.max_position_size > 0  # The critical constraint
