"""
Integration tests for admin authorization.

Tests the require_admin dependency function to ensure regular users cannot
access admin endpoints.

**Feature: user-management, Property 2: Regular users cannot access admin endpoints**
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.core.security import require_admin
from app.models.account import User


@pytest.mark.asyncio
async def test_require_admin_allows_admin_user():
    """
    Property 2: Regular users cannot access admin endpoints.

    Test that an admin user is allowed through the require_admin dependency.
    This is the positive case to verify the dependency works correctly.

    **Validates: Requirements 1.2, 2.3, 3.3, 4.3**
    """
    # Create a mock admin user
    admin_user = AsyncMock(spec=User)
    admin_user.is_admin = True
    admin_user.id = 1
    admin_user.address = "0x" + "a" * 40

    # Call require_admin with admin user
    result = await require_admin(current_user=admin_user)

    # Should return the user without raising an exception
    assert result == admin_user
    assert result.is_admin is True


@pytest.mark.asyncio
async def test_require_admin_denies_regular_user():
    """
    Property 2: Regular users cannot access admin endpoints.

    Test that a regular (non-admin) user is denied access via require_admin.
    For any regular user attempting to access any admin endpoint, the system
    should raise a 403 Forbidden error.

    **Validates: Requirements 1.2, 2.3, 3.3, 4.3**
    """
    # Create a mock regular user
    regular_user = AsyncMock(spec=User)
    regular_user.is_admin = False
    regular_user.id = 2
    regular_user.address = "0x" + "b" * 40

    # Call require_admin with regular user - should raise HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await require_admin(current_user=regular_user)

    # Verify the exception details
    assert exc_info.value.status_code == 403
    assert "Admin privileges required" in exc_info.value.detail
