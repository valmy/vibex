import pytest
from sqlalchemy import select
from app.services.llm.strategy_manager import StrategyManager
from app.services.llm.context_builder import ContextBuilderService
from app.models.account import Account, User
from app.models.strategy import Strategy
from app.schemas.trading_decision import StrategyRiskParameters

@pytest.mark.integration
@pytest.mark.asyncio
async def test_strategy_persistence_flow(db_session_factory, db_session):
    # 1. Setup Services
    strategy_manager = StrategyManager(session_factory=db_session_factory)
    context_builder = ContextBuilderService(session_factory=db_session_factory)

    # Initialize predefined strategies (this seeds the DB)
    await strategy_manager.initialize()

    # 2. Create a Test Account
    # Clean up existing test data first
    await db_session.execute(select(Account).where(Account.id == 999))
    existing_account = (await db_session.execute(select(Account).where(Account.id == 999))).scalar_one_or_none()
    if existing_account:
        await db_session.delete(existing_account)

    existing_user = (await db_session.execute(select(User).where(User.id == 1))).scalar_one_or_none()
    if existing_user:
        await db_session.delete(existing_user)
    await db_session.commit()

    # Create a user first
    test_user = User(id=1, address="0x123", is_admin=True)
    db_session.add(test_user)
    await db_session.commit()

    test_account = Account(
        id=999,
        user_id=1,
        name="Test Account",
        api_key="test_key",
        api_secret="test_secret",
        is_paper_trading=True,
        maker_fee_bps=10,
        taker_fee_bps=20,
        # balance_usd=10000.0 # This will fail if column doesn't exist
    )
    # We need to manually set balance_usd if it's missing from model but required by logic
    # But if it's missing from model, we can't save it to DB.
    # Let's assume for a moment it IS missing and we need to add it.
    # For this test to pass ContextBuilder, we might need to patch it or fix the model.
    # Let's try to add it to the object and see if SQLAlchemy complains on init (it will).
    # So I will NOT add it here, and expect ContextBuilder to fail, confirming the bug.

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
        cooldown_period=60
    )

    custom_strategy = await strategy_manager.create_custom_strategy(
        name="Integration Test Strategy",
        prompt_template="Test Prompt",
        risk_parameters=risk_params,
        timeframe_preference=["15m", "1h"],
        created_by="tester"
    )
    assert custom_strategy.strategy_id is not None

    # 5. Assign Strategy to Account
    assignment = await strategy_manager.assign_strategy_to_account(
        account_id=999,
        strategy_id=custom_strategy.strategy_id
    )
    assert assignment.strategy_id == custom_strategy.strategy_id
    assert assignment.account_id == 999
    assert assignment.is_active is True

    # 6. Verify ContextBuilder picks up the new strategy
    # We might need to clear cache if ContextBuilder caches it
    context_builder.clear_cache(f"account_context_999")

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
            switch_reason="Testing switch"
        )

        context_builder.clear_cache(f"account_context_999")
        context = await context_builder.get_account_context(account_id=999)
        assert context.active_strategy.strategy_id == conservative.strategy_id

    # Cleanup
    await db_session.delete(test_account)
    await db_session.commit()
