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
        from app.schemas.trading_decision import AssetMarketData

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

        # Create asset market data for BTCUSDT
        btc_asset_data = AssetMarketData(
            symbol="BTCUSDT",
            current_price=48000.0,
            price_change_24h=1000.0,
            volume_24h=1000000.0,
            funding_rate=0.01,
            open_interest=50000000.0,
            volatility=0.02,
            technical_indicators=indicators,
            price_history=[
                PricePoint(timestamp=datetime.now(timezone.utc), price=47000.0, volume=1000.0),
                PricePoint(timestamp=datetime.now(timezone.utc), price=47500.0, volume=1000.0),
                PricePoint(timestamp=datetime.now(timezone.utc), price=48000.0, volume=1000.0),
            ],
        )

        # Create asset market data for ETHUSDT
        eth_asset_data = AssetMarketData(
            symbol="ETHUSDT",
            current_price=3000.0,
            price_change_24h=100.0,
            volume_24h=500000.0,
            funding_rate=0.012,
            open_interest=25000000.0,
            volatility=0.025,
            technical_indicators=indicators,
            price_history=[
                PricePoint(timestamp=datetime.now(timezone.utc), price=2900.0, volume=5000.0),
                PricePoint(timestamp=datetime.now(timezone.utc), price=2950.0, volume=5000.0),
                PricePoint(timestamp=datetime.now(timezone.utc), price=3000.0, volume=5000.0),
            ],
        )

        market_context = MarketContext(
            assets={"BTCUSDT": btc_asset_data, "ETHUSDT": eth_asset_data},
            market_sentiment="neutral",
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
            symbols=["BTCUSDT", "ETHUSDT"],
            account_id=1,
            timeframes=["1h", "4h"],
            market_data=market_context,
            account_state=account_context,
            risk_metrics=risk_metrics,
            recent_trades={"BTCUSDT": []},
        )

    @pytest.fixture
    def valid_buy_decision(self):
        """Create a valid multi-asset buy decision for testing."""
        from app.schemas.trading_decision import AssetDecision

        return TradingDecision(
            decisions=[
                AssetDecision(
                    asset="BTCUSDT",
                    action="buy",
                    allocation_usd=150.0,  # 3% of 5k, well below 15% limit
                    tp_price=50000.0,
                    sl_price=47000.0,
                    exit_plan="Take profit at resistance",
                    rationale="Strong bullish momentum",
                    confidence=85.0,
                    risk_level="low",
                ),
                AssetDecision(
                    asset="ETHUSDT",
                    action="buy",
                    allocation_usd=100.0,  # 2% of 5k
                    tp_price=3200.0,
                    sl_price=2900.0,
                    exit_plan="Take profit at resistance",
                    rationale="Strong bullish momentum",
                    confidence=85.0,
                    risk_level="low",
                ),
            ],
            portfolio_rationale="Overall bullish market conditions favor long positions",
            total_allocation_usd=250.0,
            portfolio_risk_level="low",
        )

    @pytest.mark.asyncio
    async def test_valid_decision_passes_validation(
        self, validator, valid_buy_decision, sample_trading_context
    ):
        """Test that a valid decision passes all validation checks."""
        # Clear any existing positions to test the decision in isolation
        sample_trading_context.account_state.open_positions = []

        result = await validator.validate_decision(valid_buy_decision, sample_trading_context)

        assert result.is_valid, f"Validation failed with errors: {result.errors}"
        assert len(result.errors) == 0
        assert result.validation_time_ms > 0
        assert "multi_asset_schema_validation" in result.rules_checked
        assert "portfolio_allocation_validation" in result.rules_checked
        assert "allocation_validation" in result.rules_checked
        assert "price_logic_validation" in result.rules_checked
        assert "position_size_validation" in result.rules_checked
        assert "leverage_validation" in result.rules_checked
        assert "action_requirements_validation" in result.rules_checked
        assert "strategy_specific_validation" in result.rules_checked
        assert "risk_exposure_validation" in result.rules_checked
        assert "position_limit_validation" in result.rules_checked
        assert "daily_loss_validation" in result.rules_checked
        assert "correlation_validation" in result.rules_checked
        assert "concentration_validation" in result.rules_checked

    @pytest.mark.asyncio
    async def test_schema_validation_catches_invalid_confidence(
        self, validator, sample_trading_context
    ):
        """Test schema validation catches invalid confidence values."""
        from app.schemas.trading_decision import AssetDecision

        # Test with Pydantic validation error handling
        try:
            invalid_asset_decision = AssetDecision(
                asset="BTCUSDT",
                action="buy",
                allocation_usd=1000.0,
                exit_plan="Test",
                rationale="Test",
                confidence=150.0,  # Invalid: > 100
                risk_level="medium",
            )
            invalid_decision = TradingDecision(
                decisions=[invalid_asset_decision],
                portfolio_rationale="Test",
                total_allocation_usd=1000.0,
                portfolio_risk_level="medium",
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
        from app.schemas.trading_decision import AssetDecision

        invalid_asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="adjust_position",
            allocation_usd=500.0,
            exit_plan="Adjust position",
            rationale="Market changed",
            confidence=70.0,
            risk_level="low",
        )

        invalid_decision = TradingDecision(
            decisions=[invalid_asset_decision],
            portfolio_rationale="Adjust position",
            total_allocation_usd=500.0,
            portfolio_risk_level="low",
        )

        result = await validator.validate_decision(invalid_decision, sample_trading_context)

        assert not result.is_valid
        assert any("position_adjustment is required" in error for error in result.errors)

    @pytest.mark.asyncio
    async def test_allocation_validation_against_available_balance(
        self, validator, sample_trading_context
    ):
        """Test allocation validation against available balance."""
        from app.schemas.trading_decision import AssetDecision

        excessive_asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=9000.0,  # Exceeds available balance of 8000
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        excessive_decision = TradingDecision(
            decisions=[excessive_asset_decision],
            portfolio_rationale="Test",
            total_allocation_usd=9000.0,
            portfolio_risk_level="medium",
        )

        result = await validator.validate_decision(excessive_decision, sample_trading_context)

        assert not result.is_valid
        assert any("exceeds available balance" in error for error in result.errors)

    @pytest.mark.asyncio
    async def test_price_logic_validation_buy_order(self, validator, sample_trading_context):
        """Test price logic validation for buy orders."""
        from app.schemas.trading_decision import AssetDecision

        invalid_price_asset_decision = AssetDecision(
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

        invalid_price_decision = TradingDecision(
            decisions=[invalid_price_asset_decision],
            portfolio_rationale="Test",
            total_allocation_usd=1000.0,
            portfolio_risk_level="medium",
        )

        result = await validator.validate_decision(invalid_price_decision, sample_trading_context)

        assert not result.is_valid
        assert any("Take-profit price must be higher" in error for error in result.errors)
        assert any("Stop-loss price must be lower" in error for error in result.errors)

    @pytest.mark.asyncio
    async def test_position_size_validation(self, validator, sample_trading_context):
        """Test position size validation against maximum allowed."""
        from app.schemas.trading_decision import AssetDecision

        oversized_asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=2500.0,  # Exceeds max position size of 2000
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        oversized_decision = TradingDecision(
            decisions=[oversized_asset_decision],
            portfolio_rationale="Test",
            total_allocation_usd=2500.0,
            portfolio_risk_level="medium",
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

        from app.schemas.trading_decision import AssetDecision

        new_position_asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=1000.0,
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        new_position_decision = TradingDecision(
            decisions=[
                new_position_asset_decision,
                AssetDecision(
                    asset="ETHUSDT",
                    action="hold",
                    allocation_usd=0.0,
                    exit_plan="Wait for confirmation",
                    rationale="Neutral momentum",
                    confidence=70.0,
                    risk_level="low",
                ),
            ],
            portfolio_rationale="Test",
            total_allocation_usd=1000.0,
            portfolio_risk_level="medium",
        )

        result = await validator.validate_decision(new_position_decision, sample_trading_context)

        assert not result.is_valid
        assert any("would exceed maximum" in error for error in result.errors)

    @pytest.mark.asyncio
    async def test_adjust_position_without_existing_position(
        self, validator, sample_trading_context
    ):
        """Test that adjust_position fails when no existing position exists."""
        from app.schemas.trading_decision import AssetDecision

        adjust_asset_decision = AssetDecision(
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

        adjust_decision = TradingDecision(
            decisions=[adjust_asset_decision],
            portfolio_rationale="Adjust position",
            total_allocation_usd=0.0,
            portfolio_risk_level="low",
        )

        result = await validator.validate_decision(adjust_decision, sample_trading_context)

        assert not result.is_valid
        assert any("no existing position" in error for error in result.errors)

    @pytest.mark.asyncio
    async def test_risk_exposure_validation(self, validator, sample_trading_context):
        """Test risk exposure validation."""
        from app.schemas.trading_decision import AssetDecision

        # Set high risk exposure
        sample_trading_context.account_state.risk_exposure = 90.0

        high_risk_asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=1500.0,
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="high",
        )

        high_risk_decision = TradingDecision(
            decisions=[high_risk_asset_decision],
            portfolio_rationale="Test",
            total_allocation_usd=1500.0,
            portfolio_risk_level="high",
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
            PositionSummary(
                symbol="ETHBTC",
                side="long",
                size=10.0,
                entry_price=0.06,
                current_price=0.062,
                unrealized_pnl=200.0,
                percentage_pnl=3.33,
            ),
        ]

        from app.schemas.trading_decision import AssetDecision

        btc_asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=1000.0,
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        btc_decision = TradingDecision(
            decisions=[
                btc_asset_decision,
                AssetDecision(
                    asset="ETHUSDT",
                    action="hold",
                    allocation_usd=0.0,
                    exit_plan="Wait for confirmation",
                    rationale="Neutral momentum",
                    confidence=70.0,
                    risk_level="low",
                ),
            ],
            portfolio_rationale="Test",
            total_allocation_usd=1000.0,
            portfolio_risk_level="medium",
        )

        result = await validator.validate_decision(btc_decision, sample_trading_context)

        # Should have correlation risk warning
        assert any("High correlation risk" in warning for warning in result.warnings)

    @pytest.mark.asyncio
    async def test_concentration_risk_validation(self, validator, sample_trading_context):
        """Test concentration risk validation."""
        from app.schemas.trading_decision import AssetDecision

        # Create high concentration scenario
        high_concentration_asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=7000.0,  # High concentration relative to balance
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        high_concentration_decision = TradingDecision(
            decisions=[high_concentration_asset_decision],
            portfolio_rationale="Test",
            total_allocation_usd=7000.0,
            portfolio_risk_level="medium",
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
        from app.schemas.trading_decision import AssetDecision

        asset_decision_1 = AssetDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=1000.0,
            exit_plan="Test",
            rationale="Test",
            confidence=30.0,  # Low confidence
            risk_level="high",  # High risk
        )

        asset_decision_2 = AssetDecision(
            asset="ETHUSDT",
            action="buy",
            allocation_usd=500.0,
            exit_plan="Test",
            rationale="Test",
            confidence=40.0,  # Low confidence
            risk_level="high",  # High risk
        )

        decision = TradingDecision(
            decisions=[asset_decision_1, asset_decision_2],
            portfolio_rationale="Test",
            total_allocation_usd=1500.0,
            portfolio_risk_level="high",
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
        from app.schemas.trading_decision import AssetDecision

        original_asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=10000.0,  # Invalid amount
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        original_decision = TradingDecision(
            decisions=[original_asset_decision],
            portfolio_rationale="Test",
            total_allocation_usd=10000.0,
            portfolio_risk_level="medium",
        )

        validation_errors = ["Allocation exceeds available balance"]

        fallback = await validator.create_fallback_decision(
            original_decision, sample_trading_context, validation_errors
        )

        # Fallback should be a hold decision with zero allocation
        assert len(fallback.decisions) > 0
        first_decision = fallback.decisions[0]
        assert first_decision.action == "hold"
        assert first_decision.allocation_usd == 0.0
        assert first_decision.confidence == 25.0
        assert first_decision.risk_level == "low"
        assert "Fallback decision" in first_decision.rationale

    @pytest.mark.asyncio
    async def test_validation_metrics_tracking(
        self, validator, valid_buy_decision, sample_trading_context
    ):
        """Test validation metrics tracking."""
        # Perform several validations
        await validator.validate_decision(valid_buy_decision, sample_trading_context)

        # Create an invalid decision
        from app.schemas.trading_decision import AssetDecision

        invalid_asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=20000.0,  # Exceeds balance
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        invalid_decision = TradingDecision(
            decisions=[invalid_asset_decision],
            portfolio_rationale="Test",
            total_allocation_usd=20000.0,
            portfolio_risk_level="medium",
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

        from app.schemas.trading_decision import AssetDecision

        valid_order_adjustment_asset = AssetDecision(
            asset="BTCUSDT",
            action="adjust_orders",
            allocation_usd=0.0,
            order_adjustment=OrderAdjustment(adjust_tp=True, new_tp_price=50000.0),
            exit_plan="Adjust take profit",
            rationale="Price moved favorably",
            confidence=80.0,
            risk_level="low",
        )

        valid_order_adjustment = TradingDecision(
            decisions=[
                valid_order_adjustment_asset,
                AssetDecision(
                    asset="ETHUSDT",
                    action="hold",
                    allocation_usd=0.0,
                    exit_plan="Wait for confirmation",
                    rationale="Neutral momentum",
                    confidence=70.0,
                    risk_level="low",
                ),
            ],
            portfolio_rationale="Adjust orders",
            total_allocation_usd=0.0,
            portfolio_risk_level="low",
        )

        result = await validator.validate_decision(valid_order_adjustment, sample_trading_context)

        assert result.is_valid, f"Validation failed with errors: {result.errors}"

    @pytest.mark.asyncio
    async def test_strategy_specific_validation(self, validator, sample_trading_context):
        """Test strategy-specific validation rules with correct risk calculation.

        With the new logic, risk is calculated as: allocation × stop_loss_percentage.
        With $10,000 balance and 15% max risk per trade = $1,500 max risk.
        $2,000 allocation with 80% SL = $1,600 actual risk (exceeds $1,500 limit).
        """
        from app.schemas.trading_decision import AssetDecision

        excessive_risk_asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=2000.0,
            sl_price=9600.0,  # 80% below current price (wide stop loss)
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        excessive_risk_decision = TradingDecision(
            decisions=[
                excessive_risk_asset_decision,
                AssetDecision(
                    asset="ETHUSDT",
                    action="hold",
                    allocation_usd=0.0,
                    exit_plan="Wait for confirmation",
                    rationale="Neutral momentum",
                    confidence=70.0,
                    risk_level="low",
                ),
            ],
            portfolio_rationale="Test",
            total_allocation_usd=2000.0,
            portfolio_risk_level="medium",
        )

        result = await validator.validate_decision(excessive_risk_decision, sample_trading_context)

        assert not result.is_valid
        assert any("exceeds strategy limit" in error for error in result.errors)

    @pytest.mark.asyncio
    async def test_hold_action_validation(self, validator, sample_trading_context):
        """Test validation of hold action."""
        from app.schemas.trading_decision import AssetDecision

        hold_asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="hold",
            allocation_usd=0.0,  # Should be 0 for hold
            exit_plan="Wait for better entry",
            rationale="Market conditions unclear",
            confidence=60.0,
            risk_level="low",
        )

        hold_decision = TradingDecision(
            decisions=[hold_asset_decision],
            portfolio_rationale="Wait for better entry",
            total_allocation_usd=0.0,
            portfolio_risk_level="low",
        )

        result = await validator.validate_decision(hold_decision, sample_trading_context)

        assert result.is_valid

        # Test invalid hold with non-zero allocation
        invalid_hold_asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="hold",
            allocation_usd=1000.0,  # Should be 0 for hold
            exit_plan="Wait",
            rationale="Test",
            confidence=60.0,
            risk_level="low",
        )

        invalid_hold = TradingDecision(
            decisions=[invalid_hold_asset_decision],
            portfolio_rationale="Wait",
            total_allocation_usd=1000.0,
            portfolio_risk_level="low",
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
        from app.schemas.trading_decision import AssetDecision

        problematic_asset_decision = AssetDecision(
            asset="INVALID/PAIR",  # Potentially problematic asset symbol
            action="buy",
            allocation_usd=50000.0,  # Exceeds available balance significantly
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        problematic_decision = TradingDecision(
            decisions=[problematic_asset_decision],
            portfolio_rationale="Test",
            total_allocation_usd=50000.0,
            portfolio_risk_level="medium",
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
        from app.schemas.trading_decision import AssetDecision

        poor_ratio_asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=1000.0,
            tp_price=48100.0,  # Very small profit target
            sl_price=46000.0,  # Large stop loss
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        poor_ratio_decision = TradingDecision(
            decisions=[
                poor_ratio_asset_decision,
                AssetDecision(
                    asset="ETHUSDT",
                    action="hold",
                    allocation_usd=0.0,
                    exit_plan="Wait for confirmation",
                    rationale="Neutral momentum",
                    confidence=70.0,
                    risk_level="low",
                ),
            ],
            portfolio_rationale="Test",
            total_allocation_usd=1000.0,
            portfolio_risk_level="medium",
        )

        result = await validator.validate_decision(poor_ratio_decision, sample_trading_context)

        # Should have warning about poor risk/reward ratio
        assert any("less than 1:1" in warning for warning in result.warnings)

    @pytest.mark.asyncio
    async def test_large_allocation_warning(self, validator, sample_trading_context):
        """Test large allocation warning generation."""
        from app.schemas.trading_decision import AssetDecision

        large_allocation_asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=7000.0,  # More than 50% of available balance
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        large_allocation_decision = TradingDecision(
            decisions=[
                large_allocation_asset_decision,
                AssetDecision(
                    asset="ETHUSDT",
                    action="hold",
                    allocation_usd=0.0,
                    exit_plan="Wait for confirmation",
                    rationale="Neutral momentum",
                    confidence=70.0,
                    risk_level="low",
                ),
            ],
            portfolio_rationale="Test",
            total_allocation_usd=7000.0,
            portfolio_risk_level="medium",
        )

        result = await validator.validate_decision(
            large_allocation_decision, sample_trading_context
        )

        # Should have warning about large allocation
        assert any("more than 50% of available balance" in warning for warning in result.warnings)


class TestCalculateStopLossPercentage:
    """Test _calculate_stop_loss_percentage helper method."""

    @pytest.fixture
    def validator(self):
        """Create a fresh validator instance for each test."""
        return DecisionValidator()

    def test_buy_action_with_valid_sl(self, validator):
        """Test stop loss percentage calculation for buy action."""
        from app.schemas.trading_decision import AssetDecision

        asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=1000.0,
            sl_price=47000.0,  # $1,000 below current price
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        sl_pct = validator._calculate_stop_loss_percentage(asset_decision, 48000.0)

        assert sl_pct is not None
        assert abs(sl_pct - 2.0833) < 0.01  # (48000-47000)/48000 * 100

    def test_sell_action_with_valid_sl(self, validator):
        """Test stop loss percentage calculation for sell action."""
        from app.schemas.trading_decision import AssetDecision

        asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="sell",
            allocation_usd=1000.0,
            sl_price=49000.0,  # $1,000 above current price
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        sl_pct = validator._calculate_stop_loss_percentage(asset_decision, 48000.0)

        assert sl_pct is not None
        assert abs(sl_pct - 2.0833) < 0.01  # (49000-48000)/48000 * 100

    def test_no_sl_price_returns_none(self, validator):
        """Test that None is returned when sl_price is not set."""
        from app.schemas.trading_decision import AssetDecision

        asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=1000.0,
            sl_price=None,
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        sl_pct = validator._calculate_stop_loss_percentage(asset_decision, 48000.0)

        assert sl_pct is None

    def test_hold_action_returns_none(self, validator):
        """Test that None is returned for hold action."""
        from app.schemas.trading_decision import AssetDecision

        asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="hold",
            allocation_usd=0.0,
            sl_price=47000.0,
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="low",
        )

        sl_pct = validator._calculate_stop_loss_percentage(asset_decision, 48000.0)

        assert sl_pct is None

    def test_zero_price_returns_none(self, validator):
        """Test that None is returned when current price is zero (defensive programming)."""
        from app.schemas.trading_decision import AssetDecision

        asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=1000.0,
            sl_price=47000.0,
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        sl_pct = validator._calculate_stop_loss_percentage(asset_decision, 0.0)

        assert sl_pct is None

    def test_negative_price_returns_none(self, validator):
        """Test that None is returned when current price is negative (defensive programming)."""
        from app.schemas.trading_decision import AssetDecision

        asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=1000.0,
            sl_price=47000.0,
            exit_plan="Test",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        sl_pct = validator._calculate_stop_loss_percentage(asset_decision, -100.0)

        assert sl_pct is None


class TestRiskPerTradeValidation:
    """Test risk per trade validation with correct stop-loss-based calculation."""

    @pytest.fixture
    def validator(self):
        """Create a fresh validator instance for each test."""
        return DecisionValidator()

    @pytest.fixture
    def sample_trading_context(self):
        """Create a sample trading context for testing."""
        from app.schemas.trading_decision import AssetMarketData

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

        btc_asset_data = AssetMarketData(
            symbol="BTCUSDT",
            current_price=48000.0,
            price_change_24h=1000.0,
            volume_24h=1000000.0,
            funding_rate=0.01,
            open_interest=50000000.0,
            volatility=0.02,
            technical_indicators=indicators,
            price_history=[
                PricePoint(timestamp=datetime.now(timezone.utc), price=47000.0, volume=1000.0),
                PricePoint(timestamp=datetime.now(timezone.utc), price=47500.0, volume=1000.0),
                PricePoint(timestamp=datetime.now(timezone.utc), price=48000.0, volume=1000.0),
            ],
        )

        eth_asset_data = AssetMarketData(
            symbol="ETHUSDT",
            current_price=3000.0,
            price_change_24h=100.0,
            volume_24h=500000.0,
            funding_rate=0.012,
            open_interest=25000000.0,
            volatility=0.025,
            technical_indicators=indicators,
            price_history=[
                PricePoint(timestamp=datetime.now(timezone.utc), price=2900.0, volume=5000.0),
                PricePoint(timestamp=datetime.now(timezone.utc), price=2950.0, volume=5000.0),
                PricePoint(timestamp=datetime.now(timezone.utc), price=3000.0, volume=5000.0),
            ],
        )

        market_context = MarketContext(
            assets={"BTCUSDT": btc_asset_data, "ETHUSDT": eth_asset_data},
            market_sentiment="neutral",
        )

        risk_params = StrategyRiskParameters(
            max_risk_per_trade=2.0,  # 2% of balance = $200 max risk for $10k balance
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
            symbols=["BTCUSDT", "ETHUSDT"],
            account_id=1,
            timeframes=["1h", "4h"],
            market_data=market_context,
            account_state=account_context,
            risk_metrics=risk_metrics,
            recent_trades={"BTCUSDT": []},
        )

    @pytest.mark.asyncio
    async def test_large_allocation_with_tight_sl_passes(
        self, validator, sample_trading_context
    ):
        """Test that large allocation with tight stop loss passes risk validation.

        With $10,000 balance, 2% max risk per trade = $200 max risk.
        $1,500 allocation with 1% SL = $15 actual risk (passes risk check).
        Note: May fail concentration check (single asset), which is expected.
        """
        from app.schemas.trading_decision import AssetDecision

        asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=1500.0,
            sl_price=47520.0,
            exit_plan="Tight stop loss",
            rationale="Strong momentum",
            confidence=85.0,
            risk_level="medium",
        )

        decision = TradingDecision(
            decisions=[
                asset_decision,
                AssetDecision(
                    asset="ETHUSDT",
                    action="hold",
                    allocation_usd=0.0,
                    exit_plan="Wait for confirmation",
                    rationale="Neutral momentum",
                    confidence=70.0,
                    risk_level="low",
                ),
            ],
            portfolio_rationale="Test",
            total_allocation_usd=1500.0,
            portfolio_risk_level="medium",
        )

        result = await validator.validate_decision(decision, sample_trading_context)

        assert not any("exceeds strategy limit" in error for error in result.errors), (
            f"Risk per trade check failed: {result.errors}"
        )

    @pytest.mark.asyncio
    async def test_smaller_allocation_with_wide_sl_fails(
        self, validator, sample_trading_context
    ):
        """Test that smaller allocation with wide stop loss fails validation.

        With $10,000 balance, 2% max risk per trade = $200 max risk.
        $500 allocation with 50% SL = $250 actual risk (fails).
        """
        from app.schemas.trading_decision import AssetDecision

        asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=500.0,
            sl_price=24000.0,
            exit_plan="Wide stop loss",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        decision = TradingDecision(
            decisions=[asset_decision],
            portfolio_rationale="Test",
            total_allocation_usd=500.0,
            portfolio_risk_level="medium",
        )

        result = await validator.validate_decision(decision, sample_trading_context)

        assert not result.is_valid
        assert any("exceeds strategy limit" in error for error in result.errors)

    @pytest.mark.asyncio
    async def test_no_sl_uses_default_stop_loss(
        self, validator, sample_trading_context
    ):
        """Test that missing sl_price uses strategy's default stop loss percentage.

        With $10,000 balance, 2% max risk per trade = $200 max risk.
        $15,000 allocation with 1.5% default SL = $225 actual risk (fails).
        """
        from app.schemas.trading_decision import AssetDecision

        asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=15000.0,
            sl_price=None,
            exit_plan="Default SL",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        decision = TradingDecision(
            decisions=[asset_decision],
            portfolio_rationale="Test",
            total_allocation_usd=15000.0,
            portfolio_risk_level="medium",
        )

        result = await validator.validate_decision(decision, sample_trading_context)

        assert not result.is_valid
        assert any("exceeds strategy limit" in error for error in result.errors)

    @pytest.mark.asyncio
    async def test_sl_at_current_price_fails(
        self, validator, sample_trading_context
    ):
        """Test that stop loss at current price (0% SL) fails validation."""
        from app.schemas.trading_decision import AssetDecision

        asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=1000.0,
            sl_price=48000.0,
            exit_plan="No stop loss",
            rationale="Test",
            confidence=70.0,
            risk_level="high",
        )

        decision = TradingDecision(
            decisions=[asset_decision],
            portfolio_rationale="Test",
            total_allocation_usd=1000.0,
            portfolio_risk_level="medium",
        )

        result = await validator.validate_decision(decision, sample_trading_context)

        assert not result.is_valid
        assert any("must be positive" in error for error in result.errors)

    @pytest.mark.asyncio
    async def test_sl_over_100_percent_capped(
        self, validator, sample_trading_context
    ):
        """Test that stop loss over 100% is capped at 100%."""
        from app.schemas.trading_decision import AssetDecision

        asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=500.0,
            sl_price=12000.0,
            exit_plan="Wide stop loss",
            rationale="Test",
            confidence=70.0,
            risk_level="medium",
        )

        decision = TradingDecision(
            decisions=[asset_decision],
            portfolio_rationale="Test",
            total_allocation_usd=500.0,
            portfolio_risk_level="medium",
        )

        result = await validator.validate_decision(decision, sample_trading_context)

        assert not result.is_valid
        assert any("exceeds strategy limit" in error for error in result.errors)

    @pytest.mark.asyncio
    async def test_valid_allocation_with_sell_action(
        self, validator, sample_trading_context
    ):
        """Test valid risk calculation for sell action with tight stop loss.

        Note: May fail concentration check (single asset), which is expected.
        We only verify the risk per trade validation passes.
        """
        from app.schemas.trading_decision import AssetDecision

        asset_decision = AssetDecision(
            asset="BTCUSDT",
            action="sell",
            allocation_usd=1500.0,
            sl_price=48500.0,
            exit_plan="Take profit on downside",
            rationale="Bearish signals",
            confidence=80.0,
            risk_level="medium",
        )

        decision = TradingDecision(
            decisions=[
                asset_decision,
                AssetDecision(
                    asset="ETHUSDT",
                    action="hold",
                    allocation_usd=0.0,
                    exit_plan="Wait for confirmation",
                    rationale="Neutral momentum",
                    confidence=70.0,
                    risk_level="low",
                ),
            ],
            portfolio_rationale="Test",
            total_allocation_usd=1500.0,
            portfolio_risk_level="medium",
        )

        result = await validator.validate_decision(decision, sample_trading_context)

        assert not any("exceeds strategy limit" in error for error in result.errors), (
            f"Risk per trade check failed: {result.errors}"
        )
