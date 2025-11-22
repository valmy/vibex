"""
User management schemas for request/response validation.

Provides Pydantic models for user-related API operations including
listing users, retrieving user details, and managing admin status.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserBase(BaseModel):
    """Base user schema with common fields."""

    model_config = ConfigDict(from_attributes=True)

    address: str = Field(
        ...,
        min_length=42,
        max_length=42,
        description="Ethereum wallet address (42-character hex string starting with 0x)",
        examples=["0x1234567890123456789012345678901234567890"],
    )


class UserRead(UserBase):
    """User read schema with all fields for API responses."""

    id: int = Field(..., description="Unique user identifier")
    is_admin: bool = Field(default=False, description="Whether user has admin privileges")
    created_at: datetime = Field(..., description="Timestamp when user was created")
    updated_at: datetime = Field(..., description="Timestamp when user was last updated")


class UserList(BaseModel):
    """Paginated user list response schema."""

    model_config = ConfigDict(from_attributes=True)

    users: list[UserRead] = Field(..., description="List of users in this page")
    total: int = Field(..., ge=0, description="Total number of users in the system")
    skip: int = Field(..., ge=0, description="Number of users skipped (pagination offset)")
    limit: int = Field(..., gt=0, description="Maximum number of users per page")
