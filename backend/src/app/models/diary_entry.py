"""
Diary entry model for trading journal.

Represents a journal entry for trading analysis and reflection.
"""

from sqlalchemy import Column, String, Text, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship
from .base import BaseModel


class DiaryEntry(BaseModel):
    """Trading diary entry model."""

    __tablename__ = "diary_entries"
    __table_args__ = (
        Index("idx_diary_account_id", "account_id"),
        Index("idx_diary_entry_type", "entry_type"),
        {"schema": "trading"}
    )

    # Foreign key
    account_id = Column(Integer, ForeignKey("trading.accounts.id"), nullable=False, index=True)

    # Entry details
    entry_type = Column(String(50), nullable=False)  # trade_analysis, market_analysis, reflection, note
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)

    # Entry metadata
    tags = Column(String(255), nullable=True)  # comma-separated tags
    sentiment = Column(String(20), nullable=True)  # bullish, bearish, neutral
    confidence = Column(String(20), nullable=True)  # high, medium, low

    # Relationships
    account = relationship("Account", back_populates="diary_entries")

    def __repr__(self):
        """String representation."""
        return f"<DiaryEntry(id={self.id}, title={self.title}, type={self.entry_type})>"

