from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.trading_decision import StrategyRiskParameters, TradingStrategy
from app.services.llm.context_builder import ContextBuilderService


@pytest.mark.asyncio
class TestContextBuilderStrategy:
    @pytest.fixture
    def mock_strategy_manager(self):
        return AsyncMock()

    @pytest.fixture
    def context_builder(self, mock_strategy_manager):
        with patch("app.services.llm.context_builder.StrategyManager") as MockStrategyManager:
            MockStrategyManager.return_value = mock_strategy_manager
            service = ContextBuilderService(session_factory=None)
            # Manually set the mock because __init__ creates a new instance
            service.strategy_manager = mock_strategy_manager
            return service

    async def test_get_account_context_uses_assigned_strategy(
        self, context_builder, mock_strategy_manager
    ):
        from app.schemas.trading_decision import PerformanceMetrics

        # Mock dependencies
        context_builder.market_data_service = AsyncMock()

        # Mock DB session
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        context_builder._session_factory = lambda: mock_db

        # Mock Account query result
        mock_account = MagicMock()
        mock_account.id = 1
        mock_account.balance_usd = 10000.0
        mock_account.max_position_size_usd = 10000.0
        mock_account.maker_fee_bps = 10
        mock_account.taker_fee_bps = 20

        mock_account_result = MagicMock()
        mock_account_result.scalar_one_or_none = AsyncMock(return_value=mock_account)

        # Mock positions query result
        mock_positions_result = MagicMock()
        mock_positions_result.scalars.return_value.all.return_value = []

        # Configure execute side effects
        mock_db.execute.side_effect = [mock_account_result, mock_positions_result]

        # Mock StrategyManager response
        mock_strategy = TradingStrategy(
            strategy_id="custom_strategy",
            strategy_name="Custom Strategy",
            strategy_type="custom",
            prompt_template="template",
            risk_parameters=StrategyRiskParameters(
                max_risk_per_trade=1.0,
                max_daily_loss=2.0,
                stop_loss_percentage=1.0,
                take_profit_ratio=2.0,
                max_leverage=5.0,
                cooldown_period=60,
            ),
            timeframe_preference=["1h"],
            max_positions=5,
            position_sizing="fixed",
            is_active=True,
        )
        mock_strategy_manager.get_account_strategy.return_value = mock_strategy

        # Mock _calculate_performance_metrics
        mock_metrics = PerformanceMetrics(
            total_pnl=100.0,
            win_rate=50.0,
            avg_win=10.0,
            avg_loss=5.0,
            max_drawdown=10.0,
            sharpe_ratio=1.5,
        )
        context_builder._calculate_performance_metrics = AsyncMock(return_value=mock_metrics)

        # Execute
        context = await context_builder.get_account_context(account_id=1)

        # Verify
        assert context.active_strategy.strategy_id == "custom_strategy"
        mock_strategy_manager.get_account_strategy.assert_called_once_with(1)

    async def test_get_account_context_fallbacks_to_default(
        self, context_builder, mock_strategy_manager
    ):
        from app.schemas.trading_decision import PerformanceMetrics

        # Mock dependencies
        context_builder.market_data_service = AsyncMock()

        # Mock DB session
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        context_builder._session_factory = lambda: mock_db

        # Mock Account query result
        mock_account = MagicMock()
        mock_account.id = 1
        mock_account.balance_usd = 10000.0
        mock_account.max_position_size_usd = 10000.0
        mock_account.maker_fee_bps = 10
        mock_account.taker_fee_bps = 20

        mock_account_result = MagicMock()
        mock_account_result.scalar_one_or_none = AsyncMock(return_value=mock_account)

        # Mock positions query result
        mock_positions_result = MagicMock()
        mock_positions_result.scalars.return_value.all.return_value = []

        # Configure execute side effects
        mock_db.execute.side_effect = [mock_account_result, mock_positions_result]

        # Mock StrategyManager response (None)
        mock_strategy_manager.get_account_strategy.return_value = None

        # Mock _calculate_performance_metrics
        mock_metrics = PerformanceMetrics(
            total_pnl=100.0,
            win_rate=50.0,
            avg_win=10.0,
            avg_loss=5.0,
            max_drawdown=10.0,
            sharpe_ratio=1.5,
        )
        context_builder._calculate_performance_metrics = AsyncMock(return_value=mock_metrics)

        # Execute
        context = await context_builder.get_account_context(account_id=1)

        # Verify
        assert context.active_strategy.strategy_id == "default"
        mock_strategy_manager.get_account_strategy.assert_called_once_with(1)
