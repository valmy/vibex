"""
Unit tests for Strategy Manager Service.

Tests strategy configuration, assignment, switching, and performance tracking.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from src.app.core.exceptions import ConfigurationError, ValidationError
from src.app.schemas.trading_decision import (
    StrategyAlert,
    StrategyPerformance,
    StrategyRiskParameters,
    TradingStrategy,
)
from src.app.services.llm.strategy_manager import StrategyManager


class TestStrategyManager:
    """Test cases for StrategyManager."""

    @pytest.fixture
    async def strategy_manager(self):
        """Create a StrategyManager instance for testing."""
        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "strategies"
            config_path.mkdir(exist_ok=True)
            manager = StrategyManager(config_path=config_path)
            yield manager

    @pytest.fixture
    def sample_risk_parameters(self):
        """Sample risk parameters for testing."""
        return StrategyRiskParameters(
            max_risk_per_trade=2.0,
            max_daily_loss=5.0,
            stop_loss_percentage=3.0,
            take_profit_ratio=2.0,
            max_leverage=2.0,
            cooldown_period=300,
        )

    @pytest.fixture
    def sample_custom_strategy(self, sample_risk_parameters):
        """Sample custom strategy for testing."""
        return TradingStrategy(
            strategy_id="test_custom",
            strategy_name="Test Custom Strategy",
            strategy_type="custom",
            prompt_template="Test prompt template",
            risk_parameters=sample_risk_parameters,
            timeframe_preference=["1h", "4h"],
            max_positions=3,
            position_sizing="percentage",
            is_active=True,
        )

    async def test_initialization(self, strategy_manager):
        """Test StrategyManager initialization."""
        # Check that predefined strategies are loaded
        strategies = await strategy_manager.get_available_strategies()
        assert len(strategies) == 5  # conservative, aggressive, scalping, swing, dca

        strategy_ids = [s.strategy_id for s in strategies]
        expected_ids = ["conservative", "aggressive", "scalping", "swing", "dca"]
        for expected_id in expected_ids:
            assert expected_id in strategy_ids

    async def test_multi_asset_prompt_templates(self, strategy_manager):
        """Test that strategy prompt templates support multi-asset context."""
        strategies = await strategy_manager.get_available_strategies()

        for strategy in strategies:
            # Verify prompt template exists and is not empty
            assert strategy.prompt_template
            assert len(strategy.prompt_template) > 0

            # Verify prompt templates can handle multi-asset context
            # They should not be symbol-specific
            assert (
                "symbol" not in strategy.prompt_template.lower()
                or "symbols" in strategy.prompt_template.lower()
            )

            # Verify prompt templates mention analysis approach
            prompt_lower = strategy.prompt_template.lower()
            assert any(
                keyword in prompt_lower
                for keyword in ["analyze", "market", "trading", "strategy", "risk"]
            )

    async def test_strategy_works_with_multi_asset_decisions(self, strategy_manager):
        """Test that strategies work correctly with multi-asset decision structure."""
        # Get a strategy
        conservative = await strategy_manager.get_strategy("conservative")
        assert conservative is not None

        # Verify strategy configuration supports multiple positions
        assert conservative.max_positions >= 1

        # Verify risk parameters are suitable for multi-asset trading
        assert conservative.risk_parameters.max_risk_per_trade > 0
        assert conservative.risk_parameters.max_daily_loss > 0

        # Verify the strategy can handle multiple assets
        # (max_positions should allow for multiple concurrent positions)
        assert conservative.max_positions >= 2 or conservative.strategy_type == "dca"

    async def test_strategy_prompt_template_multi_asset_context(self, strategy_manager):
        """Test that prompt templates are designed for multi-asset analysis."""
        strategies = await strategy_manager.get_available_strategies()

        for strategy in strategies:
            prompt = strategy.prompt_template

            # Verify prompt doesn't assume single asset
            # Should not have phrases like "the symbol" or "this asset"
            assert "the symbol" not in prompt.lower()
            assert "this asset" not in prompt.lower()

            # Verify prompt is generic enough for multiple assets
            # Should focus on market analysis, not specific to one symbol
            assert len(prompt) > 100  # Substantial prompt

            # Verify prompt includes strategy-specific guidance
            if strategy.strategy_type == "conservative":
                assert "conservative" in prompt.lower() or "capital preservation" in prompt.lower()
            elif strategy.strategy_type == "aggressive":
                assert "aggressive" in prompt.lower() or "momentum" in prompt.lower()
            elif strategy.strategy_type == "scalping":
                assert "scalping" in prompt.lower() or "quick" in prompt.lower()
            elif strategy.strategy_type == "swing":
                assert "swing" in prompt.lower() or "medium-term" in prompt.lower()
            elif strategy.strategy_type == "dca":
                assert "dca" in prompt.lower() or "dollar cost averaging" in prompt.lower()

    async def test_get_strategy(self, strategy_manager):
        """Test getting a specific strategy."""
        # Test existing strategy
        conservative = await strategy_manager.get_strategy("conservative")
        assert conservative is not None
        assert conservative.strategy_id == "conservative"
        assert conservative.strategy_type == "conservative"

        # Test non-existent strategy
        non_existent = await strategy_manager.get_strategy("non_existent")
        assert non_existent is None

    async def test_create_custom_strategy(self, strategy_manager, sample_risk_parameters):
        """Test creating a custom strategy."""
        custom_strategy = await strategy_manager.create_custom_strategy(
            strategy_id="test_custom",
            strategy_name="Test Custom",
            prompt_template="Custom prompt",
            risk_parameters=sample_risk_parameters,
            timeframe_preference=["1h", "4h"],
            max_positions=3,
            position_sizing="percentage",
        )

        assert custom_strategy.strategy_id == "test_custom"
        assert custom_strategy.strategy_name == "Test Custom"
        assert custom_strategy.strategy_type == "custom"
        assert custom_strategy.is_active is True

        # Verify it's stored
        retrieved = await strategy_manager.get_strategy("test_custom")
        assert retrieved is not None
        assert retrieved.strategy_id == "test_custom"

    async def test_create_custom_strategy_multi_asset(
        self, strategy_manager, sample_risk_parameters
    ):
        """Test creating a custom strategy designed for multi-asset trading."""
        multi_asset_prompt = """
        Analyze all provided assets and identify the best trading opportunities.
        Consider:
        - Relative strength across assets
        - Correlation and diversification
        - Portfolio-level risk management
        - Capital allocation optimization

        Provide decisions for each asset with portfolio-level rationale.
        """

        custom_strategy = await strategy_manager.create_custom_strategy(
            strategy_id="multi_asset_custom",
            strategy_name="Multi-Asset Custom Strategy",
            prompt_template=multi_asset_prompt,
            risk_parameters=sample_risk_parameters,
            timeframe_preference=["1h", "4h"],
            max_positions=5,  # Allow multiple concurrent positions
            position_sizing="percentage",
        )

        assert custom_strategy.strategy_id == "multi_asset_custom"
        assert custom_strategy.max_positions == 5
        assert "assets" in custom_strategy.prompt_template.lower()
        assert "portfolio" in custom_strategy.prompt_template.lower()

        # Verify validation passes
        errors = await strategy_manager.validate_strategy(custom_strategy)
        assert len(errors) == 0

    async def test_create_duplicate_strategy(self, strategy_manager, sample_risk_parameters):
        """Test creating a strategy with duplicate ID."""
        # Try to create a strategy with existing ID
        with pytest.raises(ValidationError, match="Strategy 'conservative' already exists"):
            await strategy_manager.create_custom_strategy(
                strategy_id="conservative",
                strategy_name="Duplicate Conservative",
                prompt_template="Duplicate prompt",
                risk_parameters=sample_risk_parameters,
            )

    async def test_validate_strategy(self, strategy_manager, sample_custom_strategy):
        """Test strategy validation."""
        # Valid strategy should have no errors
        errors = await strategy_manager.validate_strategy(sample_custom_strategy)
        assert len(errors) == 0

        # Invalid strategy with bad timeframes
        invalid_strategy = sample_custom_strategy.model_copy()
        invalid_strategy.timeframe_preference = ["invalid_timeframe"]

        errors = await strategy_manager.validate_strategy(invalid_strategy)
        assert len(errors) > 0
        assert any("Invalid timeframe" in error for error in errors)

    async def test_assign_strategy_to_account(self, strategy_manager):
        """Test assigning a strategy to an account."""
        account_id = 123
        strategy_id = "conservative"

        assignment = await strategy_manager.assign_strategy_to_account(
            account_id=account_id,
            strategy_id=strategy_id,
            assigned_by="test_user",
            switch_reason="Initial assignment",
        )

        assert assignment.account_id == account_id
        assert assignment.strategy_id == strategy_id
        assert assignment.assigned_by == "test_user"
        assert assignment.switch_reason == "Initial assignment"
        assert assignment.previous_strategy_id is None

        # Verify assignment is stored
        assigned_strategy = await strategy_manager.get_account_strategy(account_id)
        assert assigned_strategy is not None
        assert assigned_strategy.strategy_id == strategy_id

    async def test_assign_nonexistent_strategy(self, strategy_manager):
        """Test assigning a non-existent strategy."""
        with pytest.raises(ValidationError, match="Strategy 'nonexistent' not found"):
            await strategy_manager.assign_strategy_to_account(
                account_id=123, strategy_id="nonexistent"
            )

    async def test_switch_account_strategy(self, strategy_manager):
        """Test switching an account's strategy."""
        account_id = 123

        # First assign a strategy
        await strategy_manager.assign_strategy_to_account(
            account_id=account_id, strategy_id="conservative"
        )

        # Switch to aggressive
        assignment = await strategy_manager.switch_account_strategy(
            account_id=account_id,
            new_strategy_id="aggressive",
            switch_reason="Better performance needed",
            switched_by="test_user",
        )

        assert assignment.strategy_id == "aggressive"
        assert assignment.previous_strategy_id == "conservative"
        assert assignment.switch_reason == "Better performance needed"

        # Verify the switch
        current_strategy = await strategy_manager.get_account_strategy(account_id)
        assert current_strategy.strategy_id == "aggressive"

    async def test_switch_to_same_strategy(self, strategy_manager):
        """Test switching to the same strategy (should fail)."""
        account_id = 123

        # Assign a strategy
        await strategy_manager.assign_strategy_to_account(
            account_id=account_id, strategy_id="conservative"
        )

        # Try to switch to the same strategy
        with pytest.raises(ValidationError, match="already using strategy 'conservative'"):
            await strategy_manager.switch_account_strategy(
                account_id=account_id, new_strategy_id="conservative", switch_reason="Same strategy"
            )

    async def test_deactivate_activate_strategy(self, strategy_manager):
        """Test deactivating and activating strategies."""
        # Deactivate a strategy
        result = await strategy_manager.deactivate_strategy("conservative")
        assert result is True

        conservative = await strategy_manager.get_strategy("conservative")
        assert conservative.is_active is False

        # Try to assign deactivated strategy (should fail)
        with pytest.raises(ValidationError, match="Strategy 'conservative' is not active"):
            await strategy_manager.assign_strategy_to_account(
                account_id=123, strategy_id="conservative"
            )

        # Reactivate the strategy
        result = await strategy_manager.activate_strategy("conservative")
        assert result is True

        conservative = await strategy_manager.get_strategy("conservative")
        assert conservative.is_active is True

        # Now assignment should work
        assignment = await strategy_manager.assign_strategy_to_account(
            account_id=123, strategy_id="conservative"
        )
        assert assignment.strategy_id == "conservative"

    async def test_get_accounts_using_strategy(self, strategy_manager):
        """Test getting accounts using a specific strategy."""
        # Assign strategy to multiple accounts
        await strategy_manager.assign_strategy_to_account(123, "conservative")
        await strategy_manager.assign_strategy_to_account(456, "conservative")
        await strategy_manager.assign_strategy_to_account(789, "aggressive")

        # Check accounts using conservative strategy
        conservative_accounts = await strategy_manager.get_accounts_using_strategy("conservative")
        assert set(conservative_accounts) == {123, 456}

        # Check accounts using aggressive strategy
        aggressive_accounts = await strategy_manager.get_accounts_using_strategy("aggressive")
        assert aggressive_accounts == [789]

        # Check non-used strategy
        scalping_accounts = await strategy_manager.get_accounts_using_strategy("scalping")
        assert scalping_accounts == []

    async def test_resolve_strategy_conflicts(self, strategy_manager):
        """Test resolving strategy conflicts."""
        account_id = 123

        # Test account with no strategy
        conflicts = await strategy_manager.resolve_strategy_conflicts(account_id)
        assert len(conflicts) >= 1
        assert any("No strategy assigned" in conflict for conflict in conflicts)
        assert any("Auto-assigned conservative strategy" in conflict for conflict in conflicts)

        # Verify auto-assignment worked
        assigned_strategy = await strategy_manager.get_account_strategy(account_id)
        assert assigned_strategy.strategy_id == "conservative"

    async def test_update_strategy_metrics(self, strategy_manager):
        """Test updating strategy metrics."""
        strategy_id = "conservative"
        account_id = 123

        metrics = await strategy_manager.update_strategy_metrics(
            strategy_id=strategy_id,
            account_id=account_id,
            current_positions=2,
            total_allocated=1000.0,
            unrealized_pnl=50.0,
            realized_pnl_today=-20.0,
            trades_today=3,
            last_trade_time=datetime.now(timezone.utc) - timedelta(minutes=5),
        )

        assert metrics.strategy_id == strategy_id
        assert metrics.account_id == account_id
        assert metrics.current_positions == 2
        assert metrics.total_allocated == 1000.0
        assert metrics.unrealized_pnl == 50.0
        assert metrics.realized_pnl_today == -20.0
        assert metrics.trades_today == 3
        assert metrics.risk_utilization > 0  # Should be calculated
        assert metrics.cooldown_remaining > 0  # Should have some cooldown remaining

        # Verify metrics are cached
        cached_metrics = await strategy_manager.get_strategy_metrics(strategy_id, account_id)
        assert cached_metrics is not None
        assert cached_metrics.current_positions == 2

    async def test_strategy_metrics_multi_asset_positions(self, strategy_manager):
        """Test strategy metrics with multiple asset positions."""
        strategy_id = "aggressive"
        account_id = 456

        # Test with multiple positions across different assets
        metrics = await strategy_manager.update_strategy_metrics(
            strategy_id=strategy_id,
            account_id=account_id,
            current_positions=3,  # Multiple assets
            total_allocated=5000.0,  # Total across all assets
            unrealized_pnl=250.0,  # Combined P&L
            realized_pnl_today=100.0,
            trades_today=5,
            last_trade_time=datetime.now(timezone.utc) - timedelta(minutes=2),
        )

        assert metrics.current_positions == 3
        assert metrics.total_allocated == 5000.0
        assert metrics.unrealized_pnl == 250.0

        # Verify strategy allows multiple positions
        strategy = await strategy_manager.get_strategy(strategy_id)
        assert strategy.max_positions >= metrics.current_positions

    async def test_calculate_strategy_performance(self, strategy_manager):
        """Test calculating strategy performance."""
        strategy_id = "conservative"
        start_date = datetime.now(timezone.utc) - timedelta(days=30)
        end_date = datetime.now(timezone.utc)

        # Sample trade data
        trades_data = [
            {
                "pnl": 100.0,
                "volume": 1000.0,
                "entry_time": start_date,
                "exit_time": start_date + timedelta(hours=2),
            },
            {
                "pnl": -50.0,
                "volume": 500.0,
                "entry_time": start_date + timedelta(days=1),
                "exit_time": start_date + timedelta(days=1, hours=4),
            },
            {
                "pnl": 75.0,
                "volume": 750.0,
                "entry_time": start_date + timedelta(days=2),
                "exit_time": start_date + timedelta(days=2, hours=1),
            },
            {
                "pnl": -25.0,
                "volume": 250.0,
                "entry_time": start_date + timedelta(days=3),
                "exit_time": start_date + timedelta(days=3, hours=3),
            },
            {
                "pnl": 150.0,
                "volume": 1500.0,
                "entry_time": start_date + timedelta(days=4),
                "exit_time": start_date + timedelta(days=4, hours=6),
            },
        ]

        performance = await strategy_manager.calculate_strategy_performance(
            strategy_id=strategy_id,
            start_date=start_date,
            end_date=end_date,
            trades_data=trades_data,
        )

        assert performance.strategy_id == strategy_id
        assert performance.total_trades == 5
        assert performance.winning_trades == 3
        assert performance.losing_trades == 2
        assert performance.win_rate == 60.0
        assert performance.total_pnl == 250.0  # 100 - 50 + 75 - 25 + 150
        assert performance.avg_win > 0
        assert performance.avg_loss < 0
        assert performance.max_win == 150.0
        assert performance.max_loss == -50.0
        assert performance.profit_factor > 1.0
        assert performance.total_volume_traded == 4000.0

        # Test performance grade
        grade = performance.get_performance_grade()
        assert grade in ["A+", "A", "B+", "B", "C+", "C", "D", "F"]

    async def test_calculate_performance_multi_asset_trades(self, strategy_manager):
        """Test calculating performance with trades across multiple assets."""
        strategy_id = "aggressive"
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)

        # Sample multi-asset trade data (trades from BTC, ETH, SOL)
        trades_data = [
            {
                "symbol": "BTCUSDT",
                "pnl": 200.0,
                "volume": 2000.0,
                "entry_time": start_date,
                "exit_time": start_date + timedelta(hours=3),
            },
            {
                "symbol": "ETHUSDT",
                "pnl": 150.0,
                "volume": 1500.0,
                "entry_time": start_date + timedelta(hours=1),
                "exit_time": start_date + timedelta(hours=5),
            },
            {
                "symbol": "SOLUSDT",
                "pnl": -80.0,
                "volume": 800.0,
                "entry_time": start_date + timedelta(hours=2),
                "exit_time": start_date + timedelta(hours=4),
            },
            {
                "symbol": "BTCUSDT",
                "pnl": 100.0,
                "volume": 1000.0,
                "entry_time": start_date + timedelta(days=1),
                "exit_time": start_date + timedelta(days=1, hours=2),
            },
            {
                "symbol": "ETHUSDT",
                "pnl": -50.0,
                "volume": 500.0,
                "entry_time": start_date + timedelta(days=2),
                "exit_time": start_date + timedelta(days=2, hours=1),
            },
        ]

        performance = await strategy_manager.calculate_strategy_performance(
            strategy_id=strategy_id,
            start_date=start_date,
            end_date=end_date,
            trades_data=trades_data,
        )

        # Verify performance aggregates across all assets
        assert performance.strategy_id == strategy_id
        assert performance.total_trades == 5
        assert performance.winning_trades == 3  # BTC x2, ETH x1
        assert performance.losing_trades == 2  # SOL x1, ETH x1
        assert performance.total_pnl == 320.0  # 200 + 150 - 80 + 100 - 50
        assert performance.total_volume_traded == 5800.0

        # Verify strategy supports multiple assets
        strategy = await strategy_manager.get_strategy(strategy_id)
        assert strategy.max_positions >= 3  # Should allow multiple concurrent positions

    async def test_calculate_performance_no_trades(self, strategy_manager):
        """Test calculating performance with no trades."""
        strategy_id = "conservative"
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)

        performance = await strategy_manager.calculate_strategy_performance(
            strategy_id=strategy_id, start_date=start_date, end_date=end_date, trades_data=[]
        )

        assert performance.total_trades == 0
        assert performance.winning_trades == 0
        assert performance.losing_trades == 0
        assert performance.win_rate == 0.0
        assert performance.total_pnl == 0.0
        assert performance.profit_factor == 1.0

    async def test_compare_strategies(self, strategy_manager):
        """Test comparing multiple strategies."""
        # Create some performance data
        perf1 = StrategyPerformance(
            strategy_id="conservative",
            total_trades=10,
            winning_trades=7,
            losing_trades=3,
            win_rate=70.0,
            total_pnl=500.0,
            avg_win=100.0,
            avg_loss=-50.0,
            max_win=200.0,
            max_loss=-100.0,
            max_drawdown=150.0,
            sharpe_ratio=1.5,
            profit_factor=2.0,
            avg_trade_duration_hours=4.0,
            total_volume_traded=10000.0,
            start_date=datetime.now(timezone.utc) - timedelta(days=30),
            end_date=datetime.now(timezone.utc),
            period_days=30,
        )

        perf2 = StrategyPerformance(
            strategy_id="aggressive",
            total_trades=15,
            winning_trades=8,
            losing_trades=7,
            win_rate=53.3,
            total_pnl=300.0,
            avg_win=120.0,
            avg_loss=-60.0,
            max_win=250.0,
            max_loss=-150.0,
            max_drawdown=200.0,
            sharpe_ratio=1.2,
            profit_factor=1.6,
            avg_trade_duration_hours=2.0,
            total_volume_traded=15000.0,
            start_date=datetime.now(timezone.utc) - timedelta(days=30),
            end_date=datetime.now(timezone.utc),
            period_days=30,
        )

        # Cache the performance data
        strategy_manager._performance_cache["conservative"] = perf1
        strategy_manager._performance_cache["aggressive"] = perf2

        # Compare strategies
        comparison = await strategy_manager.compare_strategies(
            strategy_ids=["conservative", "aggressive"],
            comparison_period_days=30,
            ranking_criteria="sharpe_ratio",
        )

        assert len(comparison.strategies) == 2
        assert comparison.best_performing_strategy == "conservative"  # Higher Sharpe ratio
        assert comparison.ranking_criteria == "sharpe_ratio"
        assert comparison.comparison_period_days == 30

    async def test_strategy_alerts(self, strategy_manager):
        """Test strategy alert generation."""
        strategy_id = "conservative"
        account_id = 123

        # Update metrics that should trigger alerts
        await strategy_manager.update_strategy_metrics(
            strategy_id=strategy_id,
            account_id=account_id,
            current_positions=2,
            total_allocated=1000.0,
            unrealized_pnl=50.0,
            realized_pnl_today=-600.0,  # Exceeds daily loss limit (5% of assumed capital)
            trades_today=5,
            last_trade_time=datetime.now(timezone.utc),
        )

        # Check for alerts
        alerts = await strategy_manager.get_strategy_alerts(strategy_id=strategy_id)
        assert len(alerts) > 0

        # Should have critical alert for daily loss limit
        critical_alerts = [a for a in alerts if a.severity == "critical"]
        assert len(critical_alerts) > 0

        # Test acknowledging an alert
        if alerts:
            result = await strategy_manager.acknowledge_alert(0, "test_user")
            assert result is True

            # Check that alert is acknowledged
            updated_alerts = await strategy_manager.get_strategy_alerts()
            if updated_alerts:
                assert updated_alerts[0].acknowledged is True
                assert updated_alerts[0].acknowledged_by == "test_user"

    async def test_get_strategy_recommendations(self, strategy_manager):
        """Test getting strategy recommendations."""
        account_id = 123

        # Test with no strategy assigned
        recommendations = await strategy_manager.get_strategy_recommendations(account_id)
        assert len(recommendations) > 0
        assert any("No strategy assigned" in rec for rec in recommendations)

        # Assign a strategy and create poor performance
        await strategy_manager.assign_strategy_to_account(account_id, "conservative")

        poor_performance = StrategyPerformance(
            strategy_id="conservative",
            total_trades=10,
            winning_trades=2,
            losing_trades=8,
            win_rate=20.0,  # Very low win rate
            total_pnl=-1000.0,
            avg_win=50.0,
            avg_loss=-150.0,
            max_win=100.0,
            max_loss=-300.0,
            max_drawdown=-1200.0,  # Large drawdown
            profit_factor=0.3,
            avg_trade_duration_hours=2.0,
            total_volume_traded=5000.0,
            start_date=datetime.now(timezone.utc) - timedelta(days=30),
            end_date=datetime.now(timezone.utc),
            period_days=30,
        )

        strategy_manager._performance_cache["conservative"] = poor_performance

        recommendations = await strategy_manager.get_strategy_recommendations(account_id)
        assert len(recommendations) > 0
        assert any("concerning performance" in rec.lower() for rec in recommendations)

    async def test_clear_old_alerts(self, strategy_manager):
        """Test clearing old alerts."""
        # Create some old alerts
        old_alert = StrategyAlert(
            strategy_id="conservative",
            account_id=123,
            alert_type="performance_degradation",
            severity="medium",
            message="Old alert",
            created_at=datetime.now(timezone.utc) - timedelta(hours=25),  # Older than 24 hours
        )
        old_alert.acknowledged = True

        recent_alert = StrategyAlert(
            strategy_id="aggressive",
            account_id=456,
            alert_type="risk_limit_exceeded",
            severity="high",
            message="Recent alert",
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        strategy_manager._alerts = [old_alert, recent_alert]

        # Clear old alerts
        cleared_count = await strategy_manager.clear_old_alerts(max_age_hours=24)
        assert cleared_count == 1

        # Check remaining alerts
        remaining_alerts = await strategy_manager.get_strategy_alerts()
        assert len(remaining_alerts) == 1
        assert remaining_alerts[0].message == "Recent alert"

    async def test_load_save_strategy_file(self, strategy_manager, sample_custom_strategy):
        """Test loading and saving strategy files."""
        # Save strategy to file
        file_path = strategy_manager.config_path / "test_strategy.json"
        await strategy_manager.save_strategy_to_file(sample_custom_strategy, file_path)

        # Verify file exists
        assert file_path.exists()

        # Load strategy from file
        loaded_strategy = await strategy_manager.load_strategy_from_file(file_path)

        assert loaded_strategy.strategy_id == sample_custom_strategy.strategy_id
        assert loaded_strategy.strategy_name == sample_custom_strategy.strategy_name
        assert loaded_strategy.strategy_type == sample_custom_strategy.strategy_type
        assert loaded_strategy.prompt_template == sample_custom_strategy.prompt_template

    async def test_load_invalid_strategy_file(self, strategy_manager):
        """Test loading invalid strategy file."""
        # Create invalid JSON file
        invalid_file = strategy_manager.config_path / "invalid.json"
        with open(invalid_file, "w") as f:
            f.write("invalid json content")

        with pytest.raises(ConfigurationError, match="Invalid JSON"):
            await strategy_manager.load_strategy_from_file(invalid_file)

    async def test_load_nonexistent_strategy_file(self, strategy_manager):
        """Test loading non-existent strategy file."""
        nonexistent_file = strategy_manager.config_path / "nonexistent.json"

        with pytest.raises(ConfigurationError, match="Strategy file not found"):
            await strategy_manager.load_strategy_from_file(nonexistent_file)
