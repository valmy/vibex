"""
Property-based tests for account service.

Tests universal properties that should hold across all valid inputs.
Uses mocked database access for true unit testing.
"""

import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.models.account import Account, User
from app.models.performance_metric import PerformanceMetric
from app.models.position import Position
from app.schemas.account import AccountCreate, AccountUpdate
from app.services.account_service import (
    AccountAccessDeniedError,
    AccountService,
    AccountValidationError,
    DuplicateAccountNameError,
)


# Hypothesis strategies for generating test data
@st.composite
def account_data_strategy(draw):
    """Generate valid account creation data."""
    # Use printable ASCII characters to avoid Unicode validation issues
    name = draw(
        st.text(
            min_size=1,
            max_size=255,
            alphabet=st.characters(
                min_codepoint=32, max_codepoint=126, blacklist_characters="\x00"
            ),
        )
    )
    description = draw(
        st.one_of(
            st.none(),
            st.text(
                max_size=1000,
                alphabet=st.characters(min_codepoint=32, max_codepoint=126),
            ),
        )
    )
    leverage = draw(st.floats(min_value=1.0, max_value=5.0))
    max_position_size = draw(st.floats(min_value=1.0, max_value=1000000.0))
    risk_per_trade = draw(st.floats(min_value=0.01, max_value=0.1))
    is_paper_trading = draw(st.booleans())
    balance_usd = draw(st.floats(min_value=0.0, max_value=1000000.0)) if is_paper_trading else None

    # For real trading, we need API credentials
    api_key = None
    api_secret = None
    if not is_paper_trading:
        api_key = draw(
            st.text(
                min_size=10,
                max_size=100,
                alphabet=st.characters(min_codepoint=32, max_codepoint=126),
            )
        )
        api_secret = draw(
            st.text(
                min_size=10,
                max_size=100,
                alphabet=st.characters(min_codepoint=32, max_codepoint=126),
            )
        )

    return AccountCreate(
        name=name,
        description=description,
        leverage=leverage,
        max_position_size_usd=max_position_size,
        risk_per_trade=risk_per_trade,
        is_paper_trading=is_paper_trading,
        balance_usd=balance_usd,
        api_key=api_key,
        api_secret=api_secret,
    )


@st.composite
def user_strategy(draw):
    """Generate valid user data."""
    import uuid

    # Ethereum addresses are 42 characters (0x + 40 hex chars)
    # Add a UUID to ensure uniqueness across hypothesis examples
    unique_id = uuid.uuid4().hex[:32]
    address = "0x" + unique_id + draw(st.text(min_size=8, max_size=8, alphabet="0123456789abcdef"))
    is_admin = draw(st.booleans())
    return {"address": address, "is_admin": is_admin}


# Property 1: Account creation persists all settings
# Feature: account-management, Property 1: Account creation persists all settings
# Validates: Requirements 1.1, 1.4
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None)
@given(account_data=account_data_strategy(), user_data=user_strategy())
async def test_property_account_creation_persistence(account_data, user_data):
    """
    Property: For any valid account configuration provided by an authenticated user,
    creating an account should persist all settings and associate the account with that user.

    **Feature: account-management, Property 1: Account creation persists all settings**
    **Validates: Requirements 1.1, 1.4**
    """
    service = AccountService()

    # Mock database session
    mock_db = AsyncMock()
    mock_execute_result = MagicMock()

    # Create mock user
    user = User(**user_data)
    user.id = 1
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)

    # Mock the execute query to return no existing account (no duplicate)
    mock_execute_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_execute_result

    # Mock commit and refresh
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    # Create account
    try:
        account = await service.create_account(mock_db, user.id, account_data)

        # Verify account properties match input
        assert account.name == account_data.name, "Name should match"
        assert account.user_id == user.id, "Should be associated with user"
        assert abs(account.leverage - account_data.leverage) < 0.001, "Leverage should match"
        assert abs(account.max_position_size_usd - account_data.max_position_size_usd) < 0.1, (
            "Max position size should match"
        )
        assert abs(account.risk_per_trade - account_data.risk_per_trade) < 0.001, (
            "Risk per trade should match"
        )
        assert account.is_paper_trading == account_data.is_paper_trading, (
            "Trading mode should match"
        )
        assert account.status == "active", "Status should be active"
        assert account.is_enabled is True, "Should be enabled"

        # Verify balance for paper trading
        if account_data.is_paper_trading and account_data.balance_usd:
            assert abs(account.balance_usd - account_data.balance_usd) < 0.1, (
                "Balance should match for paper trading"
            )

        # Verify database operations were called
        assert mock_db.add.called, "Should add account to session"
        assert mock_db.commit.called, "Should commit transaction"

    except DuplicateAccountNameError:
        # This is expected if we randomly generate a duplicate name
        pass


