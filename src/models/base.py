"""
Base model classes and common functionality for SQLAlchemy models.
Provides UUID primary keys, timestamps, and validation utilities.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    def to_dict(self) -> dict[str, Any]:
        """Convert model instance to dictionary."""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

    def __repr__(self) -> str:
        """String representation of model."""
        attrs = ", ".join(f"{k}={v!r}" for k, v in self.to_dict().items())
        return f"{self.__class__.__name__}({attrs})"


class TimestampMixin:
    """Mixin for adding created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Record creation timestamp",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Record last update timestamp",
    )


class UUIDMixin:
    """Mixin for adding UUID primary key."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="Primary key UUID",
    )


class BaseModel(Base, UUIDMixin, TimestampMixin):
    """Base model with UUID primary key and timestamps."""

    __abstract__ = True
