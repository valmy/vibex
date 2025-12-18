import pytest
from eth_account import Account as EthAccount
from sqlalchemy import select

from app.db.session import get_session_factory, init_db
from app.models.account import Account, User
from app.schemas.trading_decision import StrategyRiskParameters
from app.services.llm.context_builder import ContextBuilderService
from app.services.llm.strategy_manager import StrategyManager


@pytest.mark.e2e
class TestStrategyPersistenceE2E:
    @pytest.fixture
    async def db_session(self):
        """Create database session."""
        try:
            # Ensure database is initialized
            await init_db()

            # Get the session factory
            session_factory = get_session_factory()

            # Create and yield a session
            async with session_factory() as db:
                yield db
        except Exception as e:
            pytest.skip(f"Database not available: {e}")

    @pytest.fixture
    async def db_session_factory(self):
        """Get session factory."""
        await init_db()
        return get_session_factory()

    @pytest.mark.asyncio
    async def test_strategy_persistence_flow(self, db_session_factory, db_session):
        # 1. Setup Services
        strategy_manager = StrategyManager(session_factory=db_session_factory)
        context_builder = ContextBuilderService(session_factory=db_session_factory)

        # Initialize predefined strategies (this seeds the DB)
        await strategy_manager.initialize()

        # 2. Create a Test Account
        # Clean up existing test data first
        await db_session.execute(select(Account).where(Account.id == 999))
        existing_account = (
            await db_session.execute(select(Account).where(Account.id == 999))
        ).scalar_one_or_none()
        if existing_account:
            await db_session.delete(existing_account)

        # Clean up existing custom strategy with the same name
        existing_strategies = await strategy_manager.get_available_strategies()
        for strategy in existing_strategies:
            if strategy.strategy_name == "Integration Test Strategy":
                await strategy_manager.delete_strategy(strategy.strategy_id)

        existing_user = (
            await db_session.execute(select(User).where(User.id == 9999))
        ).scalar_one_or_none()
        if existing_user:
            await db_session.delete(existing_user)
        await db_session.commit()

        # Create a user first with a valid Ethereum address
        eth_account = EthAccount.create()
        test_user = User(id=9999, address=eth_account.address, is_admin=True)
        db_session.add(test_user)
        await db_session.commit()

        test_account = Account(
            id=999,
            user_id=9999,
            name="Test Account",
            api_key="test_key",
            api_secret="test_secret",
            is_paper_trading=True,
            maker_fee_bps=10,
            taker_fee_bps=20,
        )

        db_session.add(test_account)
        await db_session.commit()

        # 3. Verify Default Strategy
        # Initially, no strategy is assigned, so ContextBuilder should return default
        context = await context_builder.get_account_context(account_id=999)
        assert context.active_strategy.strategy_id == "default"

        # 4. Create a Custom Strategy
        risk_params = StrategyRiskParameters(
            max_risk_per_trade=1.5,
            max_daily_loss=3.0,
            stop_loss_percentage=2.0,
            take_profit_ratio=3.0,
            max_leverage=5.0,
            cooldown_period=60,
        )

        custom_strategy = await strategy_manager.create_custom_strategy(
            strategy_name="Integration Test Strategy",
            prompt_template="Test Prompt",
            risk_parameters=risk_params,
            timeframe_preference=["15m", "1h"],
            created_by="tester",
        )
        assert custom_strategy.strategy_id is not None

        # 5. Assign Strategy to Account
        assignment = await strategy_manager.assign_strategy_to_account(
            account_id=999, strategy_id=custom_strategy.strategy_id
        )
        assert assignment.strategy_id == custom_strategy.strategy_id
        assert assignment.account_id == 999
        assert assignment.is_active is True

        # 6. Verify ContextBuilder picks up the new strategy
        # We might need to clear cache if ContextBuilder caches it
        context_builder.clear_cache("account_context_999")

        context = await context_builder.get_account_context(account_id=999)
        assert context.active_strategy.strategy_id == custom_strategy.strategy_id
        assert context.active_strategy.strategy_name == "Integration Test Strategy"
        assert context.active_strategy.risk_parameters.max_risk_per_trade == 1.5

        # 7. Switch Strategy
        # Switch to a predefined strategy (e.g., 'conservative' if initialized)
        # Let's check available strategies first
        strategies = await strategy_manager.get_available_strategies()
        conservative = next((s for s in strategies if s.strategy_type == "conservative"), None)

        if conservative:
            await strategy_manager.switch_account_strategy(
                account_id=999,
                new_strategy_id=conservative.strategy_id,
                switch_reason="Testing switch",
            )

            context_builder.clear_cache("account_context_999")
            context = await context_builder.get_account_context(account_id=999)
            assert context.active_strategy.strategy_id == conservative.strategy_id

        # Cleanup
        deleted = await strategy_manager.delete_strategy(custom_strategy.strategy_id)
        assert deleted, f"Failed to delete strategy {custom_strategy.strategy_id}"
        await db_session.delete(test_account)
        await db_session.delete(test_user)
        await db_session.commit()
