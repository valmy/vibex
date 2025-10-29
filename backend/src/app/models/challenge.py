from sqlalchemy import Column, String, DateTime
from sqlalchemy.sql import func
from .base import BaseModel


class Challenge(BaseModel):
    __tablename__ = "challenges"
    __table_args__ = ({"schema": "trading", "extend_existing": True},)

    address = Column(String(42), nullable=False, index=True)
    challenge = Column(String(64), nullable=False, unique=True)
    created_at = Column(DateTime, server_default=func.now())
