"""
TestEvent model for real-time test execution events.
Represents events during test execution for progress tracking and immediate feedback.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .test_suite import TestSuite

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from .base import BaseModel


class TestEventType(str, Enum):
    """Test event type enumeration."""

    TEST_STARTED = "test_started"
    TEST_ENDED = "test_ended"
    SUITE_STARTED = "suite_started"
    SUITE_ENDED = "suite_ended"
    ERROR = "error"


class TestEvent(BaseModel):
    """Real-time test execution event model."""

    __tablename__ = "test_events"

    suite_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_suites.id", ondelete="CASCADE"),
        nullable=False,
        comment="Foreign key to test suite",
    )

    test_external_id: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="External ID of the test (if applicable)",
    )

    event_type: Mapped[str] = mapped_column(
        SQLEnum(TestEventType, name="test_event_type", native_enum=False),
        nullable=False,
        comment="Type of event",
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="When the event occurred",
    )

    data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Event-specific data payload",
    )

    request_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Request ID from the originating HTTP request",
    )

    user_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="User ID from the authenticated request context",
    )

    # Relationships
    suite: Mapped[TestSuite] = relationship(
        "TestSuite", back_populates="test_events", lazy="select"
    )

    # Constraints and indexes
    __table_args__ = (
        Index("ix_test_events_suite_id", "suite_id"),
        Index("ix_test_events_event_type", "event_type"),
        Index("ix_test_events_timestamp", "timestamp"),
        Index("ix_test_events_test_external_id", "test_external_id"),
        Index("ix_test_events_suite_timestamp", "suite_id", "timestamp"),
        Index("ix_test_events_suite_type", "suite_id", "event_type"),
        Index("ix_test_events_request_id", "request_id"),
        Index("ix_test_events_user_id", "user_id"),
    )

    @validates("test_external_id")
    def validate_test_external_id(self, key: str, test_external_id: str | None) -> str | None:
        """Validate test external ID format."""
        if test_external_id is None:
            return None

        test_external_id = test_external_id.strip()
        if not test_external_id:
            return None

        if len(test_external_id) > 200:
            raise ValueError("Test external ID cannot exceed 200 characters")

        return test_external_id

    @validates("timestamp")
    def validate_timestamp(self, key: str, timestamp: datetime) -> datetime:
        """Validate timestamp is reasonable."""
        if timestamp is None:
            raise ValueError("Timestamp cannot be None")

        return timestamp

    @validates("data")
    def validate_data(self, key: str, data: dict[str, Any] | None) -> dict[str, Any] | None:
        """Validate event data is a proper dictionary."""
        if data is None:
            return None

        if not isinstance(data, dict):
            raise ValueError("Event data must be a dictionary")

        return data

    @validates("request_id")
    def validate_request_id(self, key: str, request_id: str | None) -> str | None:
        """Validate request ID format."""
        if request_id is None:
            return None

        request_id = request_id.strip()
        if not request_id:
            return None

        if len(request_id) > 100:
            raise ValueError("Request ID cannot exceed 100 characters")

        return request_id

    @validates("user_id")
    def validate_user_id(self, key: str, user_id: str | None) -> str | None:
        """Validate user ID format."""
        if user_id is None:
            return None

        user_id = user_id.strip()
        if not user_id:
            return None

        if len(user_id) > 100:
            raise ValueError("User ID cannot exceed 100 characters")

        return user_id

    @property
    def is_test_event(self) -> bool:
        """Check if this is a test-specific event."""
        return self.event_type in (TestEventType.TEST_STARTED, TestEventType.TEST_ENDED)

    @property
    def is_suite_event(self) -> bool:
        """Check if this is a suite-level event."""
        return self.event_type in (TestEventType.SUITE_STARTED, TestEventType.SUITE_ENDED)

    @property
    def is_error_event(self) -> bool:
        """Check if this is an error event."""
        return self.event_type == TestEventType.ERROR

    def get_data_field(self, field_name: str, default: Any = None) -> Any:
        """Get a field from the event data safely."""
        if not self.data:
            return default
        return self.data.get(field_name, default)

    def __str__(self) -> str:
        """String representation."""
        return (
            f"TestEvent(type={self.event_type}, suite={self.suite_id}, timestamp={self.timestamp})"
        )
