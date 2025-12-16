from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional, Any, Dict

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..models.account import User
from .config import config

http_bearer = HTTPBearer(auto_error=True, scheme_name="BearerAuth")

credentials_exception = HTTPException(
    status_code=401,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


class TokenData(BaseModel):
    username: Optional[str] = None


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode: Dict[str, Any] = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)
    return encoded_jwt


def verify_token(token: str, credentials_exception: HTTPException) -> TokenData:
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise credentials_exception
        return TokenData(username=username)
    except JWTError as e:
        raise credentials_exception from e


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(http_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    token = credentials.credentials
    token_data = verify_token(token, credentials_exception)
    result = await db.execute(
        select(User).where(func.lower(User.address) == func.lower(token_data.username))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


async def require_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """
    Dependency that requires the current user to be an admin.

    Raises HTTPException(403) if user is not admin.

    Args:
        current_user: The currently authenticated user.

    Returns:
        The authenticated user if they have admin privileges.

    Raises:
        HTTPException: 403 Forbidden if user is not an admin.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required",
        )
    return current_user


# Alias for backward compatibility
async def get_current_admin_user(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """
    Deprecated: Use require_admin instead.

    Dependency that requires the current user to be an admin.
    This is an alias for require_admin maintained for backward compatibility.
    """
    return await require_admin(current_user)


async def require_account_owner(
    account_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Dependency that requires the current user to own the account.

    Args:
        account_id: The account ID to check ownership for
        current_user: The currently authenticated user
        db: Database session

    Returns:
        The Account object if user owns it

    Raises:
        HTTPException: 404 if account not found, 403 if user doesn't own the account
    """
    from ..models.account import Account

    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()

    if account is None:
        raise HTTPException(
            status_code=404,
            detail=f"Account with id {account_id} not found",
        )

    if account.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this account",
        )

    return account


async def require_admin_or_owner(
    account_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Dependency that requires the current user to be admin or own the account.

    Args:
        account_id: The account ID to check ownership for
        current_user: The currently authenticated user
        db: Database session

    Returns:
        The Account object if user is admin or owns it

    Raises:
        HTTPException: 404 if account not found, 403 if neither admin nor owner
    """
    from ..models.account import Account

    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()

    if account is None:
        raise HTTPException(
            status_code=404,
            detail=f"Account with id {account_id} not found",
        )

    if account.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this account",
        )

    return account
