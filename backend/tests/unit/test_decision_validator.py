"""
Unit tests for Decision Validator Service.

Tests comprehensive validation including schema validation, business rules,
risk management checks, and fallback mechanisms.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.trading_decision import (
    AccountContext,
    MarketContext,
    OrderAdjustment,
    PerformanceMetrics,
    PositionAdjustment,
    PositionSummary,
    PricePoint,
    RiskMetrics,
    RiskValidationResult,
    StrategyRiskParameters,
    TechnicalIndicators,
    TechnicalIndicatorsSet,
    TradingContext,
    TradingDecision,
    TradingStrategy,
    ValidationResult,
)
from app.services.llm.decision_validator import DecisionValidator, get_decision_validator


class TestDecisionValidator:
    """Test DecisionValidator service."""

    @pytest.fixture
    def validator(self):
        """Create a fresh validator instance for each test."""
        return DecisionValidator()

    @pytest.fixture
    def sample_trading_context(self):
        """Create a sample trading context for testing."""
        indicators = TechnicalIndicators(
            interval=TechnicalIndicatorsSet(
                ema_20=[48000.0],
                ema_50=[47000.0],
                rsi=[65.0],
                macd=[100.0],
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
                bb_upper=[49500.0],
                bb_lower=[46500.0],
                bb_middle=[48000.0],
                atr=[550.0],
            ),
        )

        market_context = MarketContext(
            current_price=48000.0,
            price_change_24h=1000.0,
            volume_24h=1000000.0,
            funding_rate=0.01,
            open_interest=50000000.0,
            volatility=0.02,
            technical_indicators=indicators,
            price_history=[
                PricePoint(timestamp=datetime.now(timezone.utc), price=47000.0),
                PricePoint(timestamp=datetime.now(timezone.utc), price=47500.0),
                PricePoint(timestamp=datetime.now(timezone.utc), price=48000.0),
            ],
        )

        risk_params = StrategyRiskParameters(
            max_risk_per_trade=15.0,  # Increased to allow test allocations
            max_daily_loss=20.0,
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
            max_positions=3,
            is_active=True,
        )

        performance = PerformanceMetrics(
            total_pnl=1000.0,
            win_rate=60.0,
            avg_win=150.0,
            avg_loss=-75.0,
            max_drawdown=-200.0,
            sharpe_ratio=1.5,
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

        risk_metrics = RiskMetrics(
            var_95=500.0, max_drawdown=1000.0, correlation_risk=15.0, concentration_risk=25.0
        )

        return TradingContext(
            symbol="BTCUSDT",
            account_id=1,
            market_data=market_context,
            account_state=account_context,
            risk_metrics=risk_metrics,
        )

    @pytest.fixture
    def valid_buy_decision(self):
        """Create a valid buy decision for testing."""
        return TradingDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=1000.0,
            tp_price=50000.0,
            sl_price=46000.0,
            exit_plan="Take profit at resistance, stop loss at support",
            rationale="Strong bullish momentum with RSI oversold",
            confidence=85.0,
            risk_level="medium",
        )

    @pytest.mark.asyncio
    async def test_valid_decision_passes_validation(
        self, validator, valid_buy_decision, sample_trading_context
    ):
        """Test that a valid decision passes all validation checks."""
        result = await validator.validate_decision(valid_buy_decision, sample_trading_context)

        assert result.is_valid
        assert len(result.errors) == 0
        assert result.validation_time_ms > 0
        assert "schema_validation" in result.rules_checked

    @pytest.mark.asyncio
    async def test_schema_validation_catches_invalid_confidence(
        self, validator, sample_trading_context
    ):
        """Test schema validation catches invalid confidence values."""
        # Test with Pydantic validation error handling
        try:
            invalid_decision = TradingDecision(
                asset="BTCUSDT",
                action="buy",
                allocation_usd=1000.0,
                exit_plan="Test",
                rationale="Test",
                confidence=150.0,  # Invalid: > 100
                risk_level="medium",
            )
            # If we get here, Pydantic didn't catch it, so test our validation
            result = await validator.validate_decision(invalid_decision, sample_trading_context)
            assert not result.is_valid
        except ValidationError:
            # Pydantic caught it as expected
            assert True

    @pytest.mark.asyncio
    async def test_schema_validation_requires_position_adjustment(
        self, validator, sample_trading_context
    ):
        """Test schema validation requires position_adjustment for adjust_position action."""
        invalid_decision = TradingDecision(
            asset="BTCUSDT",
            action="adjust_position",
            allocation_usd=500.0,
            exit_plan="Adjust position",
            rationale="Market changed",
            confidence=70.0,
            risk_level="low",
        )

        result = await validator.validate_decision(invalid_decision, sample_trading_context)

        assert not result.is_valid
        assert any("position_adjustment is required" in error for error in result.errors)

    @pytest.mark.asyncio
    async def test_allocation_validation_against_available_balance(
        self, validator, sample_trading_context
    ):
        """Test allocation validation against available balance."""
        excessive_decision = TradingDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=9000.0,  # Exceeds available balance of 8000
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        result = await validator.validate_decision(excessive_decision, sample_trading_context)

        assert not result.is_valid
        assert any("exceeds available balance" in error for error in result.errors)

    @pytest.mark.asyncio
    async def test_price_logic_validation_buy_order(self, validator, sample_trading_context):
        """Test price logic validation for buy orders."""
        invalid_price_decision = TradingDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=1000.0,
            tp_price=45000.0,  # Invalid: TP should be higher than current (48000)
            sl_price=50000.0,  # Invalid: SL should be lower than current
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        result = await validator.validate_decision(invalid_price_decision, sample_trading_context)

        assert not result.is_valid
        assert any("Take-profit price must be higher" in error for error in result.errors)
        assert any("Stop-loss price must be lower" in error for error in result.errors)

    @pytest.mark.asyncio
    async def test_position_size_validation(self, validator, sample_trading_context):
        """Test position size validation against maximum allowed."""
        oversized_decision = TradingDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=2500.0,  # Exceeds max position size of 2000
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        result = await validator.validate_decision(oversized_decision, sample_trading_context)

        assert not result.is_valid
        assert any("exceeds maximum allowed" in error for error in result.errors)

    @pytest.mark.asyncio
    async def test_position_limit_validation(self, validator, sample_trading_context):
        """Test position limit validation when max positions reached."""
        # Add positions to reach the limit
        sample_trading_context.account_state.open_positions = [
            PositionSummary(
                symbol="ETHUSDT",
                side="long",
                size=1000.0,
                entry_price=3000.0,
                current_price=3100.0,
                unrealized_pnl=100.0,
                percentage_pnl=3.33,
            ),
            PositionSummary(
                symbol="SOLUSDT",
                side="long",
                size=500.0,
                entry_price=100.0,
                current_price=105.0,
                unrealized_pnl=25.0,
                percentage_pnl=5.0,
            ),
            PositionSummary(
                symbol="ADAUSDT",
                side="short",
                size=2000.0,
                entry_price=0.5,
                current_price=0.48,
                unrealized_pnl=40.0,
                percentage_pnl=4.0,
            ),
        ]

        new_position_decision = TradingDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=1000.0,
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        result = await validator.validate_decision(new_position_decision, sample_trading_context)

        assert not result.is_valid
        assert any("maximum positions" in error for error in result.errors)

    @pytest.mark.asyncio
    async def test_adjust_position_without_existing_position(
        self, validator, sample_trading_context
    ):
        """Test that adjust_position fails when no existing position exists."""
        adjust_decision = TradingDecision(
            asset="BTCUSDT",
            action="adjust_position",
            allocation_usd=0.0,
            position_adjustment=PositionAdjustment(
                adjustment_type="increase", adjustment_amount_usd=500.0
            ),
            exit_plan="Increase position",
            rationale="Market favorable",
            confidence=70.0,
            risk_level="low",
        )

        result = await validator.validate_decision(adjust_decision, sample_trading_context)

        assert not result.is_valid
        assert any("no existing position" in error for error in result.errors)

    @pytest.mark.asyncio
    async def test_risk_exposure_validation(self, validator, sample_trading_context):
        """Test risk exposure validation."""
        # Set high risk exposure
        sample_trading_context.account_state.risk_exposure = 90.0

        high_risk_decision = TradingDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=1500.0,
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="high",
        )

        result = await validator.validate_decision(high_risk_decision, sample_trading_context)

        # Should have warnings or errors about high risk
        has_risk_issue = len(result.warnings) > 0 or any(
            "risk" in error.lower() for error in result.errors
        )
        assert has_risk_issue

    @pytest.mark.asyncio
    async def test_correlation_risk_validation(self, validator, sample_trading_context):
        """Test correlation risk validation."""
        # Add existing BTC positions to create correlation risk
        sample_trading_context.account_state.open_positions = [
            PositionSummary(
                symbol="BTCEUR",
                side="long",
                size=1000.0,
                entry_price=40000.0,
                current_price=41000.0,
                unrealized_pnl=100.0,
                percentage_pnl=2.5,
            ),
            PositionSummary(
                symbol="BTCGBP",
                side="long",
                size=500.0,
                entry_price=35000.0,
                current_price=36000.0,
                unrealized_pnl=50.0,
                percentage_pnl=2.86,
            ),
        ]

        btc_decision = TradingDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=1000.0,
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        result = await validator.validate_decision(btc_decision, sample_trading_context)

        # Should have correlation risk warning
        assert any("correlation risk" in warning.lower() for warning in result.warnings)

    @pytest.mark.asyncio
    async def test_concentration_risk_validation(self, validator, sample_trading_context):
        """Test concentration risk validation."""
        # Create high concentration scenario
        high_concentration_decision = TradingDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=7000.0,  # High concentration relative to balance
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        result = await validator.validate_decision(
            high_concentration_decision, sample_trading_context
        )

        # Should have concentration risk warning or error
        has_concentration_issue = any(
            "concentration" in (error + " " + " ".join(result.warnings)).lower()
            for error in result.errors
        )
        assert has_concentration_issue

    @pytest.mark.asyncio
    async def test_apply_risk_checks(self, validator, sample_trading_context):
        """Test comprehensive risk checks."""
        decision = TradingDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=1000.0,
            exit_plan="Test",
            rationale="Test",
            confidence=30.0,  # Low confidence
            risk_level="high",  # High risk
        )

        risk_result = await validator.apply_risk_checks(
            decision, sample_trading_context.account_state
        )

        assert isinstance(risk_result, RiskValidationResult)
        assert risk_result.risk_score > 0
        assert len(risk_result.risk_factors) > 0
        assert "Low confidence decision" in risk_result.risk_factors
        assert "Decision marked as high risk" in risk_result.risk_factors

    @pytest.mark.asyncio
    async def test_create_fallback_decision(self, validator, sample_trading_context):
        """Test fallback decision creation."""
        original_decision = TradingDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=10000.0,  # Invalid amount
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        validation_errors = ["Allocation exceeds available balance"]

        fallback = await validator.create_fallback_decision(
            original_decision, sample_trading_context, validation_errors
        )

        assert fallback.action == "hold"
        assert fallback.allocation_usd == 0.0
        assert fallback.confidence == 25.0
        assert fallback.risk_level == "low"
        assert "Fallback decision" in fallback.rationale

    @pytest.mark.asyncio
    async def test_validation_metrics_tracking(
        self, validator, valid_buy_decision, sample_trading_context
    ):
        """Test validation metrics tracking."""
        # Perform several validations
        await validator.validate_decision(valid_buy_decision, sample_trading_context)

        # Create an invalid decision
        invalid_decision = TradingDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=20000.0,  # Exceeds balance
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        await validator.validate_decision(invalid_decision, sample_trading_context)

        metrics = await validator.get_validation_metrics()

        assert metrics["total_validations"] == 2
        assert metrics["successful_validations"] == 1
        assert metrics["failed_validations"] == 1
        assert metrics["success_rate"] == 50.0
        assert metrics["avg_validation_time_ms"] > 0
        assert len(metrics["validation_errors"]) > 0

    @pytest.mark.asyncio
    async def test_metrics_reset(self, validator, valid_buy_decision, sample_trading_context):
        """Test metrics reset functionality."""
        # Perform validation to generate metrics
        await validator.validate_decision(valid_buy_decision, sample_trading_context)

        # Reset metrics
        await validator.reset_metrics()

        metrics = await validator.get_validation_metrics()

        assert metrics["total_validations"] == 0
        assert metrics["successful_validations"] == 0
        assert metrics["failed_validations"] == 0
        assert metrics["avg_validation_time_ms"] == 0.0
        assert len(metrics["validation_errors"]) == 0

    @pytest.mark.asyncio
    async def test_order_adjustment_validation(self, validator, sample_trading_context):
        """Test order adjustment validation."""
        # Add existing position
        sample_trading_context.account_state.open_positions = [
            PositionSummary(
                symbol="BTCUSDT",
                side="long",
                size=1000.0,
                entry_price=47000.0,
                current_price=48000.0,
                unrealized_pnl=100.0,
                percentage_pnl=2.13,
            )
        ]

        valid_order_adjustment = TradingDecision(
            asset="BTCUSDT",
            action="adjust_orders",
            allocation_usd=0.0,
            order_adjustment=OrderAdjustment(adjust_tp=True, new_tp_price=50000.0),
            exit_plan="Adjust take profit",
            rationale="Price moved favorably",
            confidence=80.0,
            risk_level="low",
        )

        result = await validator.validate_decision(valid_order_adjustment, sample_trading_context)

        assert result.is_valid

    @pytest.mark.asyncio
    async def test_strategy_specific_validation(self, validator, sample_trading_context):
        """Test strategy-specific validation rules."""
        # Test trade that exceeds strategy risk per trade
        excessive_risk_decision = TradingDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=2000.0,  # 20% of 10k balance, exceeds 15% strategy limit
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        result = await validator.validate_decision(excessive_risk_decision, sample_trading_context)

        assert not result.is_valid
        assert any("strategy limit" in error for error in result.errors)

    @pytest.mark.asyncio
    async def test_hold_action_validation(self, validator, sample_trading_context):
        """Test validation of hold action."""
        hold_decision = TradingDecision(
            asset="BTCUSDT",
            action="hold",
            allocation_usd=0.0,  # Should be 0 for hold
            exit_plan="Wait for better entry",
            rationale="Market conditions unclear",
            confidence=60.0,
            risk_level="low",
        )

        result = await validator.validate_decision(hold_decision, sample_trading_context)

        assert result.is_valid

        # Test invalid hold with non-zero allocation
        invalid_hold = TradingDecision(
            asset="BTCUSDT",
            action="hold",
            allocation_usd=1000.0,  # Should be 0 for hold
            exit_plan="Wait",
            rationale="Test",
            confidence=60.0,
            risk_level="low",
        )

        result = await validator.validate_decision(invalid_hold, sample_trading_context)

        assert not result.is_valid
        assert any("should be 0 for hold action" in error for error in result.errors)

    def test_get_decision_validator_singleton(self):
        """Test that get_decision_validator returns singleton instance."""
        validator1 = get_decision_validator()
        validator2 = get_decision_validator()

        assert validator1 is validator2
        assert isinstance(validator1, DecisionValidator)

    @pytest.mark.asyncio
    async def test_validation_error_handling(self, validator, sample_trading_context):
        """Test validation handles unexpected errors gracefully."""
        # Create a decision that should cause validation errors
        problematic_decision = TradingDecision(
            asset="INVALID/PAIR",  # Potentially problematic asset symbol
            action="buy",
            allocation_usd=50000.0,  # Exceeds available balance significantly
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        result = await validator.validate_decision(problematic_decision, sample_trading_context)

        # Should handle gracefully and return validation result
        assert isinstance(result, ValidationResult)
        # This should fail validation due to excessive allocation
        assert not result.is_valid
        assert result.validation_time_ms > 0

    @pytest.mark.asyncio
    async def test_risk_reward_ratio_warning(self, validator, sample_trading_context):
        """Test risk/reward ratio warning generation."""
        poor_ratio_decision = TradingDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=1000.0,
            tp_price=48500.0,  # Small profit target
            sl_price=46000.0,  # Large stop loss
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        result = await validator.validate_decision(poor_ratio_decision, sample_trading_context)

        # Should have warning about poor risk/reward ratio
        assert any("risk/reward ratio" in warning.lower() for warning in result.warnings)

    @pytest.mark.asyncio
    async def test_large_allocation_warning(self, validator, sample_trading_context):
        """Test large allocation warning generation."""
        large_allocation_decision = TradingDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=5000.0,  # More than 50% of available balance
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        result = await validator.validate_decision(
            large_allocation_decision, sample_trading_context
        )

        # Should have warning about large allocation
        assert any("large allocation" in warning.lower() for warning in result.warnings)
