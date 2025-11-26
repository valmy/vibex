"""
Account management service for trading accounts.

Provides business logic for managing trading accounts with ownership control,
trading mode validation, and balance synchronization.
"""

import logging
import uuid
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.account import Account, User
from ..schemas.account import AccountCreate, AccountUpdate

logger = logging.getLogger(__name__)


class AccountServiceError(Exception):
    """Base exception for account service errors."""

    pass


class AccountNotFoundError(AccountServiceError):
    """Raised when an account is not found."""

    pass


class AccountAccessDeniedError(AccountServiceError):
    """Raised when user doesn't have access to an account."""

    pass


class AccountValidationError(AccountServiceError):
    """Raised when account validation fails."""

    pass


class DuplicateAccountNameError(AccountServiceError):
    """Raised when attempting to create an account with a duplicate name."""

    pass


class ActivePositionsError(AccountServiceError):
    """Raised when trying to delete account with active positions."""

    pass


class BalanceSyncError(AccountServiceError):
    """Raised when balance sync fails."""

    pass


class InvalidApiCredentialsError(BalanceSyncError):
    """Raised when API credentials are invalid (401 Unauthorized)."""

    pass


class ExternalApiError(BalanceSyncError):
    """Raised when external API (AsterDEX) returns an error (502 Bad Gateway)."""

    pass


class StatusTransitionError(AccountServiceError):
    """Raised when an invalid status transition is attempted."""

    pass


