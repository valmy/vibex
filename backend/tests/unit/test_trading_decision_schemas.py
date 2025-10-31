"""
Unit tests for trading decision schemas.

Tests validation rules, constraints, and serialization for all trading decision models.
"""

from datetime import datetime
from datetime import timezone

import pytest
from pydantic import ValidationError

from app.schemas.trading_decision import (
    AccountContext,
    HealthStatus,
    MarketContext,
    PerformanceMetrics,
    PositionAdjustment,
    PricePoint,
    RiskMetrics,
    StrategyAlert,
    StrategyAssignment,
    StrategyMetrics,
    StrategyPerformance,
    StrategyRiskParameters,
    TechnicalIndicators,
    TradingContext,
    TradingDecision,
    TradingStrategy,
    UsageMetrics,
    ValidationResult,
)


class TestTradingDecision:
    """Test TradingDecision model validation."""

    def test_valid_buy_decision(self):
        """Test creating a valid buy decision."""
        decision = TradingDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=1000.0,
            tp_price=50000.0,
            sl_price=45000.0,
            exit_plan="Take profit at resistance, stop loss at support",
            rationale="Strong bullish momentum with RSI oversold",
            confidence=85.0,
            risk_level="medium",
        )

        assert decision.asset == "BTCUSDT"
        assert decision.action == "buy"
        assert decision.allocation_usd == 1000.0
        assert decision.confidence == 85.0

    def test_adjust_position_requires_position_adjustment(self):
        """Test that adjust_position action requires position_adjustment."""
        decision = TradingDecision(
            asset="BTCUSDT",
            action="adjust_position",
            allocation_usd=500.0,
            exit_plan="Adjust position size",
            rationale="Market conditions changed",
            confidence=70.0,
            risk_level="low",
        )

        errors = decision.validate_action_requirements()
        assert "position_adjustment is required for adjust_position action" in errors

    def test_adjust_orders_requires_order_adjustment(self):
        """Test that adjust_orders action requires order_adjustment."""
        decision = TradingDecision(
            asset="BTCUSDT",
            action="adjust_orders",
            allocation_usd=0.0,
            exit_plan="Adjust stop loss",
            rationale="Price moved favorably",
            confidence=80.0,
            risk_level="low",
        )

        errors = decision.validate_action_requirements()
        assert "order_adjustment is required for adjust_orders action" in errors

    def test_price_logic_validation_buy(self):
        """Test price logic validation for buy orders."""
        decision = TradingDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=1000.0,
            tp_price=45000.0,  # Invalid: TP should be higher than current
            sl_price=50000.0,  # Invalid: SL should be lower than current
            exit_plan="Test",
            rationale="Test",
            confidence=50.0,
            risk_level="low",
        )

        current_price = 48000.0
        errors = decision.validate_price_logic(current_price)

        assert len(errors) == 2
        assert any("Take-profit price must be higher" in error for error in errors)
        assert any("Stop-loss price must be lower" in error for error in errors)

    def test_invalid_confidence_range(self):
        """Test that confidence must be between 0 and 100."""
        with pytest.raises(ValidationError):
            TradingDecision(
                asset="BTCUSDT",
                action="buy",
                allocation_usd=1000.0,
                exit_plan="Test",
                rationale="Test",
                confidence=150.0,  # Invalid: > 100
                risk_level="low",
            )


class TestPositionAdjustment:
    """Test PositionAdjustment model validation."""

    def test_valid_position_adjustment(self):
        """Test creating a valid position adjustment."""
        adjustment = PositionAdjustment(
            adjustment_type="increase",
            adjustment_amount_usd=500.0,
            adjustment_percentage=25.0,
            new_tp_price=52000.0,
            new_sl_price=46000.0,
        )

        assert adjustment.adjustment_type == "increase"
        assert adjustment.adjustment_amount_usd == 500.0
        assert adjustment.adjustment_percentage == 25.0

    def test_invalid_adjustment_amount(self):
        """Test that adjustment amount must be positive."""
        with pytest.raises(ValidationError):
            PositionAdjustment(
                adjustment_type="increase",
                adjustment_amount_usd=-100.0,  # Invalid: negative
            )


