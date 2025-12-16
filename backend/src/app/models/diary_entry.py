"""
Diary entry model for trading journal.

Represents a journal entry for trading analysis and reflection.
"""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .account import Account


class DiaryEntry(BaseModel):
    """Trading diary entry model."""

    __tablename__ = "diary_entries"
    __table_args__ = (
        Index("idx_diary_account_id", "account_id"),
        Index("idx_diary_entry_type", "entry_type"),
        {"schema": "trading"},
    )

    # Foreign key
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("trading.accounts.id"), nullable=False, index=True)

    # Entry details
    entry_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # trade_analysis, market_analysis, reflection, note
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Entry metadata
    tags: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # comma-separated tags
    sentiment: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # bullish, bearish, neutral
    confidence: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # high, medium, low

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="diary_entries")

    def __repr__(self) -> str:
        """String representation."""
        return f"<DiaryEntry(id={self.id}, title={self.title}, type={self.entry_type})>"
