"""
API routes for account management with ownership control.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.logging import get_logger
from ...core.security import get_current_user
from ...db import get_db
from ...models import User
from ...schemas import AccountCreate, AccountListResponse, AccountRead, AccountUpdate
from ...services.account_service import (
    AccountAccessDeniedError,
    AccountNotFoundError,
    AccountService,
    AccountValidationError,
    ActivePositionsError,
    DuplicateAccountNameError,
    ExternalApiError,
    InvalidApiCredentialsError,
    StatusTransitionError,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/accounts", tags=["Trading"])
account_service = AccountService()


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
async def create_account(
    account_data: AccountCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new trading account for the authenticated user.

    The account will be automatically associated with the authenticated user.
    For paper trading accounts, you can set an arbitrary initial balance.
    For real trading accounts, API credentials are required.

    **Example Request:**
    ```json
    {
        "name": "My Trading Account",
        "description": "Main trading account for BTC/ETH",
        "is_paper_trading": true,
        "balance_usd": 10000.0,
        "leverage": 2.0,
        "max_position_size_usd": 5000.0,
        "risk_per_trade": 0.02
    }
    ```

    **Returns:**
    - 201: Account created successfully
    - 400: Duplicate account name or validation error
    - 401: Invalid or missing authentication token
    - 422: Invalid request data
    """
    try:
        account = await account_service.create_account(
            db=db,
            user_id=current_user.id,
            data=account_data,
        )
        return AccountRead.from_account(account)
    except DuplicateAccountNameError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except AccountValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error creating account: {e}")
        raise HTTPException(status_code=500, detail="Failed to create account") from e


@router.get("", response_model=AccountListResponse)
async def list_accounts(
    skip: int = Query(0, ge=0, description="Number of accounts to skip"),
    limit: int = Query(100, gt=0, le=1000, description="Maximum number of accounts to return"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all trading accounts owned by the authenticated user.

    Returns only accounts that belong to the authenticated user.
    Admin users will also only see their own accounts (not all accounts in the system).

    **Query Parameters:**
    - skip: Number of accounts to skip (default: 0)
    - limit: Maximum number of accounts to return (default: 100, max: 1000)

    **Returns:**
    - 200: List of accounts with total count
    - 401: Invalid or missing authentication token
    """
    try:
        accounts, total = await account_service.list_user_accounts(
            db=db,
            user_id=current_user.id,
            skip=skip,
            limit=limit,
        )

        return AccountListResponse(
            total=total,
            items=[AccountRead.from_account(account) for account in accounts],
        )
    except Exception as e:
        logger.error(f"Error listing accounts: {e}")
        raise HTTPException(status_code=500, detail="Failed to list accounts") from e


@router.get("/{account_id}", response_model=AccountRead)
async def get_account(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific trading account by ID.

    Only the account owner or admin users can access the account details.
    API credentials are masked in the response for security.

    **Path Parameters:**
    - account_id: The ID of the account to retrieve

    **Returns:**
    - 200: Account details with masked credentials
    - 401: Invalid or missing authentication token
    - 403: User does not own this account and is not an admin
    - 404: Account not found
    """
    try:
        account = await account_service.get_account(
            db=db,
            account_id=account_id,
            user=current_user,
        )
        return AccountRead.from_account(account)
    except AccountNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except AccountAccessDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error getting account: {e}")
        raise HTTPException(status_code=500, detail="Failed to get account") from e


@router.put("/{account_id}", response_model=AccountRead)
async def update_account(
    account_id: int,
    account_data: AccountUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a trading account.

    Only the account owner or admin users can update the account.
    The updated_at timestamp is automatically updated.

    **Path Parameters:**
    - account_id: The ID of the account to update

    **Example Request:**
    ```json
    {
        "status": "paused",
        "leverage": 3.0,
        "max_position_size_usd": 8000.0
    }
    ```

    **Returns:**
    - 200: Account updated successfully
    - 400: Validation error (e.g., invalid status, switching to real trading without credentials)
    - 401: Invalid or missing authentication token
    - 403: User does not own this account and is not an admin
    - 404: Account not found
    """
    try:
        account = await account_service.update_account(
            db=db,
            account_id=account_id,
            user=current_user,
            data=account_data,
        )
        return AccountRead.from_account(account)
    except AccountNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except AccountAccessDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except (AccountValidationError, StatusTransitionError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error updating account: {e}")
        raise HTTPException(status_code=500, detail="Failed to update account") from e


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: int,
    force: bool = Query(
        False,
        description="Force delete even if account has active positions",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a trading account.

    Only the account owner or admin users can delete the account.
    Deletion cascades to all related entities (positions, orders, trades, etc.).

    **Path Parameters:**
    - account_id: The ID of the account to delete

    **Query Parameters:**
    - force: Force delete even if account has active positions (default: false)

    **Returns:**
    - 204: Account deleted successfully (no content)
    - 400: Account has active positions and force=false
    - 401: Invalid or missing authentication token
    - 403: User does not own this account and is not an admin
    - 404: Account not found

    **Warning:** This operation cannot be undone. All related data will be permanently deleted.
    """
    try:
        await account_service.delete_account(
            db=db,
            account_id=account_id,
            user=current_user,
            force=force,
        )
    except AccountNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except AccountAccessDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ActivePositionsError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error deleting account: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete account") from e


@router.post("/{account_id}/sync-balance", response_model=AccountRead)
async def sync_balance(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Sync account balance from AsterDEX API.

    Only available for real trading accounts with valid API credentials.
    Paper trading accounts use manually set balances and cannot be synced.

    **Path Parameters:**
    - account_id: The ID of the account to sync

    **Returns:**
    - 200: Balance synced successfully with updated account details
    - 400: Account is in paper trading mode (sync not allowed)
    - 401: Invalid API credentials (AsterDEX authentication failed)
    - 403: User does not own this account and is not an admin
    - 404: Account not found
    - 502: AsterDEX API error (service unavailable or other API issues)

    **Example Response:**
    ```json
    {
        "id": 1,
        "name": "My Trading Account",
        "balance_usd": 15234.56,
        "is_paper_trading": false,
        ...
    }
    ```
    """
    try:
        account = await account_service.sync_balance(
            db=db,
            account_id=account_id,
            user=current_user,
        )
        return AccountRead.from_account(account)
    except AccountNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except AccountAccessDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except AccountValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except InvalidApiCredentialsError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except ExternalApiError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error syncing balance: {e}")
        raise HTTPException(status_code=500, detail="Failed to sync balance") from e