class TestTradingStrategy:
    """Test TradingStrategy model validation."""

    def test_valid_strategy(self):
        """Test creating a valid trading strategy."""
        risk_params = StrategyRiskParameters(
            max_risk_per_trade=2.0,
            max_daily_loss=5.0,
            stop_loss_percentage=1.5,
            take_profit_ratio=2.0,
            max_leverage=3.0,
            cooldown_period=300,
        )

        strategy = TradingStrategy(
            strategy_id="conservative_swing",
            strategy_name="Conservative Swing Trading",
            strategy_type="conservative",
            prompt_template="Focus on low-risk entries",
            risk_parameters=risk_params,
            timeframe_preference=["4h", "1d"],
            max_positions=2,
        )

        assert strategy.strategy_id == "conservative_swing"
        assert strategy.strategy_type == "conservative"
        assert len(strategy.timeframe_preference) == 2

    def test_strategy_constraint_validation(self):
        """Test strategy constraint validation."""
        risk_params = StrategyRiskParameters(
            max_risk_per_trade=10.0,  # Higher than daily loss
            max_daily_loss=5.0,
            stop_loss_percentage=1.5,
        )

        strategy = TradingStrategy(
            strategy_id="test",
            strategy_name="Test",
            strategy_type="scalping",
            prompt_template="Test",
            risk_parameters=risk_params,
            timeframe_preference=["4h", "1d"],  # Wrong timeframes for scalping
        )

        errors = strategy.validate_strategy_constraints()
        assert len(errors) >= 2
        assert any("max_risk_per_trade cannot exceed max_daily_loss" in error for error in errors)
        assert any("Scalping strategy should include short timeframes" in error for error in errors)

    def test_default_prompt_templates(self):
        """Test default prompt template generation."""
        risk_params = StrategyRiskParameters(
            max_risk_per_trade=2.0, max_daily_loss=5.0, stop_loss_percentage=1.5
        )

        strategy = TradingStrategy(
            strategy_id="test",
            strategy_name="Test",
            strategy_type="conservative",
            prompt_template="",
            risk_parameters=risk_params,
        )

        template = strategy.get_default_prompt_template()
        assert "capital preservation" in template.lower()


class TestValidationResult:
    """Test ValidationResult model."""

    def test_validation_result_creation(self):
        """Test creating validation result."""
        result = ValidationResult(
            is_valid=False,
            errors=["Invalid allocation amount"],
            warnings=["High risk level"],
            validation_time_ms=15.5,
            rules_checked=["allocation_check", "risk_check"],
        )

        assert not result.is_valid
        assert len(result.errors) == 1
        assert len(result.warnings) == 1
        assert result.validation_time_ms == 15.5


class TestUsageMetrics:
    """Test UsageMetrics model."""

    def test_usage_metrics_creation(self):
        """Test creating usage metrics."""
        start_time = datetime.now(timezone.utc)
        end_time = datetime.now(timezone.utc)

        metrics = UsageMetrics(
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
            avg_response_time_ms=250.0,
            total_cost_usd=12.50,
            cost_per_request=0.125,
            requests_per_hour=10.0,
            error_rate=5.0,
            uptime_percentage=99.5,
            period_start=start_time,
            period_end=end_time,
        )

        assert metrics.total_requests == 100
        assert metrics.error_rate == 5.0
        assert metrics.uptime_percentage == 99.5


class TestHealthStatus:
    """Test HealthStatus model."""

    def test_healthy_status(self):
        """Test creating healthy status."""
        status = HealthStatus(
            is_healthy=True,
            response_time_ms=150.0,
            last_successful_request=datetime.now(timezone.utc),
            consecutive_failures=0,
            circuit_breaker_open=False,
            available_models=["gpt-4", "grok-4"],
            current_model="gpt-4",
        )

        assert status.is_healthy
        assert status.response_time_ms == 150.0
        assert len(status.available_models) == 2


