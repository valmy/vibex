"""
Diary entry schemas for request/response validation.
"""

from typing import Optional
from pydantic import Field
from .base import BaseSchema, BaseCreateSchema, BaseUpdateSchema


class DiaryEntryCreate(BaseCreateSchema):
    """Schema for creating a diary entry."""

    account_id: int = Field(..., description="Account ID")
    entry_type: str = Field(..., description="Entry type: trade_analysis, market_analysis, reflection, note")
    title: str = Field(..., min_length=1, max_length=255, description="Entry title")
    content: str = Field(..., min_length=1, description="Entry content")
    tags: Optional[str] = Field(None, description="Comma-separated tags")
    sentiment: Optional[str] = Field(None, description="Sentiment: bullish, bearish, neutral")
    confidence: Optional[str] = Field(None, description="Confidence: high, medium, low")


class DiaryEntryUpdate(BaseUpdateSchema):
    """Schema for updating a diary entry."""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = Field(None, min_length=1)
    tags: Optional[str] = None
    sentiment: Optional[str] = None
    confidence: Optional[str] = None


class DiaryEntryRead(BaseSchema):
    """Schema for reading a diary entry."""

    account_id: int
    entry_type: str
    title: str
    content: str
    tags: Optional[str] = None
    sentiment: Optional[str] = None
    confidence: Optional[str] = None


class DiaryEntryListResponse(BaseSchema):
    """Schema for diary entry list response."""

    total: int
    items: list[DiaryEntryRead]

