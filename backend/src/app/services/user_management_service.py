"""
User management service for admin operations.

Provides business logic for managing users and admin privileges.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.account import User

logger = logging.getLogger(__name__)


class UserManagementService:
    """Service for managing users and admin privileges."""

    def _log_structured(
        self,
        level: str,
        message: str,
        correlation_id: str,
        action: str,
        admin_address: Optional[str] = None,
        target_user_address: Optional[str] = None,
        target_user_id: Optional[int] = None,
        error: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log a structured audit event using logger's extra parameter.

        Args:
            level: Log level (INFO, ERROR, WARNING)
            message: Human-readable message
            correlation_id: Unique request correlation ID
            action: Action being performed
            admin_address: Address of admin performing action
            target_user_address: Address of target user (if applicable)
            target_user_id: ID of target user (if applicable)
            error: Error message (if applicable)
            error_details: Additional error details
        """
        log_data = {
            "correlation_id": correlation_id,
            "action": action,
        }

        if admin_address:
            log_data["admin_address"] = admin_address
        if target_user_address:
            log_data["target_user_address"] = target_user_address
        if target_user_id is not None:
            log_data["target_user_id"] = target_user_id
        if error:
            log_data["error"] = error
        if error_details:
            log_data["error_details"] = error_details

        if level == "INFO":
            logger.info(message, extra=log_data)
        elif level == "ERROR":
            logger.error(message, extra=log_data)
        elif level == "WARNING":
            logger.warning(message, extra=log_data)

    async def list_users(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        admin_user: Optional[User] = None,
    ) -> List[User]:
        """
        List all users with pagination support.

        Args:
            db: Database session
            skip: Number of users to skip (default: 0)
            limit: Maximum number of users to return (default: 100)
            admin_user: The admin user performing the action (for audit logging)

        Returns:
            List of User objects

        Raises:
            ValueError: If skip or limit are negative
        """
        correlation_id = str(uuid.uuid4())

        try:
            if skip < 0:
                raise ValueError("skip must be non-negative")
            if limit <= 0:
                raise ValueError("limit must be positive")

            result = await db.execute(select(User).offset(skip).limit(limit).order_by(User.id))
            users = result.scalars().all()

            # Log successful list operation
            if admin_user:
                self._log_structured(
                    level="INFO",
                    message=f"User list retrieved by {admin_user.address}",
                    correlation_id=correlation_id,
                    action="list_users",
                    admin_address=admin_user.address,
                )

            return list(users)
        except ValueError as e:
            # Log failed list operation
            if admin_user:
                self._log_structured(
                    level="ERROR",
                    message=f"Failed to list users: {str(e)}",
                    correlation_id=correlation_id,
                    action="list_users",
                    admin_address=admin_user.address,
                    error=str(e),
                    error_details={"skip": skip, "limit": limit},
                )
            raise

    async def get_user_by_id(
        self,
        db: AsyncSession,
        user_id: int,
        admin_user: Optional[User] = None,
    ) -> Optional[User]:
        """
        Get a user by ID.

        Args:
            db: Database session
            user_id: The user ID to retrieve
            admin_user: The admin user performing the action (for audit logging)

        Returns:
            User object if found, None otherwise
        """
        correlation_id = str(uuid.uuid4())

        try:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            # Log successful get operation
            if admin_user and user:
                self._log_structured(
                    level="INFO",
                    message=f"User {user_id} retrieved by {admin_user.address}",
                    correlation_id=correlation_id,
                    action="get_user",
                    admin_address=admin_user.address,
                    target_user_id=user_id,
                    target_user_address=user.address,
                )

            return user
        except Exception as e:
            # Log failed get operation
            if admin_user:
                self._log_structured(
                    level="ERROR",
                    message=f"Failed to get user {user_id}: {str(e)}",
                    correlation_id=correlation_id,
                    action="get_user",
                    admin_address=admin_user.address,
                    target_user_id=user_id,
                    error=str(e),
                )
            raise

    async def promote_user_to_admin(
        self,
        db: AsyncSession,
        user_id: int,
        admin_user: User,
    ) -> User:
        """
        Promote a user to admin status.

        Args:
            db: Database session
            user_id: The user ID to promote
            admin_user: The admin user performing the action (for audit logging)

        Returns:
            Updated User object with is_admin set to True

        Raises:
            ValueError: If user not found
        """
        correlation_id = str(uuid.uuid4())

        try:
            result = await db.execute(select(User).where(User.id == user_id).with_for_update())
            user = result.scalar_one_or_none()

            if user is None:
                raise ValueError(f"User with id {user_id} not found")

            if user.id == admin_user.id:
                raise ValueError("Admins cannot change their own status")

            user.is_admin = True
            db.add(user)
            await db.commit()
            await db.refresh(user)

            # Log successful promotion
            self._log_structured(
                level="INFO",
                message=f"User {user_id} promoted to admin by {admin_user.address}",
                correlation_id=correlation_id,
                action="promote_to_admin",
                admin_address=admin_user.address,
                target_user_id=user_id,
                target_user_address=user.address,
            )

            return user
        except ValueError as e:
            # Log failed promotion
            self._log_structured(
                level="ERROR",
                message=f"Failed to promote user {user_id}: {str(e)}",
                correlation_id=correlation_id,
                action="promote_to_admin",
                admin_address=admin_user.address,
                target_user_id=user_id,
                error=str(e),
            )
            raise
        except Exception as e:
            # Log unexpected errors
            self._log_structured(
                level="ERROR",
                message=f"Unexpected error promoting user {user_id}: {str(e)}",
                correlation_id=correlation_id,
                action="promote_to_admin",
                admin_address=admin_user.address,
                target_user_id=user_id,
                error=str(e),
                error_details={"error_type": type(e).__name__},
            )
            raise

    async def revoke_admin_status(
        self,
        db: AsyncSession,
        user_id: int,
        admin_user: User,
    ) -> User:
        """
        Revoke admin status from a user.

        Args:
            db: Database session
            user_id: The user ID to revoke admin status from
            admin_user: The admin user performing the action (for audit logging)

        Returns:
            Updated User object with is_admin set to False

        Raises:
            ValueError: If user not found
        """
        correlation_id = str(uuid.uuid4())

        try:
            result = await db.execute(select(User).where(User.id == user_id).with_for_update())
            user = result.scalar_one_or_none()

            if user is None:
                raise ValueError(f"User with id {user_id} not found")

            if user.id == admin_user.id:
                raise ValueError("Admins cannot change their own status")

            user.is_admin = False
            db.add(user)
            await db.commit()
            await db.refresh(user)

            # Log successful revocation
            self._log_structured(
                level="INFO",
                message=f"Admin status revoked from user {user_id} by {admin_user.address}",
                correlation_id=correlation_id,
                action="revoke_admin",
                admin_address=admin_user.address,
                target_user_id=user_id,
                target_user_address=user.address,
            )

            return user
        except ValueError as e:
            # Log failed revocation
            self._log_structured(
                level="ERROR",
                message=f"Failed to revoke admin from user {user_id}: {str(e)}",
                correlation_id=correlation_id,
                action="revoke_admin",
                admin_address=admin_user.address,
                target_user_id=user_id,
                error=str(e),
            )
            raise
        except Exception as e:
            # Log unexpected errors
            self._log_structured(
                level="ERROR",
                message=f"Unexpected error revoking admin from user {user_id}: {str(e)}",
                correlation_id=correlation_id,
                action="revoke_admin",
                admin_address=admin_user.address,
                target_user_id=user_id,
                error=str(e),
                error_details={"error_type": type(e).__name__},
            )
            raise