class TestMarketContext:
    """Test MarketContext model validation."""

    def test_price_trend_detection(self):
        """Test price trend detection."""
        indicators = TechnicalIndicators(ema_20=48000.0, ema_50=47000.0, rsi=65.0, macd=100.0)

        # Create price history with upward trend
        price_points = [
            PricePoint(timestamp=datetime.now(timezone.utc), price=47000.0),
            PricePoint(timestamp=datetime.now(timezone.utc), price=47500.0),
            PricePoint(timestamp=datetime.now(timezone.utc), price=48000.0),
            PricePoint(timestamp=datetime.now(timezone.utc), price=48500.0),
        ]

        market_context = MarketContext(
            current_price=48500.0,
            price_change_24h=1500.0,
            volume_24h=1000000.0,
            volatility=0.02,
            technical_indicators=indicators,
            price_history=price_points,
        )

        trend = market_context.get_price_trend()
        assert trend == "bullish"

    def test_sufficient_indicators_check(self):
        """Test sufficient indicators validation."""
        # Indicators with enough data
        indicators_sufficient = TechnicalIndicators(
            ema_20=48000.0, ema_50=47000.0, rsi=65.0, macd=100.0
        )

        market_context = MarketContext(
            current_price=48000.0,
            price_change_24h=1000.0,
            volume_24h=1000000.0,
            volatility=0.02,
            technical_indicators=indicators_sufficient,
        )

        assert market_context.has_sufficient_indicators()

        # Indicators with insufficient data
        indicators_insufficient = TechnicalIndicators(ema_20=48000.0, rsi=65.0)

        market_context_insufficient = MarketContext(
            current_price=48000.0,
            price_change_24h=1000.0,
            volume_24h=1000000.0,
            volatility=0.02,
            technical_indicators=indicators_insufficient,
        )

        assert not market_context_insufficient.has_sufficient_indicators()


class TestAccountContext:
    """Test AccountContext model validation."""

    def test_can_open_new_position(self):
        """Test position opening validation."""
        risk_params = StrategyRiskParameters(
            max_risk_per_trade=2.0, max_daily_loss=5.0, stop_loss_percentage=1.5
        )

        strategy = TradingStrategy(
            strategy_id="test",
            strategy_name="Test Strategy",
            strategy_type="conservative",
            prompt_template="Test",
            risk_parameters=risk_params,
            max_positions=2,
        )

        performance = PerformanceMetrics(
            total_pnl=1000.0, win_rate=60.0, avg_win=150.0, avg_loss=-75.0, max_drawdown=-200.0
        )

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

        # Should be able to open position within limits
        assert account_context.can_open_new_position(1500.0)

        # Should not be able to open position exceeding available balance
        assert not account_context.can_open_new_position(9000.0)

        # Should not be able to open position exceeding max position size
        assert not account_context.can_open_new_position(2500.0)


class TestTradingContext:
    """Test TradingContext model validation."""

    def test_context_summary_generation(self):
        """Test trading context summary generation."""
        # Create minimal valid context components
        indicators = TechnicalIndicators(ema_20=48000.0, ema_50=47000.0, rsi=65.0, macd=100.0)

        market_context = MarketContext(
            current_price=48000.0,
            price_change_24h=1000.0,
            volume_24h=1000000.0,
            volatility=0.02,
            technical_indicators=indicators,
            price_history=[PricePoint(timestamp=datetime.now(timezone.utc), price=48000.0)],
        )

        risk_params = StrategyRiskParameters(
            max_risk_per_trade=2.0, max_daily_loss=5.0, stop_loss_percentage=1.5
        )

        strategy = TradingStrategy(
            strategy_id="test",
            strategy_name="Test Strategy",
            strategy_type="conservative",
            prompt_template="Test",
            risk_parameters=risk_params,
            is_active=True,
        )

        performance = PerformanceMetrics(
            total_pnl=1000.0, win_rate=60.0, avg_win=150.0, avg_loss=-75.0, max_drawdown=-200.0
        )

        account_context = AccountContext(
            account_id=1,
            balance_usd=10000.0,
            available_balance=8000.0,
            total_pnl=1000.0,
            recent_performance=performance,
            risk_exposure=20.0,
            max_position_size=2000.0,
            active_strategy=strategy,
        )

        risk_metrics = RiskMetrics(
            var_95=500.0, max_drawdown=1000.0, correlation_risk=15.0, concentration_risk=25.0
        )

        trading_context = TradingContext(
            symbol="BTCUSDT",
            account_id=1,
            market_data=market_context,
            account_state=account_context,
            risk_metrics=risk_metrics,
        )

        summary = trading_context.get_context_summary()

        assert summary["symbol"] == "BTCUSDT"
        assert summary["account_id"] == 1
        assert summary["current_price"] == 48000.0
        assert summary["strategy"] == "Test Strategy"
        assert "price_trend" in summary