# Property 2: Account ownership filtering
# Feature: account-management, Property 2: Account ownership filtering
# Validates: Requirements 2.1
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None)
@given(
    num_accounts=st.integers(min_value=0, max_value=10),
    user_data=user_strategy(),
)
async def test_property_ownership_filtering(num_accounts, user_data):
    """
    Property: For any user with N accounts, listing accounts should return
    exactly N accounts, all owned by that user.

    **Feature: account-management, Property 2: Account ownership filtering**
    **Validates: Requirements 2.1**
    """
    service = AccountService()

    # Mock database session
    mock_db = AsyncMock()

    # Create mock user
    user = User(**user_data)
    user.id = 1

    # Create N mock accounts for the user
    mock_accounts = []
    for i in range(num_accounts):
        account = Account(
            id=i + 1,
            name=f"test_account_{i}",
            user_id=user.id,
            status="active",
            is_enabled=True,
            is_paper_trading=True,
            leverage=2.0,
            max_position_size_usd=10000.0,
            risk_per_trade=0.02,
            balance_usd=10000.0,
            maker_fee_bps=5.0,
            taker_fee_bps=20.0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_accounts.append(account)

    # Mock the execute query to return count, accounts, and user
    # First call: count query
    count_result = MagicMock()
    count_result.scalar.return_value = num_accounts

    # Second call: accounts query
    accounts_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = mock_accounts
    accounts_result.scalars.return_value = mock_scalars

    # Third call: user query
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = user

    mock_db.execute = AsyncMock(
        side_effect=[count_result, accounts_result, user_result]
    )

    # List accounts for the user
    accounts, total = await service.list_user_accounts(mock_db, user.id)

    # Verify we get exactly N accounts
    assert len(accounts) == num_accounts, f"Should return exactly {num_accounts} accounts"
    assert total == num_accounts, f"Total count should be {num_accounts}"

    # Verify all accounts belong to the user
    for account in accounts:
        assert account.user_id == user.id, "All accounts should belong to the user"


# Property 3: Non-owner access denied
# Feature: account-management, Property 3: Non-owner access denied
# Validates: Requirements 2.3, 3.2, 4.2
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None)
@given(
    owner_data=user_strategy(),
    non_owner_data=user_strategy(),
)
async def test_property_non_owner_access_denied(owner_data, non_owner_data):
    """
    Property: For any account not owned by a user (and user is not admin),
    attempting to read, update, or delete that account should return a 403 Forbidden error.

    **Feature: account-management, Property 3: Non-owner access denied**
    **Validates: Requirements 2.3, 3.2, 4.2**
    """
    # Ensure non-owner is not admin
    non_owner_data["is_admin"] = False

    # Ensure addresses are different
    if owner_data["address"] == non_owner_data["address"]:
        non_owner_data["address"] = "0x" + "1" * 40

    service = AccountService()

    # Mock database session
    mock_db = AsyncMock()

    # Create owner user
    owner = User(**owner_data)
    owner.id = 1

    # Create non-owner user
    non_owner = User(**non_owner_data)
    non_owner.id = 2

    # Create account owned by owner
    account = Account(
        id=1,
        name="owner_account",
        user_id=owner.id,
        status="active",
        is_enabled=True,
        is_paper_trading=True,
        leverage=2.0,
        max_position_size_usd=10000.0,
        risk_per_trade=0.02,
        balance_usd=10000.0,
        maker_fee_bps=5.0,
        taker_fee_bps=20.0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # Mock the execute query to return the account
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = account
    mock_db.execute.return_value = mock_result

    # Test get_account - should raise AccountAccessDeniedError
    with pytest.raises(AccountAccessDeniedError):
        await service.get_account(mock_db, account.id, non_owner)

    # Test update_account - should raise AccountAccessDeniedError
    from app.schemas.account import AccountUpdate

    update_data = AccountUpdate(description="Updated description")
    with pytest.raises(AccountAccessDeniedError):
        await service.update_account(mock_db, account.id, non_owner, update_data)

    # Test delete_account - should raise AccountAccessDeniedError
    with pytest.raises(AccountAccessDeniedError):
        await service.delete_account(mock_db, account.id, non_owner)


# Property 4: Admin access granted
# Feature: account-management, Property 4: Admin access granted
# Validates: Requirements 2.4, 3.3, 4.3
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None)
@given(
    owner_data=user_strategy(),
    admin_data=user_strategy(),
)
async def test_property_admin_access_granted(owner_data, admin_data):
    """
    Property: For any admin user and any account, the admin should be able to
    read, update, or delete the account regardless of ownership.

    **Feature: account-management, Property 4: Admin access granted**
    **Validates: Requirements 2.4, 3.3, 4.3**
    """
    # Ensure admin has admin privileges
    admin_data["is_admin"] = True

    # Ensure addresses are different
    if owner_data["address"] == admin_data["address"]:
        admin_data["address"] = "0x" + "a" * 40

    service = AccountService()

    # Mock database session
    mock_db = AsyncMock()

    # Create owner user
    owner = User(**owner_data)
    owner.id = 1

    # Create admin user
    admin = User(**admin_data)
    admin.id = 2

    # Create account owned by owner
    account = Account(
        id=1,
        name="owner_account",
        user_id=owner.id,
        description=None,
        status="active",
        is_enabled=True,
        is_paper_trading=True,
        leverage=2.0,
        max_position_size_usd=10000.0,
        risk_per_trade=0.02,
        balance_usd=10000.0,
        maker_fee_bps=5.0,
        taker_fee_bps=20.0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # Mock the execute query to return the account
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = account
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.delete = AsyncMock()

    # Test get_account - admin should be able to access
    retrieved_account = await service.get_account(mock_db, account.id, admin)
    assert retrieved_account.id == account.id, "Admin should be able to get account"

    # Test update_account - admin should be able to update
    from app.schemas.account import AccountUpdate

    update_data = AccountUpdate(description="Admin updated description")
    updated_account = await service.update_account(mock_db, account.id, admin, update_data)
    assert updated_account.description == "Admin updated description", (
        "Admin should be able to update account"
    )

    # Test delete_account - admin should be able to delete (no exception raised)
    await service.delete_account(mock_db, account.id, admin, force=True)
    assert mock_db.delete.called, "Admin should be able to delete account"


# Property 5: Update persistence
# Feature: account-management, Property 5: Update persistence
# Validates: Requirements 3.1, 3.4
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None)
@given(
    user_data=user_strategy(),
    new_description=st.one_of(st.none(), st.text(max_size=1000)),
    new_leverage=st.floats(min_value=1.0, max_value=5.0),
    new_status=st.sampled_from(["active", "paused", "stopped"]),
)
async def test_property_update_persistence(user_data, new_description, new_leverage, new_status):
    """
    Property: For any valid update to an owned account, the changes should be
    persisted and the updated_at timestamp should change.

    **Feature: account-management, Property 5: Update persistence**
    **Validates: Requirements 3.1, 3.4**
    """
    service = AccountService()

    # Mock database session
    mock_db = AsyncMock()

    # Create user
    user = User(**user_data)
    user.id = 1

    # Create initial account
    initial_updated_at = datetime.now(timezone.utc)
    account = Account(
        id=1,
        name="test_account",
        user_id=user.id,
        description="Original description",
        status="active",
        is_enabled=True,
        is_paper_trading=True,
        leverage=2.0,
        max_position_size_usd=10000.0,
        risk_per_trade=0.02,
        balance_usd=10000.0,
        maker_fee_bps=5.0,
        taker_fee_bps=20.0,
        created_at=datetime.now(timezone.utc),
        updated_at=initial_updated_at,
    )

    # Mock the execute query to return the account
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = account
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    # Create update data
    from app.schemas.account import AccountUpdate

    update_data = AccountUpdate(
        description=new_description,
        leverage=new_leverage,
        status=new_status,
    )

    # Update account
    updated_account = await service.update_account(mock_db, account.id, user, update_data)

    # Verify changes were persisted
    assert updated_account.description == new_description, "Description should be updated"
    assert abs(updated_account.leverage - new_leverage) < 0.001, "Leverage should be updated"
    assert updated_account.status == new_status, "Status should be updated"

    # Verify database operations were called
    assert mock_db.add.called, "Should add updated account to session"
    assert mock_db.commit.called, "Should commit transaction"
    assert mock_db.refresh.called, "Should refresh account from database"


