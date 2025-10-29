from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str


class Challenge(BaseModel):
    challenge: str


class ChallengeCreate(BaseModel):
    address: str
    challenge: str


class ChallengeRead(ChallengeCreate):
    id: str
    created_at: str