class TestStrategyPerformance:
    """Test StrategyPerformance model and methods."""

    def test_performance_grade_calculation(self):
        """Test performance grade calculation."""
        # High-performing strategy
        high_performance = StrategyPerformance(
            strategy_id="high_performer",
            total_trades=100,
            winning_trades=75,
            losing_trades=25,
            win_rate=75.0,
            total_pnl=5000.0,
            avg_win=100.0,
            avg_loss=-50.0,
            max_win=500.0,
            max_loss=-200.0,
            max_drawdown=-300.0,
            sharpe_ratio=2.5,
            profit_factor=2.0,
            avg_trade_duration_hours=4.0,
            total_volume_traded=100000.0,
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc),
            period_days=30,
        )

        grade = high_performance.get_performance_grade()
        assert grade in ["A+", "A"]
        assert not high_performance.needs_attention()

    def test_roi_calculation(self):
        """Test ROI calculation."""
        performance = StrategyPerformance(
            strategy_id="test",
            total_trades=50,
            winning_trades=30,
            losing_trades=20,
            win_rate=60.0,
            total_pnl=2000.0,
            avg_win=100.0,
            avg_loss=-50.0,
            max_win=300.0,
            max_loss=-150.0,
            max_drawdown=-200.0,
            profit_factor=1.5,
            avg_trade_duration_hours=2.0,
            total_volume_traded=50000.0,
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc),
            period_days=30,
        )

        roi = performance.calculate_roi(10000.0)
        assert roi == 20.0  # 2000/10000 * 100

    def test_needs_attention_detection(self):
        """Test needs attention detection."""
        # Poor performing strategy
        poor_performance = StrategyPerformance(
            strategy_id="poor_performer",
            total_trades=50,
            winning_trades=10,
            losing_trades=40,
            win_rate=20.0,  # Very low win rate
            total_pnl=-1000.0,
            avg_win=50.0,
            avg_loss=-30.0,
            max_win=100.0,
            max_loss=-200.0,
            max_drawdown=-1500.0,  # High drawdown
            profit_factor=0.5,  # Low profit factor
            avg_trade_duration_hours=1.0,
            total_volume_traded=25000.0,
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc),
            period_days=30,
        )

        assert poor_performance.needs_attention()
        grade = poor_performance.get_performance_grade()
        assert grade in ["D", "F"]


class TestStrategyAssignment:
    """Test StrategyAssignment model."""

    def test_strategy_assignment_creation(self):
        """Test creating strategy assignment."""
        assignment = StrategyAssignment(
            account_id=1,
            strategy_id="conservative_swing",
            assigned_by="admin",
            previous_strategy_id="aggressive_scalp",
            switch_reason="Risk reduction requested",
        )

        assert assignment.account_id == 1
        assert assignment.strategy_id == "conservative_swing"
        assert assignment.is_active
        assert assignment.switch_reason == "Risk reduction requested"


class TestStrategyMetrics:
    """Test StrategyMetrics model."""

    def test_strategy_metrics_creation(self):
        """Test creating strategy metrics."""
        metrics = StrategyMetrics(
            strategy_id="test_strategy",
            account_id=1,
            current_positions=2,
            total_allocated=5000.0,
            unrealized_pnl=250.0,
            realized_pnl_today=100.0,
            trades_today=3,
            last_trade_time=datetime.now(timezone.utc),
            risk_utilization=45.0,
            cooldown_remaining=120,
        )

        assert metrics.strategy_id == "test_strategy"
        assert metrics.current_positions == 2
        assert metrics.risk_utilization == 45.0
        assert metrics.cooldown_remaining == 120


class TestStrategyAlert:
    """Test StrategyAlert model."""

    def test_strategy_alert_creation(self):
        """Test creating strategy alert."""
        alert = StrategyAlert(
            strategy_id="risky_strategy",
            account_id=1,
            alert_type="risk_limit_exceeded",
            severity="high",
            message="Daily loss limit exceeded",
            threshold_value=500.0,
            current_value=750.0,
        )

        assert alert.alert_type == "risk_limit_exceeded"
        assert alert.severity == "high"
        assert not alert.acknowledged
        assert alert.current_value == 750.0
