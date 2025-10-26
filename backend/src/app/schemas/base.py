"""
Base schemas for all Pydantic models.

Provides common fields and configuration.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base schema with common fields."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BaseCreateSchema(BaseModel):
    """Base schema for create operations."""

    model_config = ConfigDict(from_attributes=True)


class BaseUpdateSchema(BaseModel):
    """Base schema for update operations."""

    model_config = ConfigDict(from_attributes=True)
