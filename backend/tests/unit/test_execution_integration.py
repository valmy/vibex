import pytest
from unittest.mock import MagicMock, AsyncMock, patch, ANY
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.llm.decision_engine import DecisionEngine
from app.schemas.trading_decision import DecisionResult, TradingDecision, AssetDecision, TradingContext, MarketContext, AssetMarketData
from app.models.account import Account

@pytest.mark.unit
class TestExecutionIntegration:
    
    @pytest.fixture
    def mock_db(self):
        db = MagicMock(spec=AsyncSession)
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        return db

    @pytest.fixture
    def mock_account(self):
        account = MagicMock(spec=Account)
        account.id = 1
        account.leverage = 5.0
        account.is_paper_trading = True
        return account

    @pytest.mark.asyncio
    async def test_decision_triggers_execution(self, mock_db, mock_account):
        """Test that a 'buy' decision from DecisionEngine triggers ExecutionService."""
        
        # 1. Setup Decision Engine with mocks
        # Using a lambda that returns a context manager mock for session_factory
        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=mock_db)
        session_cm.__aexit__ = AsyncMock()
        
        engine = DecisionEngine(session_factory=MagicMock(return_value=session_cm))
        
        # Mock database fetch for account
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_account
        mock_db.execute.return_value = mock_result

        # Construct valid schemas
        asset_decision = AssetDecision.model_construct(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=100.0,
            tp_price=60000.0,
            sl_price=40000.0,
            exit_plan="plan",
            rationale="bullish",
            confidence=80.0,
            risk_level="low"
        )
        trading_decision = TradingDecision.model_construct(
            decisions=[asset_decision],
            portfolio_rationale="strat",
            total_allocation_usd=100.0,
            portfolio_risk_level="low"
        )
        
        # Mock MarketContext for price lookup
        asset_market_data = AssetMarketData.model_construct(current_price=50000.0)
        market_context = MarketContext.model_construct(assets={"BTCUSDT": asset_market_data})
        context = TradingContext.model_construct(market_data=market_context)
        
        decision_result = DecisionResult.model_construct(
            decision=trading_decision,
            context=context,
            validation_passed=True,
            processing_time_ms=100.0,
            model_used="test-model"
        )
        
        # Configure DecisionEngine mocks
        engine._get_strategy = AsyncMock(return_value=MagicMock(strategy_id="test", timeframe_preference=["1m", "5m"]))
        engine._build_context = AsyncMock(return_value=context)
        engine._generate_decision = AsyncMock(return_value=decision_result)
        engine._validate_and_handle_fallback = AsyncMock(return_value=decision_result)
        engine._persist_decision_if_repository_exists = AsyncMock()

        # 2. Mock ExecutionService
        with patch("app.services.llm.decision_engine.get_execution_service") as mock_get_service:
            mock_execution_service = AsyncMock()
            mock_get_service.return_value = mock_execution_service
            
            # 3. Call make_trading_decision
            await engine.make_trading_decision(account_id=1, symbols=["BTCUSDT"])
            
            # 4. Verify ExecutionService was called
            # Quantity should be 100 / 50000 = 0.002
            mock_execution_service.execute_order.assert_called_once_with(
                db=mock_db,
                account=mock_account,
                symbol="BTCUSDT",
                action="buy",
                quantity=0.002,
                tp_price=60000.0,
                sl_price=40000.0
            )
            
            mock_db.commit.assert_called()
