"""Unit tests for security middleware functions."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from src.app.core.security import require_account_owner, require_admin_or_owner
from src.app.models.account import Account, User


@pytest.mark.asyncio
async def test_require_account_owner_success():
    """Test that account owner can access their account."""
    # Create mock user
    user = User(address="0x123", is_admin=False)
    user.id = 1

    # Create mock account
    account = Account(
        name="Test Account",
        user_id=1,
        leverage=2.0,
        max_position_size_usd=10000.0,
        risk_per_trade=0.02,
        balance_usd=10000.0,
        is_paper_trading=True,
    )
    account.id = 100

    # Mock database session
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = account
    mock_db.execute.return_value = mock_result

    # Test that owner can access
    result = await require_account_owner(
        account_id=100,
        current_user=user,
        db=mock_db,
    )

    assert result.id == 100
    assert result.user_id == 1


@pytest.mark.asyncio
async def test_require_account_owner_not_found():
    """Test that 404 is raised for non-existent account."""
    # Create mock user
    user = User(address="0x123", is_admin=False)
    user.id = 1

    # Mock database session - account not found
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    # Test that 404 is raised for non-existent account
    with pytest.raises(HTTPException) as exc_info:
        await require_account_owner(
            account_id=99999,
            current_user=user,
            db=mock_db,
        )

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_require_account_owner_forbidden():
    """Test that 403 is raised when user doesn't own the account."""
    # Create mock users
    owner = User(address="0x123", is_admin=False)
    owner.id = 1

    non_owner = User(address="0x456", is_admin=False)
    non_owner.id = 2

    # Create mock account owned by first user
    account = Account(
        name="Test Account",
        user_id=1,
        leverage=2.0,
        max_position_size_usd=10000.0,
        risk_per_trade=0.02,
        balance_usd=10000.0,
        is_paper_trading=True,
    )
    account.id = 100

    # Mock database session
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = account
    mock_db.execute.return_value = mock_result

    # Test that non-owner gets 403
    with pytest.raises(HTTPException) as exc_info:
        await require_account_owner(
            account_id=100,
            current_user=non_owner,
            db=mock_db,
        )

    assert exc_info.value.status_code == 403
    assert "do not have access" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_require_admin_or_owner_owner_success():
    """Test that account owner can access their account."""
    # Create mock user
    user = User(address="0x123", is_admin=False)
    user.id = 1

    # Create mock account
    account = Account(
        name="Test Account",
        user_id=1,
        leverage=2.0,
        max_position_size_usd=10000.0,
        risk_per_trade=0.02,
        balance_usd=10000.0,
        is_paper_trading=True,
    )
    account.id = 100

    # Mock database session
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = account
    mock_db.execute.return_value = mock_result

    # Test that owner can access
    result = await require_admin_or_owner(
        account_id=100,
        current_user=user,
        db=mock_db,
    )

    assert result.id == 100
    assert result.user_id == 1


@pytest.mark.asyncio
async def test_require_admin_or_owner_admin_success():
    """Test that admin can access any account."""
    # Create mock users
    owner = User(address="0x123", is_admin=False)
    owner.id = 1

    admin = User(address="0x456", is_admin=True)
    admin.id = 2

    # Create mock account owned by first user
    account = Account(
        name="Test Account",
        user_id=1,
        leverage=2.0,
        max_position_size_usd=10000.0,
        risk_per_trade=0.02,
        balance_usd=10000.0,
        is_paper_trading=True,
    )
    account.id = 100

    # Mock database session
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = account
    mock_db.execute.return_value = mock_result

    # Test that admin can access
    result = await require_admin_or_owner(
        account_id=100,
        current_user=admin,
        db=mock_db,
    )

    assert result.id == 100
    assert result.user_id == 1  # Account still owned by owner


@pytest.mark.asyncio
async def test_require_admin_or_owner_not_found():
    """Test that 404 is raised for non-existent account."""
    # Create mock user
    user = User(address="0x123", is_admin=False)
    user.id = 1

    # Mock database session - account not found
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    # Test that 404 is raised for non-existent account
    with pytest.raises(HTTPException) as exc_info:
        await require_admin_or_owner(
            account_id=99999,
            current_user=user,
            db=mock_db,
        )

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_require_admin_or_owner_forbidden():
    """Test that 403 is raised when user is neither admin nor owner."""
    # Create mock users
    owner = User(address="0x123", is_admin=False)
    owner.id = 1

    non_owner = User(address="0x456", is_admin=False)
    non_owner.id = 2

    # Create mock account owned by first user
    account = Account(
        name="Test Account",
        user_id=1,
        leverage=2.0,
        max_position_size_usd=10000.0,
        risk_per_trade=0.02,
        balance_usd=10000.0,
        is_paper_trading=True,
    )
    account.id = 100

    # Mock database session
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = account
    mock_db.execute.return_value = mock_result

    # Test that non-owner non-admin gets 403
    with pytest.raises(HTTPException) as exc_info:
        await require_admin_or_owner(
            account_id=100,
            current_user=non_owner,
            db=mock_db,
        )

    assert exc_info.value.status_code == 403
    assert "do not have access" in exc_info.value.detail.lower()
