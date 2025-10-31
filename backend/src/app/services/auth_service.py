import secrets

from eth_account import Account
from eth_account.messages import encode_defunct
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.account import User
from ..models.challenge import Challenge


async def get_challenge(db: AsyncSession, address: str) -> str:
    """Generate and store a challenge for the given address."""
    challenge_text = secrets.token_hex(32)
    challenge = Challenge(address=address, challenge=challenge_text)
    db.add(challenge)
    await db.commit()
    return challenge_text


async def get_or_create_user(db: AsyncSession, address: str) -> User:
    """Retrieve a user by address, creating one if it doesn't exist."""
    result = await db.execute(select(User).where(User.address == address))
    user = result.scalar_one_or_none()
    if user:
        return user

    count_result = await db.execute(select(func.count()).select_from(User))
    is_admin = (count_result.scalar() or 0) == 0

    user = User(address=address, is_admin=is_admin)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(
    db: AsyncSession, address: str, signature: str, challenge: str
) -> User | None:
    """Verify signature for the challenge and return the user if valid."""
    result = await db.execute(select(Challenge).where(Challenge.challenge == challenge))
    db_challenge = result.scalar_one_or_none()

    if not db_challenge or db_challenge.address.lower() != address.lower():
        return None

    try:
        message = encode_defunct(text=challenge)
        sig = signature if signature.startswith("0x") else f"0x{signature}"
        recovered_address = Account.recover_message(message, signature=sig)
        if recovered_address.lower() == address.lower():
            await db.delete(db_challenge)
            await db.commit()
            return await get_or_create_user(db, address)
    except Exception:
        return None

    return None
