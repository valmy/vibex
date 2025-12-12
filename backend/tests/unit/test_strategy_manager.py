"""
Unit tests for Strategy Manager Service.

Tests strategy configuration, assignment, switching, and performance tracking.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.exceptions import ValidationError
from src.app.models.account import Account as AccountModel
from src.app.models.strategy import Strategy as StrategyModel
from src.app.models.strategy import StrategyAssignment as StrategyAssignmentModel
from src.app.schemas.trading_decision import (
    StrategyRiskParameters,
    TradingStrategy,
)
from src.app.services.llm.strategy_manager import StrategyManager


class TestStrategyManager:
    """Test cases for StrategyManager."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock(spec=AsyncSession)
        return session

    @pytest.fixture
    def mock_session_factory(self, mock_session):
        """Create a mock session factory."""
        factory = MagicMock()
        factory.return_value.__aenter__.return_value = mock_session
        return factory

    @pytest.fixture
    def strategy_manager(self, mock_session_factory):
        """Create a StrategyManager instance for testing."""
        manager = StrategyManager(session_factory=mock_session_factory)
        return manager

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

    @pytest.fixture
    def valid_risk_params(self):
        return {
            "max_risk_per_trade": 1.0,
            "max_daily_loss": 5.0,
            "stop_loss_percentage": 2.0,
            "take_profit_ratio": 2.0,
            "max_leverage": 2.0,
            "cooldown_period": 600,
            "max_funding_rate_bps": 5.0,
            "liquidation_buffer": 0.15,
        }

    async def test_initialization(self, strategy_manager, mock_session, valid_risk_params):
        """Test StrategyManager initialization."""

        # Mock database response for get_available_strategies
        def create_mock_strategy(sid):
            return StrategyModel(
                strategy_id=sid,
                strategy_name=f"{sid.capitalize()} Strategy",
                strategy_type=sid
                if sid
                in [
                    "conservative_perps",
                    "aggressive_perps",
                    "scalping_perps",
                    "swing_perps",
                    "dca_hedge",
                ]
                else "custom",
                prompt_template="template",
                risk_parameters=valid_risk_params,
                timeframe_preference=["1h"],
                max_positions=1,
                position_sizing="fixed",
                order_preference="any",
                funding_rate_threshold=0.0,
                is_active=True,
            )

        mock_strategies = [
            create_mock_strategy("conservative_perps"),
            create_mock_strategy("aggressive_perps"),
            create_mock_strategy("scalping_perps"),
            create_mock_strategy("swing_perps"),
            create_mock_strategy("dca_hedge"),
        ]

        # Setup mock return for get_available_strategies query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_strategies
        mock_session.execute.return_value = mock_result

        # Check that predefined strategies are loaded
        strategies = await strategy_manager.get_available_strategies()
        assert len(strategies) == 5

    async def test_get_strategy(self, strategy_manager, mock_session, valid_risk_params):
        """Test getting a specific strategy."""
        # Mock database response
        mock_strategy = StrategyModel(
            strategy_id="conservative_perps",
            strategy_name="Conservative Perps",
            strategy_type="conservative",
            prompt_template="template",
            risk_parameters=valid_risk_params,
            timeframe_preference=["4h"],
            max_positions=2,
            position_sizing="percentage",
            order_preference="maker_only",
            funding_rate_threshold=0.05,
            is_active=True,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_strategy
        mock_session.execute.return_value = mock_result

        # Test existing strategy
        conservative = await strategy_manager.get_strategy("conservative_perps")
        assert conservative is not None
        assert conservative.strategy_id == "conservative_perps"
        assert conservative.strategy_type == "conservative"

        # Test non-existent strategy
        mock_result.scalar_one_or_none.return_value = None
        non_existent = await strategy_manager.get_strategy("non_existent")
        assert non_existent is None

    async def test_create_custom_strategy(
        self, strategy_manager, sample_risk_parameters, mock_session
    ):
        """Test creating a custom strategy."""
        # Mock check for existing strategy (returns None)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        custom_strategy = await strategy_manager.create_custom_strategy(
            name="Test Custom",
            prompt_template="Custom prompt",
            risk_parameters=sample_risk_parameters,
            timeframe_preference=["1h", "4h"],
            max_positions=3,
            position_sizing="percentage",
            order_preference="maker_only",
            funding_rate_threshold=0.01,
        )

        assert custom_strategy.strategy_id == "test_custom"
        assert custom_strategy.strategy_name == "Test Custom"
        assert custom_strategy.strategy_type == "custom"
        assert custom_strategy.is_active is True
        assert custom_strategy.order_preference == "maker_only"
        assert custom_strategy.funding_rate_threshold == 0.01

        # Verify DB interaction
        assert mock_session.add.called
        assert mock_session.commit.called

    async def test_create_duplicate_strategy(
        self, strategy_manager, sample_risk_parameters, mock_session
    ):
        """Test creating a strategy with duplicate ID."""
        # Mock check for existing strategy (returns existing)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = StrategyModel(
            strategy_id="conservative_perps"
        )
        mock_session.execute.return_value = mock_result

        with pytest.raises(ValidationError, match="Strategy 'conservative_perps' already exists"):
            await strategy_manager.create_custom_strategy(
                name="Conservative Perps",
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

    async def test_assign_strategy_to_account(
        self, strategy_manager, mock_session, valid_risk_params
    ):
        """Test assigning a strategy to an account."""
        account_id = 123
        strategy_id = "conservative_perps"

        # Mock account lookup
        mock_account = MagicMock(spec=AccountModel)
        mock_account.id = account_id

        # Mock strategy lookup
        mock_strategy = StrategyModel(
            id=1,
            strategy_id=strategy_id,
            strategy_name="Conservative Perps",
            strategy_type="conservative",
            prompt_template="template",
            timeframe_preference=["1h"],
            max_positions=1,
            position_sizing="fixed",
            order_preference="maker_only",
            funding_rate_threshold=0.05,
            is_active=True,
            risk_parameters=valid_risk_params,
        )

        # Mock account lookup result
        mock_result_account = MagicMock()
        mock_result_account.scalar_one_or_none.return_value = mock_account

        # Mock strategy lookup result
        mock_result_strategy = MagicMock()
        mock_result_strategy.scalar_one_or_none.return_value = mock_strategy

        # Mock current assignment lookup (None)
        mock_result_assignment = MagicMock()
        mock_result_assignment.scalar_one_or_none.return_value = None

        # Configure execute side effects: account, strategy, assignment
        mock_session.execute.side_effect = [
            mock_result_account,
            mock_result_strategy,
            mock_result_assignment,
        ]

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

        assert mock_session.add.called
        assert mock_session.commit.called

    async def test_assign_nonexistent_strategy(self, strategy_manager, mock_session):
        """Test assigning a non-existent strategy."""
        account_id = 123

        # Mock account lookup (account exists)
        mock_account = MagicMock(spec=AccountModel)
        mock_account.id = account_id
        mock_result_account = MagicMock()
        mock_result_account.scalar_one_or_none.return_value = mock_account

        # Mock strategy lookup returning None
        mock_result_strategy = MagicMock()
        mock_result_strategy.scalar_one_or_none.return_value = None

        # Configure execute side effects: account, strategy
        mock_session.execute.side_effect = [mock_result_account, mock_result_strategy]

        with pytest.raises(ValidationError, match="Strategy 'nonexistent' not found"):
            await strategy_manager.assign_strategy_to_account(
                account_id=account_id, strategy_id="nonexistent"
            )

    async def test_switch_account_strategy(self, strategy_manager, mock_session, valid_risk_params):
        """Test switching an account's strategy."""
        account_id = 123
        old_strategy_id = "conservative_perps"
        new_strategy_id = "aggressive_perps"

        # Mock account
        mock_account = MagicMock(spec=AccountModel)
        mock_account.id = account_id

        # Mock get_account_strategy response (current strategy)
        mock_current_strategy = StrategyModel(
            id=1,
            strategy_id=old_strategy_id,
            strategy_name="Conservative Perps",
            strategy_type="conservative",
            prompt_template="template",
            timeframe_preference=["1h"],
            max_positions=1,
            position_sizing="fixed",
            order_preference="maker_only",
            funding_rate_threshold=0.05,
            is_active=True,
            risk_parameters=valid_risk_params,
        )

        # Mock get_strategy response (new strategy validation)
        mock_new_strategy = StrategyModel(
            id=2,
            strategy_id=new_strategy_id,
            strategy_name="Aggressive Perps",
            strategy_type="aggressive",
            prompt_template="template",
            timeframe_preference=["1h"],
            max_positions=1,
            position_sizing="fixed",
            order_preference="taker_accepted",
            funding_rate_threshold=0.15,
            is_active=True,
            risk_parameters=valid_risk_params,
        )

        # Mock assignment flow
        # 1. get_account_strategy query
        res1 = MagicMock()
        res1.scalar_one_or_none.return_value = mock_current_strategy

        # 2. _validate_strategy_switch -> get_strategy query
        res2 = MagicMock()
        res2.scalar_one_or_none.return_value = mock_new_strategy

        # 3. assign_strategy_to_account -> account check
        res3 = MagicMock()
        res3.scalar_one_or_none.return_value = mock_account

        # 4. assign_strategy_to_account -> get_strategy query
        res4 = MagicMock()
        res4.scalar_one_or_none.return_value = mock_new_strategy

        # 5. assign_strategy_to_account -> get_current_assignment query
        mock_assignment = StrategyAssignmentModel(
            account_id=account_id,
            strategy_id=1,
            is_active=True,
            assigned_at=datetime.now(timezone.utc),
        )
        res5 = MagicMock()
        res5.scalar_one_or_none.return_value = mock_assignment

        # 6. assign_strategy_to_account -> get previous strategy for previous_strategy_id_str
        res6 = MagicMock()
        res6.scalar_one_or_none.return_value = mock_current_strategy

        mock_session.execute.side_effect = [res1, res2, res3, res4, res5, res6]

        assignment = await strategy_manager.switch_account_strategy(
            account_id=account_id,
            new_strategy_id=new_strategy_id,
            switch_reason="Better performance needed",
            switched_by="test_user",
        )

        assert assignment.strategy_id == new_strategy_id
        assert assignment.switch_reason == "Better performance needed"

        # Verify old assignment was deactivated
        assert mock_assignment.is_active is False
        assert mock_assignment.deactivated_by == "test_user"

    async def test_switch_to_same_strategy(self, strategy_manager, mock_session, valid_risk_params):
        """Test switching to the same strategy (should fail)."""
        account_id = 123
        strategy_id = "conservative_perps"

        # Mock get_account_strategy returning conservative
        mock_strategy = StrategyModel(
            strategy_id=strategy_id,
            strategy_name="Conservative Perps",
            strategy_type="conservative",
            prompt_template="template",
            timeframe_preference=["1h"],
            max_positions=1,
            position_sizing="fixed",
            order_preference="maker_only",
            funding_rate_threshold=0.05,
            is_active=True,
            risk_parameters=valid_risk_params,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_strategy
        mock_session.execute.return_value = mock_result

        with pytest.raises(ValidationError, match="already using strategy 'conservative_perps'"):
            await strategy_manager.switch_account_strategy(
                account_id=account_id, new_strategy_id=strategy_id, switch_reason="Same strategy"
            )

    async def test_deactivate_activate_strategy(self, strategy_manager, mock_session):
        """Test deactivating and activating strategies."""
        strategy_id = "conservative"

        # Mock strategy lookup
        mock_strategy = StrategyModel(strategy_id=strategy_id, is_active=True)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_strategy
        mock_session.execute.return_value = mock_result

        # Deactivate
        result = await strategy_manager.deactivate_strategy(strategy_id)
        assert result is True
        assert mock_strategy.is_active is False
        assert mock_session.commit.called

        # Activate
        mock_strategy.is_active = False
        result = await strategy_manager.activate_strategy(strategy_id)
        assert result is True
        assert mock_strategy.is_active is True

    async def test_get_accounts_using_strategy(self, strategy_manager, mock_session):
        """Test getting accounts using a specific strategy."""
        # Mock response
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [123, 456]
        mock_session.execute.return_value = mock_result

        accounts = await strategy_manager.get_accounts_using_strategy("conservative")
        assert accounts == [123, 456]

    async def test_calculate_strategy_performance(self, strategy_manager):
        """Test calculating strategy performance."""
        strategy_id = "conservative"
        start_date = datetime.now(timezone.utc) - timedelta(days=30)
        end_date = datetime.now(timezone.utc)

        # Sample trade data
        trades_data = [
            {"pnl": 100.0, "volume": 1000.0, "fee": 1.0, "funding": 0.5, "is_liquidation": False},
            {"pnl": -50.0, "volume": 500.0, "fee": 0.5, "funding": 0.2, "is_liquidation": False},
            {"pnl": 75.0, "volume": 750.0, "fee": 0.75, "funding": 0.3, "is_liquidation": False},
        ]

        performance = strategy_manager.calculate_strategy_performance(
            strategy_id=strategy_id,
            period_start=start_date,
            period_end=end_date,
            trades=trades_data,
        )

        assert performance.strategy_id == strategy_id
        assert performance.total_trades == 3
        assert performance.winning_trades == 2
        assert performance.losing_trades == 1
        assert performance.total_pnl == 125.0
        assert performance.total_fees_paid == 2.25
        assert performance.total_funding_paid == 1.0

    async def test_calculate_performance_no_trades(self, strategy_manager):
        """Test calculating performance with no trades."""
        strategy_id = "conservative"
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)

        performance = strategy_manager.calculate_strategy_performance(
            strategy_id=strategy_id, period_start=start_date, period_end=end_date, trades=[]
        )

        assert performance.total_trades == 0
        assert performance.winning_trades == 0
        assert performance.total_pnl == 0.0
