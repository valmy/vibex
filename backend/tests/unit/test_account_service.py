"""
Unit tests for account service.

Tests account service functions with mocked database access for isolated testing.
Uses AsyncMock for database session to avoid real database dependencies.

**Feature: account-management**
**Validates: Requirements 11.1, 11.2**
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account, User
from app.schemas.account import AccountCreate, AccountUpdate
from app.services.account_service import (
    AccountAccessDeniedError,
    AccountNotFoundError,
    AccountService,
    AccountValidationError,
    DuplicateAccountNameError,
)


@pytest.fixture
def account_service():
    """Create an account service instance."""
    return AccountService()


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_user():
    """Create a mock regular user."""
    user = MagicMock(spec=User)
    user.id = 1
    user.address = "0x" + "1" * 40
    user.is_admin = False
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def mock_admin_user():
    """Create a mock admin user."""
    user = MagicMock(spec=User)
    user.id = 99
    user.address = "0x" + "9" * 40
    user.is_admin = True
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def mock_other_user():
    """Create a mock user (different from mock_user)."""
    user = MagicMock(spec=User)
    user.id = 2
    user.address = "0x" + "2" * 40
    user.is_admin = False
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def sample_account_data():
    """Create sample account creation data for paper trading."""
    return AccountCreate(
        name="Test Account",
        description="Test Description",
        leverage=2.0,
        max_position_size_usd=10000.0,
        risk_per_trade=0.02,
        is_paper_trading=True,
        balance_usd=50000.0,
    )


@pytest.fixture
def sample_real_trading_data():
    """Create sample account creation data for real trading."""
    return AccountCreate(
        name="Real Trading Account",
        description="Real Trading Description",
        leverage=3.0,
        max_position_size_usd=5000.0,
        risk_per_trade=0.01,
        is_paper_trading=False,
        api_key="test_api_key_12345",
        api_secret="test_api_secret_67890",
    )


# Test 1: create_account with valid data and user association
@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_account_with_valid_data(
    account_service: AccountService,
    mock_db_session: AsyncMock,
    mock_user: MagicMock,
    sample_account_data: AccountCreate,
):
    """
    Test that create_account persists account with all settings and associates with user.

    **Feature: account-management**
    **Validates: Requirements 1.1, 1.4**
    """
    # Mock the execute query to return no existing account (no duplicate)
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_execute_result)
    mock_db_session.refresh = AsyncMock()

    # Create account
    result = await account_service.create_account(
        db=mock_db_session,
        user_id=mock_user.id,
        data=sample_account_data,
    )

    # Verify account was created with correct data
    assert result.name == sample_account_data.name
    assert result.description == sample_account_data.description
    assert result.leverage == sample_account_data.leverage
    assert result.max_position_size_usd == sample_account_data.max_position_size_usd
    assert result.risk_per_trade == sample_account_data.risk_per_trade
    assert result.is_paper_trading == sample_account_data.is_paper_trading
    assert result.balance_usd == sample_account_data.balance_usd
    assert result.user_id == mock_user.id
    assert result.status == "active"
    assert result.is_enabled is True

    # Verify database operations were called
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once()


# Test 2: create_account with duplicate name error
@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_account_with_duplicate_name(
    account_service: AccountService,
    mock_db_session: AsyncMock,
    mock_user: MagicMock,
    sample_account_data: AccountCreate,
):
    """
    Test that create_account raises DuplicateAccountNameError for duplicate names.

    **Feature: account-management**
    **Validates: Requirements 1.2**
    """
    # Mock the execute query to return an existing account (duplicate)
    existing_account = MagicMock(spec=Account)
    existing_account.name = sample_account_data.name

    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = existing_account
    mock_db_session.execute = AsyncMock(return_value=mock_execute_result)

    # Attempt to create account with duplicate name
    with pytest.raises(DuplicateAccountNameError) as exc_info:
        await account_service.create_account(
            db=mock_db_session,
            user_id=mock_user.id,
            data=sample_account_data,
        )

    # Verify error message contains account name
    assert sample_account_data.name in str(exc_info.value)

    # Verify no database write operations were called
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()


# Test 3: list_user_accounts with ownership filtering
@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_user_accounts_with_ownership_filtering(
    account_service: AccountService,
    mock_db_session: AsyncMock,
    mock_user: MagicMock,
):
    """
    Test that list_user_accounts returns only accounts owned by the user.

    **Feature: account-management**
    **Validates: Requirements 2.1**
    """
    # Create mock accounts for the user
    mock_accounts = [
        MagicMock(spec=Account, id=i, name=f"Account {i}", user_id=mock_user.id)
        for i in range(1, 4)
    ]

    # Mock the execute method to return user's accounts
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_accounts
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # List user accounts
    result = await account_service.list_user_accounts(
        db=mock_db_session,
        user_id=mock_user.id,
        skip=0,
        limit=100,
    )

    # Verify all returned accounts belong to the user
    assert len(result) == 3
    assert all(account.user_id == mock_user.id for account in result)

    # Verify execute was called (twice: once for accounts, once for user)
    assert mock_db_session.execute.call_count == 2


# Test 4: get_account as owner
@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_account_as_owner(
    account_service: AccountService,
    mock_db_session: AsyncMock,
    mock_user: MagicMock,
):
    """
    Test that get_account returns account when user is the owner.

    **Feature: account-management**
    **Validates: Requirements 2.2**
    """
    # Create mock account owned by user
    mock_account = MagicMock(spec=Account)
    mock_account.id = 1
    mock_account.name = "Test Account"
    mock_account.user_id = mock_user.id

    # Mock the execute method to return the account
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_account
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Get account as owner
    result = await account_service.get_account(
        db=mock_db_session,
        account_id=mock_account.id,
        user=mock_user,
    )

    # Verify account is returned
    assert result.id == mock_account.id
    assert result.name == mock_account.name
    assert result.user_id == mock_user.id


# Test 5: get_account as non-owner
@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_account_as_non_owner(
    account_service: AccountService,
    mock_db_session: AsyncMock,
    mock_user: MagicMock,
    mock_other_user: MagicMock,
):
    """
    Test that get_account raises AccountAccessDeniedError when user is not the owner.

    **Feature: account-management**
    **Validates: Requirements 2.3**
    """
    # Create mock account owned by other user
    mock_account = MagicMock(spec=Account)
    mock_account.id = 1
    mock_account.name = "Other User Account"
    mock_account.user_id = mock_other_user.id

    # Mock the execute method to return the account
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_account
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Attempt to get account as non-owner
    with pytest.raises(AccountAccessDeniedError) as exc_info:
        await account_service.get_account(
            db=mock_db_session,
            account_id=mock_account.id,
            user=mock_user,
        )

    # Verify error message
    assert "does not have access" in str(exc_info.value).lower()


# Test 6: get_account as admin
@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_account_as_admin(
    account_service: AccountService,
    mock_db_session: AsyncMock,
    mock_admin_user: MagicMock,
    mock_other_user: MagicMock,
):
    """
    Test that get_account returns account when user is admin (regardless of ownership).

    **Feature: account-management**
    **Validates: Requirements 2.4**
    """
    # Create mock account owned by other user
    mock_account = MagicMock(spec=Account)
    mock_account.id = 1
    mock_account.name = "Other User Account"
    mock_account.user_id = mock_other_user.id

    # Mock the execute method to return the account
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_account
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Get account as admin
    result = await account_service.get_account(
        db=mock_db_session,
        account_id=mock_account.id,
        user=mock_admin_user,
    )

    # Verify account is returned (admin can access any account)
    assert result.id == mock_account.id
    assert result.name == mock_account.name


# Test 7: update_account as owner
@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_account_as_owner(
    account_service: AccountService,
    mock_db_session: AsyncMock,
    mock_user: MagicMock,
):
    """
    Test that update_account persists changes when user is the owner.

    **Feature: account-management**
    **Validates: Requirements 3.1**
    """
    # Create mock account owned by user
    mock_account = MagicMock(spec=Account)
    mock_account.id = 1
    mock_account.name = "Original Name"
    mock_account.user_id = mock_user.id
    mock_account.status = "active"
    mock_account.is_paper_trading = True

    # Mock the execute method to return the account
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_account
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    mock_db_session.refresh = AsyncMock()

    # Update data
    update_data = AccountUpdate(
        name="Updated Name",
        description="Updated Description",
    )

    # Update account as owner
    result = await account_service.update_account(
        db=mock_db_session,
        account_id=mock_account.id,
        user=mock_user,
        data=update_data,
    )

    # Verify account was updated
    assert result.name == "Updated Name"
    assert result.description == "Updated Description"

    # Verify database operations were called
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once()


# Test 8: update_account as non-owner
@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_account_as_non_owner(
    account_service: AccountService,
    mock_db_session: AsyncMock,
    mock_user: MagicMock,
    mock_other_user: MagicMock,
):
    """
    Test that update_account raises AccountAccessDeniedError when user is not the owner.

    **Feature: account-management**
    **Validates: Requirements 3.2**
    """
    # Create mock account owned by other user
    mock_account = MagicMock(spec=Account)
    mock_account.id = 1
    mock_account.name = "Other User Account"
    mock_account.user_id = mock_other_user.id

    # Mock the execute method to return the account
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_account
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Update data
    update_data = AccountUpdate(name="Hacked Name")

    # Attempt to update account as non-owner
    with pytest.raises(AccountAccessDeniedError) as exc_info:
        await account_service.update_account(
            db=mock_db_session,
            account_id=mock_account.id,
            user=mock_user,
            data=update_data,
        )

    # Verify error message
    assert "does not have access" in str(exc_info.value).lower()

    # Verify no database write operations were called
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()


# Test 9: update_account as admin
@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_account_as_admin(
    account_service: AccountService,
    mock_db_session: AsyncMock,
    mock_admin_user: MagicMock,
    mock_other_user: MagicMock,
):
    """
    Test that update_account persists changes when user is admin (regardless of ownership).

    **Feature: account-management**
    **Validates: Requirements 3.3**
    """
    # Create mock account owned by other user
    mock_account = MagicMock(spec=Account)
    mock_account.id = 1
    mock_account.name = "Original Name"
    mock_account.user_id = mock_other_user.id
    mock_account.status = "active"
    mock_account.is_paper_trading = True

    # Mock the execute method to return the account
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_account
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    mock_db_session.refresh = AsyncMock()

    # Update data
    update_data = AccountUpdate(name="Admin Updated Name")

    # Update account as admin
    result = await account_service.update_account(
        db=mock_db_session,
        account_id=mock_account.id,
        user=mock_admin_user,
        data=update_data,
    )

    # Verify account was updated (admin can update any account)
    assert result.name == "Admin Updated Name"

    # Verify database operations were called
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once()


# Test 10: delete_account with cascade verification
@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_account_with_cascade(
    account_service: AccountService,
    mock_db_session: AsyncMock,
    mock_user: MagicMock,
):
    """
    Test that delete_account removes account and cascades to related data.

    **Feature: account-management**
    **Validates: Requirements 4.1, 4.4**
    """
    # Create mock account owned by user
    mock_account = MagicMock(spec=Account)
    mock_account.id = 1
    mock_account.name = "Account to Delete"
    mock_account.user_id = mock_user.id

    # Mock the execute method to return the account
    mock_get_result = MagicMock()
    mock_get_result.scalar_one_or_none.return_value = mock_account

    # Mock the positions query to return no active positions
    mock_positions_result = MagicMock()
    mock_positions_result.scalar.return_value = 0

    # Set up execute to return different results for different queries
    mock_db_session.execute = AsyncMock(side_effect=[mock_get_result, mock_positions_result])

    # Delete account
    await account_service.delete_account(
        db=mock_db_session,
        account_id=mock_account.id,
        user=mock_user,
        force=False,
    )

    # Verify delete was called
    mock_db_session.delete.assert_called_once_with(mock_account)
    mock_db_session.commit.assert_called_once()


# Test 11: validate_trading_mode for paper trading
@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_trading_mode_paper_trading(
    account_service: AccountService,
    sample_account_data: AccountCreate,
):
    """
    Test that validate_trading_mode allows paper trading without API credentials.

    **Feature: account-management**
    **Validates: Requirements 6.1, 6.4**
    """
    # Paper trading data (no API credentials)
    assert sample_account_data.is_paper_trading is True
    assert sample_account_data.api_key is None
    assert sample_account_data.api_secret is None

    # Validate trading mode - should not raise any exception
    try:
        account_service.validate_trading_mode(
            is_paper_trading=sample_account_data.is_paper_trading,
            api_key=sample_account_data.api_key,
            api_secret=sample_account_data.api_secret,
            balance_usd=sample_account_data.balance_usd,
        )
    except AccountValidationError:
        pytest.fail("validate_trading_mode raised AccountValidationError for valid paper trading")


# Test 12: validate_trading_mode for real trading with credentials
@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_trading_mode_real_trading_with_credentials(
    account_service: AccountService,
    sample_real_trading_data: AccountCreate,
):
    """
    Test that validate_trading_mode allows real trading with API credentials.

    **Feature: account-management**
    **Validates: Requirements 5.5, 6.2**
    """
    # Real trading data with API credentials
    assert sample_real_trading_data.is_paper_trading is False
    assert sample_real_trading_data.api_key is not None
    assert sample_real_trading_data.api_secret is not None

    # Validate trading mode - should not raise any exception
    try:
        account_service.validate_trading_mode(
            is_paper_trading=sample_real_trading_data.is_paper_trading,
            api_key=sample_real_trading_data.api_key,
            api_secret=sample_real_trading_data.api_secret,
            balance_usd=sample_real_trading_data.balance_usd,
        )
    except AccountValidationError:
        pytest.fail("validate_trading_mode raised AccountValidationError for valid real trading")


# Test 13: validate_trading_mode for real trading without credentials
@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_trading_mode_real_trading_without_credentials(
    account_service: AccountService,
):
    """
    Test that validate_trading_mode rejects real trading without API credentials.

    **Feature: account-management**
    **Validates: Requirements 5.5, 6.2**
    """
    # Validate trading mode - should raise AccountValidationError
    with pytest.raises(AccountValidationError) as exc_info:
        account_service.validate_trading_mode(
            is_paper_trading=False,  # Real trading
            api_key=None,  # No credentials
            api_secret=None,
            balance_usd=None,
        )

    # Verify error message mentions credentials
    assert "credential" in str(exc_info.value).lower()


# Test 14: get_account when account not found
@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_account_not_found(
    account_service: AccountService,
    mock_db_session: AsyncMock,
    mock_user: MagicMock,
):
    """
    Test that get_account raises AccountNotFoundError when account doesn't exist.

    **Feature: account-management**
    **Validates: Requirements 2.2**
    """
    # Mock the execute method to return None (account not found)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Attempt to get non-existent account
    with pytest.raises(AccountNotFoundError) as exc_info:
        await account_service.get_account(
            db=mock_db_session,
            account_id=999,
            user=mock_user,
        )

    # Verify error message contains account ID
    assert "999" in str(exc_info.value)
