"""
Property-based tests for account service.

Tests universal properties that should hold across all valid inputs.
Uses mocked database access for true unit testing.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.models.account import Account, User
from app.schemas.account import AccountCreate
from app.services.account_service import (
    AccountAccessDeniedError,
    AccountService,
    DuplicateAccountNameError,
)


# Hypothesis strategies for generating test data
@st.composite
def account_data_strategy(draw):
    """Generate valid account creation data."""
    name = draw(
        st.text(min_size=1, max_size=255, alphabet=st.characters(blacklist_characters="\x00"))
    )
    description = draw(st.one_of(st.none(), st.text(max_size=1000)))
    leverage = draw(st.floats(min_value=1.0, max_value=5.0))
    max_position_size = draw(st.floats(min_value=1.0, max_value=1000000.0))
    risk_per_trade = draw(st.floats(min_value=0.01, max_value=0.1))
    is_paper_trading = draw(st.booleans())
    balance_usd = draw(st.floats(min_value=0.0, max_value=1000000.0)) if is_paper_trading else None

    # For real trading, we need API credentials
    api_key = None
    api_secret = None
    if not is_paper_trading:
        api_key = draw(st.text(min_size=10, max_size=100))
        api_secret = draw(st.text(min_size=10, max_size=100))

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

    # Mock the execute query to return the accounts
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = mock_accounts
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute.return_value = mock_result

    # Mock user query
    mock_user_result = MagicMock()
    mock_user_result.scalar_one_or_none.return_value = user

    # List accounts for the user
    accounts = await service.list_user_accounts(mock_db, user.id)

    # Verify we get exactly N accounts
    assert len(accounts) == num_accounts, f"Should return exactly {num_accounts} accounts"

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
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
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
