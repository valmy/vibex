from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.security import create_access_token
from ...schemas.auth import Challenge, Token
from ...services.auth_service import authenticate_user, get_challenge
from ...db.session import get_db
from ...core.security import get_current_user

router = APIRouter()


@router.post("/challenge", response_model=Challenge)
async def request_challenge(address: str, db: AsyncSession = Depends(get_db)):
    """
    Requests a challenge message for a user to sign.
    """
    challenge = await get_challenge(db, address)
    return {"challenge": challenge}


@router.post("/login", response_model=Token)
async def login(challenge: str, signature: str, address: str, db: AsyncSession = Depends(get_db)):
    """
    Authenticates a user and returns a JWT token.
    """
    user = await authenticate_user(db, address, signature, challenge)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid signature")

    access_token = create_access_token(data={"sub": user.address})
    return {"access_token": access_token, "token_type": "bearer"}


from ...schemas.account import UserRead


@router.get("/me", response_model=UserRead)
def read_users_me(current_user: dict = Depends(get_current_user)):
    """
    Returns the current authenticated user.
    """
    return current_user
