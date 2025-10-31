"""
API routes for account management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.exceptions import ResourceNotFoundError, ValidationError, to_http_exception
from ...core.logging import get_logger
from ...core.security import get_current_user
from ...db import get_db
from ...models import Account
from ...schemas import AccountCreate, AccountListResponse, AccountRead, AccountUpdate

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/accounts", tags=["Trading"])


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
async def create_account(
    account_data: AccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a new trading account."""
    try:
        # Check if account name already exists
        result = await db.execute(select(Account).where(Account.name == account_data.name))
        if result.scalar_one_or_none():
            raise ValidationError(f"Account with name '{account_data.name}' already exists")

        # Create new account
        account = Account(**account_data.model_dump())
        db.add(account)
        await db.commit()
        await db.refresh(account)

        logger.info(f"Created account: {account.name}")
        return account
    except ValidationError as e:
        raise to_http_exception(e)
    except Exception as e:
        logger.error(f"Error creating account: {e}")
        raise HTTPException(status_code=500, detail="Failed to create account")


@router.get("", response_model=AccountListResponse)
async def list_accounts(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List all trading accounts."""
    try:
        # Get total count
        count_result = await db.execute(select(func.count(Account.id)))
        total = count_result.scalar()

        # Get accounts
        result = await db.execute(select(Account).offset(skip).limit(limit))
        accounts = result.scalars().all()

        return AccountListResponse(total=total, items=accounts)
    except Exception as e:
        logger.error(f"Error listing accounts: {e}")
        raise HTTPException(status_code=500, detail="Failed to list accounts")


@router.get("/{account_id}", response_model=AccountRead)
async def get_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific trading account."""
    try:
        result = await db.execute(select(Account).where(Account.id == account_id))
        account = result.scalar_one_or_none()

        if not account:
            raise ResourceNotFoundError("Account", account_id)

        return account
    except ResourceNotFoundError as e:
        raise to_http_exception(e)
    except Exception as e:
        logger.error(f"Error getting account: {e}")
        raise HTTPException(status_code=500, detail="Failed to get account")


@router.put("/{account_id}", response_model=AccountRead)
async def update_account(
    account_id: int,
    account_data: AccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update a trading account."""
    try:
        result = await db.execute(select(Account).where(Account.id == account_id))
        account = result.scalar_one_or_none()

        if not account:
            raise ResourceNotFoundError("Account", account_id)

        # Update fields
        update_data = account_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(account, field, value)

        await db.commit()
        await db.refresh(account)

        logger.info(f"Updated account: {account.name}")
        return account
    except ResourceNotFoundError as e:
        raise to_http_exception(e)
    except Exception as e:
        logger.error(f"Error updating account: {e}")
        raise HTTPException(status_code=500, detail="Failed to update account")


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Delete a trading account."""
    try:
        result = await db.execute(select(Account).where(Account.id == account_id))
        account = result.scalar_one_or_none()

        if not account:
            raise ResourceNotFoundError("Account", account_id)

        await db.delete(account)
        await db.commit()

        logger.info(f"Deleted account: {account.name}")
    except ResourceNotFoundError as e:
        raise to_http_exception(e)
    except Exception as e:
        logger.error(f"Error deleting account: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete account")