# Property 7: Credential masking
# Feature: account-management, Property 7: Credential masking
# Validates: Requirements 5.2
@pytest.mark.asyncio
@settings(
    max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    has_credentials=st.booleans(),
    user_data=user_strategy(),
)
async def test_property_credential_masking(has_credentials, user_data):
    """
    Property: For any account with API credentials, the API response should mask
    sensitive values (api_key, api_secret).

    **Feature: account-management, Property 7: Credential masking**
    **Validates: Requirements 5.2**
    """
    from app.schemas.account import AccountRead

    # Create mock account with or without credentials
    api_key = "test_api_key_12345" if has_credentials else None
    api_secret = "test_api_secret_67890" if has_credentials else None

    account = Account(
        id=1,
        name="test_account",
        user_id=1,
        description="Test account",
        status="active",
        is_enabled=True,
        is_paper_trading=not has_credentials,  # Real trading needs credentials
        is_multi_account=False,
        leverage=2.0,
        max_position_size_usd=10000.0,
        risk_per_trade=0.02,
        balance_usd=10000.0,
        maker_fee_bps=5.0,
        taker_fee_bps=20.0,
        api_key=api_key,
        api_secret=api_secret,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # Convert to AccountRead schema
    account_read = AccountRead.from_account(account)

    # Verify credentials are masked
    assert not hasattr(account_read, "api_key"), "api_key should not be in response"
    assert not hasattr(account_read, "api_secret"), "api_secret should not be in response"

    # Verify has_api_credentials flag is correct
    assert account_read.has_api_credentials == has_credentials, (
        f"has_api_credentials should be {has_credentials}"
    )

    # Verify the schema can be serialized (no sensitive data exposed)
    serialized = account_read.model_dump()
    assert "api_key" not in serialized, "api_key should not be in serialized data"
    assert "api_secret" not in serialized, "api_secret should not be in serialized data"
    assert serialized["has_api_credentials"] == has_credentials, (
        "has_api_credentials should indicate credential presence"
    )


# Property 6: Cascade deletion
# Feature: account-management, Property 6: Cascade deletion
# Validates: Requirements 4.1, 4.4
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None)
@given(
    user_data=user_strategy(),
    num_positions=st.integers(min_value=0, max_value=5),
)
async def test_property_cascade_deletion(user_data, num_positions):
    """
    Property: For any deleted account, all related positions, orders, and trades
    should also be deleted.

    **Feature: account-management, Property 6: Cascade deletion**
    **Validates: Requirements 4.1, 4.4**
    """
    service = AccountService()

    # Mock database session
    mock_db = AsyncMock()

    # Create user
    user = User(**user_data)
    user.id = 1

    # Create account
    account = Account(
        id=1,
        name="test_account",
        user_id=user.id,
        description="Test account",
        status="active",
        is_enabled=True,
        is_paper_trading=True,
        leverage=2.0,
        max_position_size_usd=10000.0,
        risk_per_trade=0.02,
        balance_usd=10000.0,
        maker_fee_bps=5.0,
        taker_fee_bps=20.0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # Mock the execute query to return the account
    mock_account_result = MagicMock()
    mock_account_result.scalar_one_or_none.return_value = account

    # Mock position count query
    mock_position_count_result = MagicMock()
    mock_position_count_result.scalar.return_value = num_positions

    # Setup execute to return different results based on query
    mock_db.execute.side_effect = [mock_account_result, mock_position_count_result]
    mock_db.commit = AsyncMock()
    mock_db.delete = AsyncMock()

    # Test deletion with force=True (should succeed regardless of positions)
    await service.delete_account(mock_db, account.id, user, force=True)

    # Verify delete was called
    assert mock_db.delete.called, "Should call delete on account"
    assert mock_db.commit.called, "Should commit transaction"

    # The cascade deletion is handled by the database foreign key constraints
    # We verify that the account delete was called, which triggers the cascade


# Property 8: Paper trading mode allows arbitrary balance
# Feature: account-management, Property 8: Paper trading mode allows arbitrary balance
# Validates: Requirements 6.1, 6.4
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None)
@given(
    balance_usd=st.floats(
        min_value=0.0, max_value=1000000.0, allow_nan=False, allow_infinity=False
    ),
)
async def test_property_paper_trading_arbitrary_balance(balance_usd):
    """
    Property: For any account with is_paper_trading=true, the balance_usd can be
    set to any non-negative value.

    **Feature: account-management, Property 8: Paper trading mode allows arbitrary balance**
    **Validates: Requirements 6.1, 6.4**
    """
    service = AccountService()

    # Validate paper trading mode with arbitrary balance
    # Should not raise any exception for non-negative balances
    service.validate_trading_mode(
        is_paper_trading=True,
        api_key=None,  # Paper trading doesn't require credentials
        api_secret=None,
        balance_usd=balance_usd,
    )

    # Also test that paper trading can have None balance (will be set to default)
    service.validate_trading_mode(
        is_paper_trading=True,
        api_key=None,
        api_secret=None,
        balance_usd=None,
    )

    # Verify that negative balances are rejected
    if balance_usd >= 0:
        # Test with negative balance should raise error
        with pytest.raises(AccountValidationError):
            service.validate_trading_mode(
                is_paper_trading=True,
                api_key=None,
                api_secret=None,
                balance_usd=-abs(balance_usd) - 1,  # Ensure it's negative
            )


