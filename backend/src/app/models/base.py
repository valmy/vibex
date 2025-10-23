"""
Base model for all SQLAlchemy ORM models.

Provides common functionality like timestamps and ID generation.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, func
from sqlalchemy.orm import declarative_base

# Create declarative base for all models
Base = declarative_base()


class BaseModel(Base):
    """Base model with common fields for all entities."""

    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        """String representation of the model."""
        return f"<{self.__class__.__name__}(id={self.id})>"

