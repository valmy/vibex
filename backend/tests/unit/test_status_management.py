"""
Unit tests for account status management.

Tests status transitions, validation, and audit logging.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.account import Account, User
from app.schemas.account import AccountUpdate
from app.services.account_service import (
    AccountService,
    AccountValidationError,
)


@pytest.mark.asyncio
async def test_status_transition_active_to_paused():
    """Test transitioning from active to paused status."""
    service = AccountService()

    # Create mock account
    account = Account(
        id=1,
        name="Test Account",
        status="active",
        is_enabled=True,
        is_paper_trading=True,
        user_id=1,
    )

    # Create mock user
    user = User(id=1, address="0x123", is_admin=False)

    # Mock database
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = account
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    # Update to paused
    update_data = AccountUpdate(status="paused")
    updated = await service.update_account(mock_db, 1, user, update_data)

    assert updated.status == "paused"
    assert updated.is_enabled is True  # Paused accounts remain enabled


@pytest.mark.asyncio
async def test_status_transition_active_to_stopped():
    """Test transitioning from active to stopped status."""
    service = AccountService()

    # Create mock account
    account = Account(
        id=1,
        name="Test Account",
        status="active",
        is_enabled=True,
        is_paper_trading=True,
        user_id=1,
    )

    # Create mock user
    user = User(id=1, address="0x123", is_admin=False)

    # Mock database
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = account
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    # Update to stopped
    update_data = AccountUpdate(status="stopped")
    updated = await service.update_account(mock_db, 1, user, update_data)

    assert updated.status == "stopped"
    assert updated.is_enabled is False  # Stopped accounts are disabled


@pytest.mark.asyncio
async def test_status_transition_stopped_to_active_paper_trading():
    """Test reactivating from stopped to active for paper trading (should succeed)."""
    service = AccountService()

    # Create mock account (paper trading, no credentials needed)
    account = Account(
        id=1,
        name="Test Account",
        status="stopped",
        is_enabled=False,
        is_paper_trading=True,
        user_id=1,
    )

    # Create mock user
    user = User(id=1, address="0x123", is_admin=False)

    # Mock database
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = account
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    # Update to active (should succeed for paper trading)
    update_data = AccountUpdate(status="active")
    updated = await service.update_account(mock_db, 1, user, update_data)

    assert updated.status == "active"
    assert updated.is_enabled is True


@pytest.mark.asyncio
async def test_status_transition_stopped_to_active_real_trading_without_credentials():
    """Test reactivating from stopped to active for real trading without credentials (should fail)."""
    service = AccountService()

    # Create mock account (real trading, no credentials)
    account = Account(
        id=1,
        name="Test Account",
        status="stopped",
        is_enabled=False,
        is_paper_trading=False,
        api_key=None,
        api_secret=None,
        user_id=1,
    )

    # Create mock user
    user = User(id=1, address="0x123", is_admin=False)

    # Mock database
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = account
    mock_db.execute.return_value = mock_result

    # Update to active (should fail - no credentials)
    update_data = AccountUpdate(status="active")
    with pytest.raises(AccountValidationError) as exc_info:
        await service.update_account(mock_db, 1, user, update_data)

    assert "Cannot reactivate stopped account" in str(exc_info.value)
    assert "API credentials" in str(exc_info.value)


@pytest.mark.asyncio
async def test_status_transition_stopped_to_active_real_trading_with_credentials():
    """Test reactivating from stopped to active for real trading with credentials (should succeed)."""
    service = AccountService()

    # Create mock account (real trading, with credentials)
    account = Account(
        id=1,
        name="Test Account",
        status="stopped",
        is_enabled=False,
        is_paper_trading=False,
        api_key="test_key",
        api_secret="test_secret",
        user_id=1,
    )

    # Create mock user
    user = User(id=1, address="0x123", is_admin=False)

    # Mock database
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = account
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    # Update to active (should succeed - has credentials)
    update_data = AccountUpdate(status="active")
    updated = await service.update_account(mock_db, 1, user, update_data)

    assert updated.status == "active"
    assert updated.is_enabled is True


@pytest.mark.asyncio
async def test_status_transition_paused_to_active():
    """Test resuming from paused to active status."""
    service = AccountService()

    # Create mock account
    account = Account(
        id=1,
        name="Test Account",
        status="paused",
        is_enabled=True,
        is_paper_trading=True,
        user_id=1,
    )

    # Create mock user
    user = User(id=1, address="0x123", is_admin=False)

    # Mock database
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = account
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    # Update to active
    update_data = AccountUpdate(status="active")
    updated = await service.update_account(mock_db, 1, user, update_data)

    assert updated.status == "active"
    assert updated.is_enabled is True


@pytest.mark.asyncio
async def test_invalid_status():
    """Test that invalid status values are rejected by Pydantic schema validation."""
    from pydantic import ValidationError

    # Try to create AccountUpdate with invalid status
    # This should be caught by Pydantic schema validation
    with pytest.raises(ValidationError) as exc_info:
        AccountUpdate(status="invalid_status")

    assert "status" in str(exc_info.value)
