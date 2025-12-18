from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import BaseModel


class Challenge(BaseModel):
    __tablename__ = "challenges"
    __table_args__ = ({"schema": "trading", "extend_existing": True},)

    address: Mapped[str] = mapped_column(String(42), nullable=False, index=True)
    challenge: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