class AccountService:
    """Service for managing trading accounts with ownership control."""

    def _log_structured(
        self,
        level: str,
        message: str,
        correlation_id: str,
        action: str,
        user_address: Optional[str] = None,
        account_id: Optional[int] = None,
        account_name: Optional[str] = None,
        error: Optional[str] = None,
        old_status: Optional[str] = None,
        new_status: Optional[str] = None,
    ) -> None:
        """
        Log a structured audit event.

        Args:
            level: Log level (INFO, ERROR, WARNING)
            message: Human-readable message
            correlation_id: Unique request correlation ID
            action: Action being performed
            user_address: Address of user performing action
            account_id: ID of account (if applicable)
            account_name: Name of account (if applicable)
            error: Error message (if applicable)
            old_status: Previous status (for status changes)
            new_status: New status (for status changes)
        """
        log_data = {
            "correlation_id": correlation_id,
            "action": action,
        }

        if user_address:
            log_data["user_address"] = user_address
        if account_id is not None:
            log_data["account_id"] = account_id
        if account_name:
            log_data["account_name"] = account_name
        if error:
            log_data["error"] = error
        if old_status:
            log_data["old_status"] = old_status
        if new_status:
            log_data["new_status"] = new_status

        if level == "INFO":
            logger.info(message, extra=log_data)
        elif level == "ERROR":
            logger.error(message, extra=log_data)
        elif level == "WARNING":
            logger.warning(message, extra=log_data)

    async def create_account(
        self,
        db: AsyncSession,
        user_id: int,
        data: AccountCreate,
    ) -> Account:
        """
        Create a new account for the user.

        Args:
            db: Database session
            user_id: ID of the user creating the account
            data: Account creation data

        Returns:
            Created Account object

        Raises:
            DuplicateAccountNameError: If account name already exists
            AccountValidationError: If validation fails
        """
        correlation_id = str(uuid.uuid4())

        try:
            # Check for duplicate name
            result = await db.execute(select(Account).where(Account.name == data.name))
            existing = result.scalar_one_or_none()
            if existing:
                raise DuplicateAccountNameError(f"Account with name '{data.name}' already exists")

            # Validate trading mode
            self.validate_trading_mode(
                is_paper_trading=data.is_paper_trading,
                api_key=data.api_key,
                api_secret=data.api_secret,
                balance_usd=data.balance_usd,
            )

            # Create account
            account = Account(
                name=data.name,
                description=data.description,
                user_id=user_id,
                api_key=data.api_key,
                api_secret=data.api_secret,
                api_passphrase=data.api_passphrase,
                leverage=data.leverage,
                max_position_size_usd=data.max_position_size_usd,
                risk_per_trade=data.risk_per_trade,
                is_paper_trading=data.is_paper_trading,
                is_multi_account=data.is_multi_account,
                status="active",
                is_enabled=True,
            )

            # Set initial balance for paper trading
            if data.is_paper_trading and hasattr(data, "balance_usd") and data.balance_usd:
                account.balance_usd = data.balance_usd

            db.add(account)
            await db.commit()
            await db.refresh(account)

            # Get user for logging
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()

            self._log_structured(
                level="INFO",
                message=f"Account '{account.name}' created by user {user_id}",
                correlation_id=correlation_id,
                action="create_account",
                user_address=user.address if user else None,
                account_id=account.id,
                account_name=account.name,
            )

            return account

        except (DuplicateAccountNameError, AccountValidationError) as e:
            self._log_structured(
                level="ERROR",
                message=f"Failed to create account: {str(e)}",
                correlation_id=correlation_id,
                action="create_account",
                account_name=data.name,
                error=str(e),
            )
            raise
        except Exception as e:
            self._log_structured(
                level="ERROR",
                message=f"Unexpected error creating account: {str(e)}",
                correlation_id=correlation_id,
                action="create_account",
                account_name=data.name,
                error=str(e),
            )
            raise

    async def list_user_accounts(
        self,
        db: AsyncSession,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[List[Account], int]:
        """
        List all accounts owned by the user with total count.

        Args:
            db: Database session
            user_id: ID of the user
            skip: Number of accounts to skip (default: 0)
            limit: Maximum number of accounts to return (default: 100)

        Returns:
            Tuple of (List of Account objects owned by the user, total count)

        Raises:
            ValueError: If skip or limit are invalid
        """
        correlation_id = str(uuid.uuid4())

        try:
            if skip < 0:
                raise ValueError("skip must be non-negative")
            if limit <= 0:
                raise ValueError("limit must be positive")

            # Get total count for this user
            count_result = await db.execute(
                select(func.count(Account.id)).where(Account.user_id == user_id)
            )
            total = count_result.scalar()

            # Get paginated accounts
            result = await db.execute(
                select(Account)
                .where(Account.user_id == user_id)
                .offset(skip)
                .limit(limit)
                .order_by(Account.id)
            )
            accounts = result.scalars().all()

            # Get user for logging
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()

            self._log_structured(
                level="INFO",
                message=f"Listed {len(accounts)} accounts for user {user_id} (total: {total})",
                correlation_id=correlation_id,
                action="list_user_accounts",
                user_address=user.address if user else None,
            )

            return list(accounts), total

        except ValueError as e:
            self._log_structured(
                level="ERROR",
                message=f"Failed to list accounts: {str(e)}",
                correlation_id=correlation_id,
                action="list_user_accounts",
                error=str(e),
            )
            raise

    async def get_account(
        self,
        db: AsyncSession,
        account_id: int,
        user: User,
    ) -> Account:
        """
        Get account by ID with ownership check.

        Args:
            db: Database session
            account_id: ID of the account
            user: Current user requesting the account

        Returns:
            Account object

        Raises:
            AccountNotFoundError: If account not found
            AccountAccessDeniedError: If user doesn't own account and is not admin
        """
        correlation_id = str(uuid.uuid4())

        try:
            result = await db.execute(select(Account).where(Account.id == account_id))
            account = result.scalar_one_or_none()

            if account is None:
                raise AccountNotFoundError(f"Account with id {account_id} not found")

            # Check ownership or admin status
            if account.user_id != user.id and not user.is_admin:
                raise AccountAccessDeniedError(
                    f"User {user.address} does not have access to account {account_id}"
                )

            self._log_structured(
                level="INFO",
                message=f"Account {account_id} retrieved by user {user.id}",
                correlation_id=correlation_id,
                action="get_account",
                user_address=user.address,
                account_id=account_id,
                account_name=account.name,
            )

            return account

        except (AccountNotFoundError, AccountAccessDeniedError) as e:
            self._log_structured(
                level="ERROR",
                message=f"Failed to get account {account_id}: {str(e)}",
                correlation_id=correlation_id,
                action="get_account",
                user_address=user.address,
                account_id=account_id,
                error=str(e),
            )
            raise

    async def update_account(
        self,
        db: AsyncSession,
        account_id: int,
        user: User,
        data: AccountUpdate,
    ) -> Account:
        """
        Update account with ownership check and status transition validation.

        Args:
            db: Database session
            account_id: ID of the account
            user: Current user requesting the update
            data: Account update data

        Returns:
            Updated Account object

        Raises:
            AccountNotFoundError: If account not found
            AccountAccessDeniedError: If user doesn't own account and is not admin
            AccountValidationError: If validation fails
            StatusTransitionError: If status transition is invalid
        """
        correlation_id = str(uuid.uuid4())

        try:
            # Get account with ownership check
            account = await self.get_account(db, account_id, user)

            # Store old status for logging
            old_status = account.status

            # Update fields
            update_data = data.model_dump(exclude_unset=True)

            # Validate and handle status transitions
            if "status" in update_data:
                new_status = update_data["status"]
                # Apply any credential updates first so validation can check them
                if "api_key" in update_data:
                    account.api_key = update_data["api_key"]
                if "api_secret" in update_data:
                    account.api_secret = update_data["api_secret"]

                # Validate status transition
                self.validate_status_transition(old_status, new_status, account)

                # Log status change with audit trail
                if old_status != new_status:
                    self._log_structured(
                        level="INFO",
                        message=f"Account {account_id} status changed from '{old_status}' to '{new_status}'",
                        correlation_id=correlation_id,
                        action="status_change",
                        user_address=user.address,
                        account_id=account_id,
                        account_name=account.name,
                        old_status=old_status,
                        new_status=new_status,
                    )

            # Validate trading mode changes
            if "is_paper_trading" in update_data:
                new_is_paper = update_data["is_paper_trading"]
                # Check credentials from update data or existing account
                api_key = update_data.get("api_key", account.api_key)
                api_secret = update_data.get("api_secret", account.api_secret)
                balance_usd = update_data.get("balance_usd", account.balance_usd)

                self.validate_trading_mode(
                    is_paper_trading=new_is_paper,
                    api_key=api_key,
                    api_secret=api_secret,
                    balance_usd=balance_usd,
                )

            # Apply all updates
            for field, value in update_data.items():
                setattr(account, field, value)

            db.add(account)
            await db.commit()
            await db.refresh(account)

            self._log_structured(
                level="INFO",
                message=f"Account {account_id} updated by user {user.id}",
                correlation_id=correlation_id,
                action="update_account",
                user_address=user.address,
                account_id=account_id,
                account_name=account.name,
            )

            return account

        except (
            AccountNotFoundError,
            AccountAccessDeniedError,
            AccountValidationError,
            StatusTransitionError,
        ) as e:
            self._log_structured(
                level="ERROR",
                message=f"Failed to update account {account_id}: {str(e)}",
                correlation_id=correlation_id,
                action="update_account",
                user_address=user.address,
                account_id=account_id,
                error=str(e),
            )
            raise

    async def delete_account(
        self,
        db: AsyncSession,
        account_id: int,
        user: User,
        force: bool = False,
    ) -> None:
        """
        Delete account with ownership check and cascade deletion.

        Args:
            db: Database session
            account_id: ID of the account
            user: Current user requesting the deletion
            force: Force delete even with active positions (default: False)

        Raises:
            AccountNotFoundError: If account not found
            AccountAccessDeniedError: If user doesn't own account and is not admin
            ActivePositionsError: If account has active positions and force=False
        """
        correlation_id = str(uuid.uuid4())

        try:
            # Get account with ownership check
            account = await self.get_account(db, account_id, user)

            # Check for active positions if not forcing
            if not force:
                # Import here to avoid circular dependency
                from ..models.position import Position

                result = await db.execute(
                    select(func.count(Position.id)).where(Position.account_id == account_id)
                )
                position_count = result.scalar()

                if position_count and position_count > 0:
                    raise ActivePositionsError(
                        f"Account has {position_count} active position(s). "
                        "Use force=True to delete anyway."
                    )

            # Delete account (cascade will handle related entities)
            await db.delete(account)
            await db.commit()

            self._log_structured(
                level="INFO",
                message=f"Account {account_id} deleted by user {user.id}",
                correlation_id=correlation_id,
                action="delete_account",
                user_address=user.address,
                account_id=account_id,
                account_name=account.name,
            )

        except (AccountNotFoundError, AccountAccessDeniedError, ActivePositionsError) as e:
            self._log_structured(
                level="ERROR",
                message=f"Failed to delete account {account_id}: {str(e)}",
                correlation_id=correlation_id,
                action="delete_account",
                user_address=user.address,
                account_id=account_id,
                error=str(e),
            )
            raise

    async def sync_balance(
        self,
        db: AsyncSession,
        account_id: int,
        user: User,
    ) -> Account:
        """
        Sync account balance from AsterDEX API.

        Args:
            db: Database session
            account_id: ID of the account
            user: Current user requesting the sync

        Returns:
            Updated Account object with synced balance

        Raises:
            AccountNotFoundError: If account not found
            AccountAccessDeniedError: If user doesn't own account and is not admin
            AccountValidationError: If account is in paper trading mode
            BalanceSyncError: If balance sync fails (401 for invalid credentials, 502 for API errors)
        """
        correlation_id = str(uuid.uuid4())

        try:
            # Get account with ownership check
            account = await self.get_account(db, account_id, user)

            # Validate account is in real trading mode
            if account.is_paper_trading:
                raise AccountValidationError(
                    "Balance sync is only allowed for real trading accounts. "
                    "Paper trading accounts use manually set balances."
                )

            # Validate account has API credentials
            if not account.api_key or not account.api_secret:
                raise AccountValidationError(
                    "Account must have API credentials configured for balance sync"
                )

            # Import AsterClient here to avoid circular dependency
            from ..core.config import config
            from ..services.market_data.client import AsterClient

            # Create AsterDEX client
            client = AsterClient(
                api_key=account.api_key,
                api_secret=account.api_secret,
                base_url=config.ASTERDEX_BASE_URL,
            )

            # Fetch balance from AsterDEX
            try:
                balance = await client.fetch_balance()
            except Exception as e:
                error_msg = str(e).lower()
                # Check for authentication errors
                if "401" in error_msg or "unauthorized" in error_msg or "invalid" in error_msg:
                    self._log_structured(
                        level="ERROR",
                        message=f"Invalid API credentials for account {account_id}",
                        correlation_id=correlation_id,
                        action="sync_balance",
                        user_address=user.address,
                        account_id=account_id,
                        error="401 Unauthorized - Invalid API credentials",
                    )
                    raise InvalidApiCredentialsError(
                        "Invalid API credentials. Please update your account credentials."
                    ) from e
                else:
                    # Other API errors
                    self._log_structured(
                        level="ERROR",
                        message=f"AsterDEX API error for account {account_id}: {str(e)}",
                        correlation_id=correlation_id,
                        action="sync_balance",
                        user_address=user.address,
                        account_id=account_id,
                        error=f"502 Bad Gateway - {str(e)}",
                    )
                    raise ExternalApiError(
                        f"Failed to fetch balance from AsterDEX API: {str(e)}"
                    ) from e

            # Update account balance
            old_balance = account.balance_usd
            account.balance_usd = balance

            db.add(account)
            await db.commit()
            await db.refresh(account)

            self._log_structured(
                level="INFO",
                message=f"Balance synced for account {account_id}: {old_balance} -> {balance}",
                correlation_id=correlation_id,
                action="sync_balance",
                user_address=user.address,
                account_id=account_id,
                account_name=account.name,
            )

            return account

        except (
            AccountNotFoundError,
            AccountAccessDeniedError,
            AccountValidationError,
            InvalidApiCredentialsError,
            ExternalApiError,
        ):
            # Re-raise known exceptions
            raise
        except Exception as e:
            self._log_structured(
                level="ERROR",
                message=f"Unexpected error syncing balance for account {account_id}: {str(e)}",
                correlation_id=correlation_id,
                action="sync_balance",
                user_address=user.address,
                account_id=account_id,
                error=str(e),
            )
            raise BalanceSyncError(f"Unexpected error during balance sync: {str(e)}") from e

    def validate_trading_mode(
        self,
        is_paper_trading: bool,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        balance_usd: Optional[float] = None,
    ) -> None:
        """
        Validate trading mode requirements.

        Args:
            is_paper_trading: Whether paper trading mode is enabled
            api_key: API key (required for real trading)
            api_secret: API secret (required for real trading)
            balance_usd: Account balance (for paper trading validation)

        Raises:
            AccountValidationError: If validation fails
        """
        # Real trading requires API credentials
        if not is_paper_trading:
            if not api_key or not api_secret:
                raise AccountValidationError(
                    "Real trading mode requires API credentials (api_key and api_secret)"
                )

        # Paper trading allows arbitrary balance (including None)
        # Balance validation is only for negative values
        if is_paper_trading and balance_usd is not None and balance_usd < 0:
            raise AccountValidationError("Paper trading balance cannot be negative")

    def validate_status_transition(
        self,
        old_status: str,
        new_status: str,
        account: Account,
    ) -> None:
        """
        Validate status transition and enforce requirements.

        Args:
            old_status: Current account status
            new_status: Desired new status
            account: Account being updated

        Raises:
            StatusTransitionError: If transition is invalid
            AccountValidationError: If requirements not met (e.g., missing credentials)
        """
        # Valid statuses
        valid_statuses = ["active", "paused", "stopped"]
        if new_status not in valid_statuses:
            raise AccountValidationError(
                f"Invalid status '{new_status}'. Must be one of: {', '.join(valid_statuses)}"
            )

        # No validation needed if status isn't changing
        if old_status == new_status:
            return

        # Reactivating from stopped requires credential validation for real trading
        if old_status == "stopped" and new_status == "active":
            if not account.is_paper_trading:
                # Real trading accounts must have valid API credentials
                if not account.api_key or not account.api_secret:
                    raise AccountValidationError(
                        "Cannot reactivate stopped account: Real trading mode requires "
                        "valid API credentials (api_key and api_secret)"
                    )

        # When setting to stopped, disable the account
        if new_status == "stopped":
            account.is_enabled = False

        # When setting to active or paused, enable the account
        if new_status in ["active", "paused"]:
            account.is_enabled = True