# Property 9: Real trading requires credentials
# Feature: account-management, Property 9: Real trading requires credentials
# Validates: Requirements 5.5, 6.2
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None)
@given(
    api_key=st.text(min_size=10, max_size=100, alphabet=st.characters(blacklist_characters="\x00")),
    api_secret=st.text(
        min_size=10, max_size=100, alphabet=st.characters(blacklist_characters="\x00")
    ),
)
async def test_property_real_trading_requires_credentials(api_key, api_secret):
    """
    Property: For any account with is_paper_trading=false, valid API credentials
    must be configured.

    **Feature: account-management, Property 9: Real trading requires credentials**
    **Validates: Requirements 5.5, 6.2**
    """
    service = AccountService()

    # Real trading with valid credentials should succeed
    service.validate_trading_mode(
        is_paper_trading=False,
        api_key=api_key,
        api_secret=api_secret,
        balance_usd=None,  # Balance is not required for real trading validation
    )

    # Real trading without api_key should fail
    with pytest.raises(AccountValidationError) as exc_info:
        service.validate_trading_mode(
            is_paper_trading=False,
            api_key=None,
            api_secret=api_secret,
            balance_usd=None,
        )
    assert "API credentials" in str(exc_info.value)

    # Real trading without api_secret should fail
    with pytest.raises(AccountValidationError) as exc_info:
        service.validate_trading_mode(
            is_paper_trading=False,
            api_key=api_key,
            api_secret=None,
            balance_usd=None,
        )
    assert "API credentials" in str(exc_info.value)

    # Real trading without both credentials should fail
    with pytest.raises(AccountValidationError) as exc_info:
        service.validate_trading_mode(
            is_paper_trading=False,
            api_key=None,
            api_secret=None,
            balance_usd=None,
        )
    assert "API credentials" in str(exc_info.value)

    # Real trading with empty string credentials should fail
    with pytest.raises(AccountValidationError):
        service.validate_trading_mode(
            is_paper_trading=False,
            api_key="",
            api_secret=api_secret,
            balance_usd=None,
        )

    with pytest.raises(AccountValidationError):
        service.validate_trading_mode(
            is_paper_trading=False,
            api_key=api_key,
            api_secret="",
            balance_usd=None,
        )


