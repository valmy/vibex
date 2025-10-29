import secrets
from sqlalchemy.orm import Session
from web3 import Web3
from eth_account.messages import encode_defunct

from ..models.account import User
from ..models.challenge import Challenge
from ..schemas.account import UserCreate


def get_challenge(db: Session, address: str) -> str:
    """
    Generates a new challenge for a user to sign and stores it in the database.
    """
    challenge_text = secrets.token_hex(32)
    challenge = Challenge(address=address, challenge=challenge_text)
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return challenge_text


def get_or_create_user(db: Session, address: str) -> User:
    """
    Retrieves a user by address, creating a new one if it doesn't exist.
    """
    user = db.query(User).filter(User.address == address).first()
    if user:
        return user

    # For now, the first user to sign in is an admin.
    # In a real application, you would have a more secure way to assign admins.
    is_admin = db.query(User).count() == 0

    user = User(address=address, is_admin=is_admin)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, address: str, signature: str, challenge: str) -> User:
    """
    Authenticates a user by verifying their signature and returns the user.
    """
    db_challenge = db.query(Challenge).filter(Challenge.challenge == challenge).first()

    if not db_challenge or db_challenge.address.lower() != address.lower():
        return None

    try:
        message = encode_defunct(text=challenge)
        recovered_address = Web3.eth.account.recover_message(message, signature=signature)
        if recovered_address.lower() == address.lower():
            db.delete(db_challenge)
            db.commit()
            return get_or_create_user(db, address)
    except Exception:
        return None

    return None
