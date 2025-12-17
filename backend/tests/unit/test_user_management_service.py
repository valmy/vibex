"""
Property-based tests for user management service.

Tests correctness properties for user management operations using hypothesis.
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import User
from app.services.user_management_service import (
    CannotModifySelfError,
    LastAdminError,
    UserManagementService,
    UserNotFoundError,
)


@pytest.fixture
def user_service():
    """Create a user management service instance."""
    return UserManagementService()


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return AsyncMock(spec=AsyncSession)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_users_returns_all_users(
    user_service: UserManagementService, mock_db_session: AsyncMock
):
    """
    **Feature: user-management, Property 1: Admin list returns all users**

    Test that list_users returns all users in the database.
    **Validates: Requirements 1.1, 1.4**
    """
    # Create mock users
    mock_users = [
        MagicMock(spec=User, id=i, address=f"0x{i:040x}", is_admin=(i % 2 == 0))
        for i in range(1, 6)
    ]

    # Mock the execute method to return users
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_users
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # List all users
    result = await user_service.list_users(mock_db_session, skip=0, limit=100)

    # Verify all users are returned
    assert len(result) == 5
    assert all(isinstance(user, MagicMock) for user in result)
    assert all(user.address in [u.address for u in mock_users] for user in result)


@pytest.mark.unit
@pytest.mark.asyncio
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    skip=st.integers(min_value=0, max_value=10),
    limit=st.integers(min_value=1, max_value=50),
)
async def test_pagination_returns_correct_subset(
    user_service: UserManagementService,
    mock_db_session: AsyncMock,
    skip: int,
    limit: int,
):
    """
    **Feature: user-management, Property 3: Pagination returns correct subset**

    Test that pagination with skip and limit returns the correct subset of users.
    **Validates: Requirements 1.5**
    """
    # Create 20 mock users
    num_users = 20
    mock_users = [
        MagicMock(spec=User, id=i, address=f"0x{i:040x}", is_admin=False)
        for i in range(1, num_users + 1)
    ]

    # Mock the execute method to return paginated users
    mock_result = MagicMock()
    expected_count = min(limit, max(0, num_users - skip))
    paginated_users = mock_users[skip : skip + limit]
    mock_result.scalars.return_value.all.return_value = paginated_users
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Get paginated results
    result = await user_service.list_users(mock_db_session, skip=skip, limit=limit)

    # Verify correct subset is returned
    assert len(result) == expected_count

    # Verify results are ordered by ID
    if len(result) > 1:
        for i in range(len(result) - 1):
            assert result[i].id < result[i + 1].id


@pytest.mark.unit
@pytest.mark.asyncio
async def test_promotion_updates_admin_status(
    user_service: UserManagementService,
    mock_db_session: AsyncMock,
):
    """
    **Feature: user-management, Property 4: Promotion updates admin status**

    Test that promoting a user updates their is_admin field to True.
    **Validates: Requirements 2.1, 2.5**
    """
    # Create mock users
    admin_user = MagicMock(spec=User, id=1, address="0x" + "1" * 40, is_admin=True)
    regular_user = MagicMock(spec=User, id=2, address="0x" + "2" * 40, is_admin=False)

    # Mock the execute method to return the regular user
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = regular_user
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    mock_db_session.refresh = AsyncMock()

    # Promote user
    result = await user_service.promote_user_to_admin(mock_db_session, regular_user.id, admin_user)

    # Verify is_admin is True
    assert result.is_admin is True
    # Verify add was called
    mock_db_session.add.assert_called_once()
    # Verify commit was called
    mock_db_session.commit.assert_called_once()
    # Verify refresh was called
    mock_db_session.refresh.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_revocation_updates_admin_status(
    user_service: UserManagementService,
    mock_db_session: AsyncMock,
):
    """
    **Feature: user-management, Property 5: Revocation updates admin status**

    Test that revoking admin status updates the is_admin field to False.
    **Validates: Requirements 3.1, 3.5**
    """
    # Create mock admin users
    admin_user = MagicMock(spec=User, id=3, address="0x" + "3" * 40, is_admin=True)
    admin_to_revoke = MagicMock(spec=User, id=4, address="0x" + "4" * 40, is_admin=True)

    # Mock the execute method to return the admin user to revoke
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = admin_to_revoke

    # Mock the admin users query to return 2 admins (more than one)
    mock_admin_users_result = MagicMock()
    mock_admin_users_result.scalars.return_value.all.return_value = [admin_user, admin_to_revoke]

    # Setup execute to return different results based on call order
    mock_db_session.execute = AsyncMock(side_effect=[mock_result, mock_admin_users_result])
    mock_db_session.refresh = AsyncMock()

    # Revoke admin status
    result = await user_service.revoke_admin_status(mock_db_session, admin_to_revoke.id, admin_user)

    # Verify is_admin is False
    assert result.is_admin is False
    # Verify add was called
    mock_db_session.add.assert_called_once()
    # Verify commit was called
    mock_db_session.commit.assert_called_once()
    # Verify refresh was called
    mock_db_session.refresh.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_user_by_id_returns_complete_information(
    user_service: UserManagementService,
    mock_db_session: AsyncMock,
):
    """
    **Feature: user-management, Property 6: Get user returns complete information**

    Test that get_user_by_id returns all required user fields.
    **Validates: Requirements 4.1, 4.5**
    """
    # Create a mock user with all required fields
    from datetime import datetime

    mock_user = MagicMock(
        spec=User,
        id=5,
        address="0x" + "d" * 40,
        is_admin=True,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    # Mock the execute method to return the user
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Get user by ID
    result = await user_service.get_user_by_id(mock_db_session, mock_user.id)

    # Verify all required fields are present
    assert result is not None
    assert result.id == mock_user.id
    assert result.address == mock_user.address
    assert result.is_admin is True
    assert result.created_at is not None
    assert result.updated_at is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_user_by_id_returns_none_for_nonexistent_user(
    user_service: UserManagementService,
    mock_db_session: AsyncMock,
):
    """Test that get_user_by_id returns None for non-existent user."""
    # Mock the execute method to return None
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    result = await user_service.get_user_by_id(mock_db_session, 99999)
    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_promote_nonexistent_user_raises_error(
    user_service: UserManagementService,
    mock_db_session: AsyncMock,
):
    """Test that promoting a non-existent user raises UserNotFoundError."""
    # Create mock admin user
    admin_user = MagicMock(spec=User, id=1, address="0x" + "1" * 40, is_admin=True)

    # Mock the execute method to return None
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(UserNotFoundError, match="User with id 99999 not found"):
        await user_service.promote_user_to_admin(mock_db_session, 99999, admin_user)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_revoke_nonexistent_user_raises_error(
    user_service: UserManagementService,
    mock_db_session: AsyncMock,
):
    """Test that revoking admin from a non-existent user raises UserNotFoundError."""
    # Create mock admin user
    admin_user = MagicMock(spec=User, id=1, address="0x" + "1" * 40, is_admin=True)

    # Mock the execute method to return None
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(UserNotFoundError, match="User with id 99999 not found"):
        await user_service.revoke_admin_status(mock_db_session, 99999, admin_user)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_users_with_invalid_skip_raises_error(
    user_service: UserManagementService,
    mock_db_session: AsyncMock,
):
    """Test that list_users with negative skip raises ValueError."""
    with pytest.raises(ValueError, match="skip must be non-negative"):
        await user_service.list_users(mock_db_session, skip=-1, limit=10)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_users_with_invalid_limit_raises_error(
    user_service: UserManagementService,
    mock_db_session: AsyncMock,
):
    """Test that list_users with non-positive limit raises ValueError."""
    with pytest.raises(ValueError, match="limit must be positive"):
        await user_service.list_users(mock_db_session, skip=0, limit=0)


# Audit Logging Property-Based Tests


@pytest.mark.unit
@pytest.mark.asyncio
async def test_promotion_actions_are_logged(
    user_service: UserManagementService,
    mock_db_session: AsyncMock,
    caplog,
):
    """
    **Feature: user-management, Property 7: Promotion actions are logged**

    Test that user promotion actions are logged with correct audit information.
    **Validates: Requirements 6.1**
    """
    # Create mock users
    admin_user = MagicMock(spec=User, id=1, address="0x" + "1" * 40, is_admin=True)
    regular_user = MagicMock(spec=User, id=2, address="0x" + "2" * 40, is_admin=False)

    # Mock the execute method to return the regular user
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = regular_user
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    mock_db_session.refresh = AsyncMock()

    # Capture logs
    with caplog.at_level(logging.INFO):
        # Promote user
        result = await user_service.promote_user_to_admin(
            mock_db_session, regular_user.id, admin_user
        )

    # Verify promotion was successful
    assert result.is_admin is True

    # Verify log entry exists
    assert len(caplog.records) > 0
    log_entry = caplog.records[0]

    # Verify log message
    assert "promoted to admin" in log_entry.message.lower()

    # Verify log contains required audit information in extra fields
    assert log_entry.action == "promote_to_admin"
    assert log_entry.admin_address == admin_user.address
    assert log_entry.target_user_address == regular_user.address
    assert log_entry.target_user_id == str(regular_user.id)
    assert hasattr(log_entry, "correlation_id")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_revocation_actions_are_logged(
    user_service: UserManagementService,
    mock_db_session: AsyncMock,
    caplog,
):
    """
    **Feature: user-management, Property 8: Revocation actions are logged**

    Test that admin status revocation actions are logged with correct audit
    information.
    **Validates: Requirements 6.2**
    """
    # Create mock admin users
    admin_user = MagicMock(spec=User, id=3, address="0x" + "3" * 40, is_admin=True)
    admin_to_revoke = MagicMock(spec=User, id=4, address="0x" + "4" * 40, is_admin=True)

    # Mock the execute method to return the admin user to revoke
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = admin_to_revoke

    # Mock the admin users query to return 2 admins (more than one)
    mock_admin_users_result = MagicMock()
    mock_admin_users_result.scalars.return_value.all.return_value = [admin_user, admin_to_revoke]

    # Setup execute to return different results based on call order
    mock_db_session.execute = AsyncMock(side_effect=[mock_result, mock_admin_users_result])
    mock_db_session.refresh = AsyncMock()

    # Capture logs
    with caplog.at_level(logging.INFO):
        # Revoke admin status
        result = await user_service.revoke_admin_status(
            mock_db_session, admin_to_revoke.id, admin_user
        )

    # Verify revocation was successful
    assert result.is_admin is False

    # Verify log entry exists
    assert len(caplog.records) > 0
    log_entry = caplog.records[0]

    # Verify log message
    assert "admin status revoked" in log_entry.message.lower()

    # Verify log contains required audit information in extra fields
    assert log_entry.action == "revoke_admin"
    assert log_entry.admin_address == admin_user.address
    assert log_entry.target_user_address == admin_to_revoke.address
    assert log_entry.target_user_id == str(admin_to_revoke.id)
    assert hasattr(log_entry, "correlation_id")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_actions_are_logged(
    user_service: UserManagementService,
    mock_db_session: AsyncMock,
    caplog,
):
    """
    **Feature: user-management, Property 9: List actions are logged**

    Test that user list actions are logged with correct audit information.
    **Validates: Requirements 6.3**
    """
    # Create mock users
    admin_user = MagicMock(spec=User, id=1, address="0x" + "1" * 40, is_admin=True)
    mock_users = [
        MagicMock(spec=User, id=i, address=f"0x{i:040x}", is_admin=(i % 2 == 0))
        for i in range(1, 4)
    ]

    # Mock the execute method to return users
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_users
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Capture logs
    with caplog.at_level(logging.INFO):
        # List users
        result = await user_service.list_users(
            mock_db_session, skip=0, limit=100, admin_user=admin_user
        )

    # Verify list was successful
    assert len(result) == 3

    # Verify log entry exists
    assert len(caplog.records) > 0
    log_entry = caplog.records[0]

    # Verify log message
    assert "user list retrieved" in log_entry.message.lower()

    # Verify log contains required audit information in extra fields
    assert log_entry.action == "list_users"
    assert log_entry.admin_address == admin_user.address
    assert hasattr(log_entry, "correlation_id")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_user_actions_are_logged(
    user_service: UserManagementService,
    mock_db_session: AsyncMock,
    caplog,
):
    """
    **Feature: user-management, Property 10: Get user actions are logged**

    Test that get user actions are logged with correct audit information.
    **Validates: Requirements 6.4**
    """
    from datetime import datetime

    # Create mock users
    admin_user = MagicMock(spec=User, id=1, address="0x" + "1" * 40, is_admin=True)
    target_user = MagicMock(
        spec=User,
        id=5,
        address="0x" + "d" * 40,
        is_admin=False,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    # Mock the execute method to return the user
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = target_user
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Capture logs
    with caplog.at_level(logging.INFO):
        # Get user
        result = await user_service.get_user_by_id(
            mock_db_session, target_user.id, admin_user=admin_user
        )

    # Verify get was successful
    assert result is not None
    assert result.id == target_user.id

    # Verify log entry exists
    assert len(caplog.records) > 0
    log_entry = caplog.records[0]

    # Verify log message
    assert "retrieved" in log_entry.message.lower()

    # Verify log contains required audit information in extra fields
    assert log_entry.action == "get_user"
    assert log_entry.admin_address == admin_user.address
    assert log_entry.target_user_address == target_user.address
    assert log_entry.target_user_id == str(target_user.id)
    assert hasattr(log_entry, "correlation_id")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_failed_operations_are_logged(
    user_service: UserManagementService,
    mock_db_session: AsyncMock,
    caplog,
):
    """
    **Feature: user-management, Property 11: Failed operations are logged**

    Test that failed user management operations are logged with error details.
    **Validates: Requirements 6.5**
    """
    # Create mock admin user
    admin_user = MagicMock(spec=User, id=1, address="0x" + "1" * 40, is_admin=True)

    # Mock the execute method to return None (user not found)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Capture logs
    with caplog.at_level(logging.ERROR):
        # Try to promote non-existent user
        with pytest.raises(UserNotFoundError):
            await user_service.promote_user_to_admin(mock_db_session, 99999, admin_user)

    # Verify error log entry exists
    assert len(caplog.records) > 0
    log_entry = caplog.records[0]

    # Verify log message contains error information
    assert "failed to promote" in log_entry.message.lower()
    assert "99999" in log_entry.message

    # Verify log contains error information in extra fields
    assert log_entry.action == "promote_to_admin"
    assert log_entry.admin_address == admin_user.address
    assert log_entry.target_user_id == "99999"
    assert hasattr(log_entry, "error")
    assert "User with id 99999 not found" in log_entry.error
    assert hasattr(log_entry, "correlation_id")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_admin_cannot_promote_self(
    user_service: UserManagementService,
    mock_db_session: AsyncMock,
):
    """Test that an admin cannot promote themselves."""
    # Create mock admin user
    admin_user = MagicMock(spec=User, id=1, address="0x" + "1" * 40, is_admin=True)

    # Mock the execute method to return the admin user
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = admin_user
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(CannotModifySelfError, match="cannot change their own status"):
        await user_service.promote_user_to_admin(mock_db_session, admin_user.id, admin_user)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_admin_cannot_revoke_self(
    user_service: UserManagementService,
    mock_db_session: AsyncMock,
):
    """Test that an admin cannot revoke their own status."""
    # Create mock admin user
    admin_user = MagicMock(spec=User, id=1, address="0x" + "1" * 40, is_admin=True)

    # Mock the execute method to return the admin user
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = admin_user
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(CannotModifySelfError, match="cannot change their own status"):
        await user_service.revoke_admin_status(mock_db_session, admin_user.id, admin_user)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cannot_revoke_last_admin(
    user_service: UserManagementService,
    mock_db_session: AsyncMock,
):
    """Test that the last admin's status cannot be revoked."""
    # Create mock admin users
    admin_user = MagicMock(spec=User, id=1, address="0x" + "1" * 40, is_admin=True)
    target_admin = MagicMock(spec=User, id=2, address="0x" + "2" * 40, is_admin=True)

    # Mock the execute method to return the target admin
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = target_admin

    # Mock the admin users query to return only 1 admin (the one being revoked)
    mock_admin_users_result = MagicMock()
    mock_admin_users_result.scalars.return_value.all.return_value = [target_admin]

    # Setup execute to return different results based on call order
    mock_db_session.execute = AsyncMock(side_effect=[mock_result, mock_admin_users_result])

    with pytest.raises(LastAdminError, match="last admin"):
        await user_service.revoke_admin_status(mock_db_session, target_admin.id, admin_user)