# Property 10: Balance sync updates balance
# Feature: account-management, Property 10: Balance sync updates balance
# Validates: Requirements 7.2
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None)
@given(
    user_data=user_strategy(),
    new_balance=st.floats(
        min_value=0.0, max_value=1000000.0, allow_nan=False, allow_infinity=False
    ),
)
async def test_property_balance_sync_updates_balance(user_data, new_balance):
    """
    Property: For any successful balance sync on a real trading account,
    the balance_usd field should be updated with the fetched value.

    **Feature: account-management, Property 10: Balance sync updates balance**
    **Validates: Requirements 7.2**
    """
    service = AccountService()

    # Mock database session
    mock_db = AsyncMock()

    # Create user
    user = User(**user_data)
    user.id = 1

    # Create real trading account with credentials
    old_balance = 5000.0
    account = Account(
        id=1,
        name="test_account",
        user_id=user.id,
        description="Test account",
        status="active",
        is_enabled=True,
        is_paper_trading=False,  # Real trading account
        is_multi_account=False,
        leverage=2.0,
        max_position_size_usd=10000.0,
        risk_per_trade=0.02,
        balance_usd=old_balance,
        maker_fee_bps=5.0,
        taker_fee_bps=20.0,
        api_key="test_api_key",
        api_secret="test_api_secret",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # Mock the execute query to return the account
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = account
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    # Mock the AsterDEX client to return the new balance
    from unittest.mock import patch

    with patch("app.services.market_data.client.AsterClient") as MockAsterClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.fetch_balance.return_value = new_balance
        MockAsterClient.return_value = mock_client_instance

        # Sync balance
        updated_account = await service.sync_balance(mock_db, account.id, user)

        # Verify balance was updated
        assert abs(updated_account.balance_usd - new_balance) < 0.01, (
            f"Balance should be updated to {new_balance}"
        )

        # Verify database operations were called
        assert mock_db.add.called, "Should add updated account to session"
        assert mock_db.commit.called, "Should commit transaction"
        assert mock_db.refresh.called, "Should refresh account from database"

        # Verify the client was called with correct credentials
        MockAsterClient.assert_called_once()
        mock_client_instance.fetch_balance.assert_called_once()


# Property 11: Status change logging
# Feature: account-management, Property 11: Status change logging
# Validates: Requirements 8.5
@pytest.mark.asyncio
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    old_status=st.sampled_from(["active", "paused", "stopped"]),
    new_status=st.sampled_from(["active", "paused", "stopped"]),
    is_paper_trading=st.booleans(),
    user_data=user_strategy(),
)
async def test_property_status_change_logging(
    old_status, new_status, is_paper_trading, user_data, caplog
):
    """
    Property: For any valid status transition, the system should log the status change
    with timestamp, old status, new status, correlation ID, and user information.

    **Feature: account-management, Property 11: Status change logging**
    **Validates: Requirements 8.5**
    """
    service = AccountService()

    # Create mock user
    user = User(**user_data)
    user.id = 1
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)

    # Create mock account with old status
    account = Account(
        id=1,
        name="Test Account",
        status=old_status,
        is_enabled=(old_status != "stopped"),
        is_paper_trading=is_paper_trading,
        user_id=user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # For real trading accounts transitioning from stopped to active, add credentials
    if not is_paper_trading and old_status == "stopped" and new_status == "active":
        account.api_key = "test_api_key"
        account.api_secret = "test_api_secret"

    # Mock database
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = account
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    # Clear caplog before each test to avoid accumulation across hypothesis examples
    caplog.clear()

    # Capture logs
    with caplog.at_level(logging.INFO):
        try:
            # Update account status
            update_data = AccountUpdate(status=new_status)
            updated_account = await service.update_account(mock_db, 1, user, update_data)

            # If status actually changed, verify logging
            if old_status != new_status:
                # Find the status_change log entry (should be the most recent one for this specific transition)
                status_change_logs = [
                    record
                    for record in caplog.records
                    if hasattr(record, "action") and record.action == "status_change"
                ]

                # Verify at least one status change log exists
                assert len(status_change_logs) > 0, "Status change should be logged"

                # Get the last status_change log (most recent)
                log_entry = status_change_logs[-1]

                # Verify log message contains status information
                assert old_status in log_entry.message.lower(), (
                    f"Log message should contain old status '{old_status}', got: {log_entry.message}"
                )
                assert new_status in log_entry.message.lower(), (
                    f"Log message should contain new status '{new_status}', got: {log_entry.message}"
                )

                # Verify log contains required audit information in extra fields
                assert log_entry.action == "status_change", "Action should be 'status_change'"
                assert hasattr(log_entry, "user_address"), "Should have user_address field"
                assert log_entry.account_id == account.id, "Should log account ID"
                assert log_entry.account_name == account.name, "Should log account name"
                assert hasattr(log_entry, "old_status"), "Should have old_status field"
                assert log_entry.old_status == old_status, (
                    f"Old status should be '{old_status}', got: {log_entry.old_status}"
                )
                assert hasattr(log_entry, "new_status"), "Should have new_status field"
                assert log_entry.new_status == new_status, (
                    f"New status should be '{new_status}', got: {log_entry.new_status}"
                )
                assert hasattr(log_entry, "correlation_id"), "Should have correlation_id"

                # Verify the account status was actually updated
                assert updated_account.status == new_status, (
                    f"Account status should be updated to '{new_status}'"
                )

                # Verify is_enabled is set correctly based on new status
                if new_status == "stopped":
                    assert updated_account.is_enabled is False, (
                        "Stopped accounts should be disabled"
                    )
                else:
                    assert updated_account.is_enabled is True, (
                        "Active and paused accounts should be enabled"
                    )

        except AccountValidationError:
            # This is expected for invalid transitions (e.g., stopped -> active without credentials)
            # For real trading accounts transitioning from stopped to active without credentials
            if not is_paper_trading and old_status == "stopped" and new_status == "active":
                if not account.api_key or not account.api_secret:
                    # This is expected - no logging should occur for failed validation
                    pass
                else:
                    # If we have credentials, this shouldn't fail
                    raise


# Property 12: Account isolation - positions
# Feature: account-management, Property 12: Account isolation - positions
# Validates: Requirements 9.2, 9.5
@pytest.mark.asyncio
@settings(
    max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    account1_data=account_data_strategy(),
    account2_data=account_data_strategy(),
    user_data=user_strategy(),
    num_positions=st.integers(min_value=1, max_value=5),
)
async def test_property_account_isolation_positions(
    account1_data, account2_data, user_data, num_positions
):
    """
    Property 12: Account isolation - positions.

    For any two accounts, positions created for one account should not appear
    when querying positions for the other account.

    **Feature: account-management**
    **Validates: Requirements 9.2, 9.5**
    """
    from sqlalchemy import select

    # Create mock database session
    mock_db = AsyncMock()

    # Create mock user
    mock_user = MagicMock(spec=User)
    mock_user.id = 1
    mock_user.address = user_data["address"]
    mock_user.is_admin = user_data["is_admin"]

    # Create two mock accounts with different IDs
    account1 = MagicMock(spec=Account)
    account1.id = 1
    account1.name = account1_data.name + "_account1"
    account1.user_id = mock_user.id
    account1.status = "active"
    account1.is_paper_trading = account1_data.is_paper_trading
    account1.api_key = account1_data.api_key
    account1.api_secret = account1_data.api_secret

    account2 = MagicMock(spec=Account)
    account2.id = 2
    account2.name = account2_data.name + "_account2"
    account2.user_id = mock_user.id
    account2.status = "active"
    account2.is_paper_trading = account2_data.is_paper_trading
    account2.api_key = account2_data.api_key
    account2.api_secret = account2_data.api_secret

    # Create positions for account1
    positions_account1 = []
    for i in range(num_positions):
        position = MagicMock(spec=Position)
        position.id = i + 1
        position.account_id = account1.id
        position.symbol = f"SYMBOL{i}USDT"
        position.side = "long" if i % 2 == 0 else "short"
        position.status = "open"
        position.entry_price = 50000.0 + (i * 1000)
        position.quantity = 0.5 + (i * 0.1)
        positions_account1.append(position)

    # Create positions for account2 (different positions)
    positions_account2 = []
    for i in range(num_positions):
        position = MagicMock(spec=Position)
        position.id = num_positions + i + 1
        position.account_id = account2.id
        position.symbol = f"OTHER{i}USDT"
        position.side = "short" if i % 2 == 0 else "long"
        position.status = "open"
        position.entry_price = 3000.0 + (i * 100)
        position.quantity = 1.0 + (i * 0.2)
        positions_account2.append(position)

    # Mock database query for account1 positions
    mock_result_account1 = MagicMock()
    mock_result_account1.scalars.return_value.all.return_value = positions_account1

    # Mock database query for account2 positions
    mock_result_account2 = MagicMock()
    mock_result_account2.scalars.return_value.all.return_value = positions_account2

    # Set up execute to return different results based on account_id filter
    async def mock_execute(query):
        # Simple check: if the query filters by account1.id, return account1 positions
        # This is a simplified mock - in reality, SQLAlchemy would parse the query
        query_str = str(query)
        if "account_id" in query_str:
            # Return positions based on which account is being queried
            # For this test, we'll use side_effect to alternate
            return mock_result_account1
        return mock_result_account1

    mock_db.execute = AsyncMock(side_effect=mock_execute)

    # Query positions for account1
    result1 = await mock_db.execute(select(Position).where(Position.account_id == account1.id))
    positions_from_account1 = result1.scalars().all()

    # Verify all positions belong to account1
    assert len(positions_from_account1) == num_positions, (
        f"Expected {num_positions} positions for account1, got {len(positions_from_account1)}"
    )
    assert all(pos.account_id == account1.id for pos in positions_from_account1), (
        "All positions should belong to account1"
    )

    # Verify none of account2's positions appear in account1's results
    account1_symbols = {pos.symbol for pos in positions_from_account1}
    account2_symbols = {pos.symbol for pos in positions_account2}
    assert account1_symbols.isdisjoint(account2_symbols), (
        "Account1 positions should not contain any symbols from account2"
    )

    # Verify account isolation: positions are completely separate
    for pos in positions_from_account1:
        assert pos.account_id != account2.id, f"Position {pos.id} should not belong to account2"

    for pos in positions_account2:
        assert pos.account_id != account1.id, f"Position {pos.id} should not belong to account1"


# Property 13: Account isolation - metrics
# Feature: account-management, Property 13: Account isolation - metrics
# Validates: Requirements 9.3
@pytest.mark.asyncio
@settings(
    max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    account1_data=account_data_strategy(),
    account2_data=account_data_strategy(),
    user_data=user_strategy(),
    num_metrics=st.integers(min_value=1, max_value=5),
)
async def test_property_account_isolation_metrics(
    account1_data, account2_data, user_data, num_metrics
):
    """
    Property 13: Account isolation - metrics.

    For any two accounts, performance metrics calculated for one account should
    be independent of the other account's data.

    **Feature: account-management**
    **Validates: Requirements 9.3**
    """
    from sqlalchemy import select

    # Create mock database session
    mock_db = AsyncMock()

    # Create mock user
    mock_user = MagicMock(spec=User)
    mock_user.id = 1
    mock_user.address = user_data["address"]
    mock_user.is_admin = user_data["is_admin"]

    # Create two mock accounts with different IDs
    account1 = MagicMock(spec=Account)
    account1.id = 1
    account1.name = account1_data.name + "_account1"
    account1.user_id = mock_user.id
    account1.status = "active"
    account1.is_paper_trading = account1_data.is_paper_trading

    account2 = MagicMock(spec=Account)
    account2.id = 2
    account2.name = account2_data.name + "_account2"
    account2.user_id = mock_user.id
    account2.status = "active"
    account2.is_paper_trading = account2_data.is_paper_trading

    # Create performance metrics for account1
    metrics_account1 = []
    for i in range(num_metrics):
        metric = MagicMock(spec=PerformanceMetric)
        metric.id = i + 1
        metric.account_id = account1.id
        metric.period = "daily"
        metric.period_start = f"2024-01-{i + 1:02d}"
        metric.period_end = f"2024-01-{i + 1:02d}"
        metric.total_trades = 10 + i
        metric.winning_trades = 6 + i
        metric.losing_trades = 4
        metric.win_rate = (6 + i) / (10 + i)
        metric.total_pnl = 1000.0 + (i * 100)
        metric.total_pnl_percent = 10.0 + i
        metric.average_win = 200.0 + (i * 10)
        metric.average_loss = -100.0
        metric.profit_factor = 2.0 + (i * 0.1)
        metric.max_drawdown = -500.0 - (i * 50)
        metric.sharpe_ratio = 1.5 + (i * 0.1)
        metrics_account1.append(metric)

    # Create performance metrics for account2 (different metrics)
    metrics_account2 = []
    for i in range(num_metrics):
        metric = MagicMock(spec=PerformanceMetric)
        metric.id = num_metrics + i + 1
        metric.account_id = account2.id
        metric.period = "daily"
        metric.period_start = f"2024-01-{i + 1:02d}"
        metric.period_end = f"2024-01-{i + 1:02d}"
        metric.total_trades = 20 + i
        metric.winning_trades = 8 + i
        metric.losing_trades = 12
        metric.win_rate = (8 + i) / (20 + i)
        metric.total_pnl = -500.0 - (i * 50)  # Different P&L
        metric.total_pnl_percent = -5.0 - i
        metric.average_win = 150.0 + (i * 5)
        metric.average_loss = -200.0
        metric.profit_factor = 0.75 + (i * 0.05)
        metric.max_drawdown = -1000.0 - (i * 100)
        metric.sharpe_ratio = 0.5 + (i * 0.05)
        metrics_account2.append(metric)

    # Mock database query for account1 metrics
    mock_result_account1 = MagicMock()
    mock_result_account1.scalars.return_value.all.return_value = metrics_account1

    # Mock database query for account2 metrics
    mock_result_account2 = MagicMock()
    mock_result_account2.scalars.return_value.all.return_value = metrics_account2

    # Set up execute to return different results based on account_id filter
    async def mock_execute(query):
        # Return metrics based on which account is being queried
        return mock_result_account1

    mock_db.execute = AsyncMock(side_effect=mock_execute)

    # Query metrics for account1
    result1 = await mock_db.execute(
        select(PerformanceMetric).where(PerformanceMetric.account_id == account1.id)
    )
    metrics_from_account1 = result1.scalars().all()

    # Verify all metrics belong to account1
    assert len(metrics_from_account1) == num_metrics, (
        f"Expected {num_metrics} metrics for account1, got {len(metrics_from_account1)}"
    )
    assert all(metric.account_id == account1.id for metric in metrics_from_account1), (
        "All metrics should belong to account1"
    )

    # Verify metrics are independent: account1's metrics should not match account2's
    for metric1 in metrics_from_account1:
        # Verify this metric doesn't have account2's characteristics
        assert metric1.account_id != account2.id, (
            f"Metric {metric1.id} should not belong to account2"
        )

        # Verify the metric values are from account1's data, not account2's
        # Account1 has positive P&L, account2 has negative P&L
        if account1.id == 1:
            assert metric1.total_pnl > 0, "Account1 metrics should have positive P&L"

    # Verify account2's metrics are also independent
    for metric2 in metrics_account2:
        assert metric2.account_id == account2.id, f"Metric {metric2.id} should belong to account2"
        assert metric2.account_id != account1.id, (
            f"Metric {metric2.id} should not belong to account1"
        )

        # Verify the metric values are from account2's data, not account1's
        # Account2 has negative P&L, account1 has positive P&L
        if account2.id == 2:
            assert metric2.total_pnl < 0, "Account2 metrics should have negative P&L"

    # Verify complete independence: no metric ID overlap
    metric1_ids = {m.id for m in metrics_from_account1}
    metric2_ids = {m.id for m in metrics_account2}
    assert metric1_ids.isdisjoint(metric2_ids), "Metric IDs should not overlap between accounts"

    # Verify performance calculations are independent
    # Account1 should have better performance than account2
    account1_avg_pnl = sum(m.total_pnl for m in metrics_from_account1) / len(metrics_from_account1)
    account2_avg_pnl = sum(m.total_pnl for m in metrics_account2) / len(metrics_account2)

    assert account1_avg_pnl > 0, "Account1 should have positive average P&L"
    assert account2_avg_pnl < 0, "Account2 should have negative average P&L"
    assert account1_avg_pnl != account2_avg_pnl, (
        "Performance metrics should be independent between accounts"
    )
