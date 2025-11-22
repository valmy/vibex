"""
API routes for user management.

Provides endpoints for admin users to manage other users and their admin status.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.logging import get_logger
from ...core.security import require_admin
from ...db import get_db
from ...models.account import User
from ...schemas.user import UserList, UserRead
from ...services.user_management_service import (
    CannotModifySelfError,
    LastAdminError,
    UserManagementService,
    UserNotFoundError,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/users", tags=["User Management"])

# Initialize service
user_service = UserManagementService()


@router.get("", response_model=UserList)
async def list_users(
    skip: int = Query(0, ge=0, description="Number of users to skip for pagination"),
    limit: int = Query(100, gt=0, le=1000, description="Maximum number of users to return"),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    List all registered users in the system.

    Only admin users can access this endpoint. Returns paginated list of all users
    with their addresses, admin status, and timestamps.

    Args:
        skip: Number of users to skip (pagination offset). Default: 0, must be >= 0
        limit: Maximum number of users to return per page. Default: 100, must be > 0 and <= 1000
        current_user: Currently authenticated admin user (injected via dependency)
        db: Database session (injected via dependency)

    Returns:
        UserList: Paginated response containing users, total count, skip, and limit

    Raises:
        HTTPException: 403 if user is not admin, 401 if not authenticated,
                      422 if pagination parameters are invalid

    Example:
        GET /api/v1/users?skip=0&limit=10
        Response:
        {
            "users": [
                {
                    "id": 1,
                    "address": "0x1234567890123456789012345678901234567890",
                    "is_admin": true,
                    "created_at": "2025-01-01T00:00:00Z",
                    "updated_at": "2025-01-01T00:00:00Z"
                }
            ],
            "total": 42,
            "skip": 0,
            "limit": 10
        }
    """
    try:

        # Get total count
        count_result = await db.execute(select(func.count(User.id)))
        total = count_result.scalar()

        # Get users
        users = await user_service.list_users(db, skip=skip, limit=limit, admin_user=current_user)

        logger.info(
            f"Listed users by admin {current_user.address}",
            extra={
                "admin_address": current_user.address,
                "skip": skip,
                "limit": limit,
                "total": total,
                "action": "list_users",
            },
        )

        return UserList(users=users, total=total, skip=skip, limit=limit)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Error listing users: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users",
        ) from e


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed information about a specific user.

    Only admin users can access this endpoint. Returns complete user information
    including ID, address, admin status, and timestamps.

    Args:
        user_id: The ID of the user to retrieve
        current_user: Currently authenticated admin user (injected via dependency)
        db: Database session (injected via dependency)

    Returns:
        UserRead: Complete user information

    Raises:
        HTTPException: 403 if user is not admin, 401 if not authenticated,
                      404 if user not found

    Example:
        GET /api/v1/users/1
        Response:
        {
            "id": 1,
            "address": "0x1234567890123456789012345678901234567890",
            "is_admin": true,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z"
        }
    """
    try:
        user = await user_service.get_user_by_id(db, user_id, admin_user=current_user)

        if user is None:
            logger.warning(
                f"Admin {current_user.address} attempted to get non-existent user {user_id}",
                extra={
                    "admin_address": current_user.address,
                    "target_user_id": user_id,
                    "action": "get_user",
                },
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} not found",
            )

        logger.info(
            f"Admin {current_user.address} retrieved user {user_id}",
            extra={
                "admin_address": current_user.address,
                "target_user_id": user_id,
                "target_user_address": user.address,
                "action": "get_user",
            },
        )

        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user",
        ) from e


@router.put("/{user_id}/promote", response_model=UserRead)
async def promote_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Promote a user to admin status.

    Only admin users can access this endpoint. Grants admin privileges to the
    specified user, allowing them to manage other users.

    Args:
        user_id: The ID of the user to promote
        current_user: Currently authenticated admin user (injected via dependency)
        db: Database session (injected via dependency)

    Returns:
        UserRead: Updated user information with is_admin set to true

    Raises:
        HTTPException: 403 if user is not admin, 401 if not authenticated,
                      404 if user not found

    Example:
        PUT /api/v1/users/2/promote
        Response:
        {
            "id": 2,
            "address": "0x0987654321098765432109876543210987654321",
            "is_admin": true,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-02T00:00:00Z"
        }
    """
    try:
        user = await user_service.promote_user_to_admin(db, user_id, current_user)

        logger.info(
            f"User {user_id} promoted to admin by {current_user.address}",
            extra={
                "admin_address": current_user.address,
                "target_user_id": user_id,
                "target_user_address": user.address,
                "action": "promote_to_admin",
            },
        )

        return user

    except UserNotFoundError as e:
        logger.warning(
            f"Admin {current_user.address} attempted to promote non-existent user {user_id}",
            extra={
                "admin_address": current_user.address,
                "target_user_id": user_id,
                "action": "promote_to_admin",
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except CannotModifySelfError as e:
        logger.warning(
            f"Admin {current_user.address} attempted to modify their own status",
            extra={
                "admin_address": current_user.address,
                "target_user_id": user_id,
                "action": "promote_to_admin",
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Error promoting user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to promote user",
        ) from e


@router.put("/{user_id}/revoke", response_model=UserRead)
async def revoke_admin(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke admin status from a user.

    Only admin users can access this endpoint. Removes admin privileges from the
    specified user, restricting them to regular user access.

    Args:
        user_id: The ID of the user to revoke admin status from
        current_user: Currently authenticated admin user (injected via dependency)
        db: Database session (injected via dependency)

    Returns:
        UserRead: Updated user information with is_admin set to false

    Raises:
        HTTPException: 403 if user is not admin, 401 if not authenticated,
                      404 if user not found

    Example:
        PUT /api/v1/users/2/revoke
        Response:
        {
            "id": 2,
            "address": "0x0987654321098765432109876543210987654321",
            "is_admin": false,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-02T00:00:00Z"
        }
    """
    try:
        user = await user_service.revoke_admin_status(db, user_id, current_user)

        logger.info(
            f"Admin status revoked from user {user_id} by {current_user.address}",
            extra={
                "admin_address": current_user.address,
                "target_user_id": user_id,
                "target_user_address": user.address,
                "action": "revoke_admin",
            },
        )

        return user

    except UserNotFoundError as e:
        logger.warning(
            f"Admin {current_user.address} attempted to revoke admin from non-existent user {user_id}",
            extra={
                "admin_address": current_user.address,
                "target_user_id": user_id,
                "action": "revoke_admin",
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except CannotModifySelfError as e:
        logger.warning(
            f"Admin {current_user.address} attempted to modify their own status",
            extra={
                "admin_address": current_user.address,
                "target_user_id": user_id,
                "action": "revoke_admin",
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except LastAdminError as e:
        logger.warning(
            f"Admin {current_user.address} attempted to revoke last admin",
            extra={
                "admin_address": current_user.address,
                "target_user_id": user_id,
                "action": "revoke_admin",
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Error revoking admin from user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke admin status",
        ) from e
