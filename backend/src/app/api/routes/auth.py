from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.security import create_access_token, get_current_user
from ...db.session import get_db
from ...schemas.account import UserRead
from ...schemas.auth import Challenge, Token
from ...services.auth_service import authenticate_user, get_challenge

router = APIRouter()


@router.post("/challenge", response_model=Challenge)
async def request_challenge(address: str, db: Annotated[AsyncSession, Depends(get_db)]) -> Challenge:
    """
    Requests a challenge message for a user to sign.
    """
    challenge = await get_challenge(db, address)
    return Challenge(challenge=challenge)


@router.post("/login", response_model=Token)
async def login(
    challenge: str, signature: str, address: str, db: Annotated[AsyncSession, Depends(get_db)]
) -> Token:
    """
    Authenticates a user and returns a JWT token.
    """
    user = await authenticate_user(db, address, signature, challenge)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid signature")

    access_token = create_access_token(data={"sub": user.address})
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserRead)
def read_users_me(current_user: Annotated[UserRead, Depends(get_current_user)]) -> UserRead:
    """
    Returns the current authenticated user.
    """
    return current_user
