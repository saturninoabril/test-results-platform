"""
Base TestResult model for common test execution fields.
Extended by framework-specific models like PlaywrightTestResult.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, validates

from .base import BaseModel


class TestStatus(str, Enum):
    """Test execution status enumeration."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING = "pending"
    FLAKY = "flaky"
    RUNNING = "running"


class BaseTestResult(BaseModel):
    """Base test result model with common fields for all frameworks."""

    __abstract__ = True

    suite_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_suites.id", ondelete="CASCADE"),
        nullable=False,
        comment="Foreign key to test suite",
    )

    test_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Test name or identifier",
    )

    full_title: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        comment="Complete test path with suite hierarchy",
    )

    status: Mapped[str] = mapped_column(
        SQLEnum(TestStatus, name="test_status", native_enum=False),
        nullable=False,
        comment="Test execution status",
    )

    duration_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Test execution time in milliseconds",
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Test execution start time",
    )

    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Test execution completion time",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if test failed",
    )

    stack_trace: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Stack trace for failed tests",
    )

    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of retry attempts",
    )

    tags: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Test tags and annotations",
    )

    external_id: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Framework-specific test identifier",
    )

    config_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Test-specific metadata and configuration",
    )

    # Common constraints
    __table_args__ = (
        CheckConstraint("duration_ms >= 0", name="ck_test_duration_non_negative"),
        CheckConstraint("retry_count >= 0", name="ck_retry_count_non_negative"),
        CheckConstraint("retry_count <= 10", name="ck_retry_count_reasonable"),
    )

    @validates("test_name")
    def validate_test_name(self, key: str, test_name: str) -> str:
        """Validate test name."""
        if not test_name or not test_name.strip():
            raise ValueError("Test name cannot be empty")

        if len(test_name.strip()) > 500:
            raise ValueError("Test name cannot exceed 500 characters")

        return test_name.strip()

    @validates("full_title")
    def validate_full_title(self, key: str, full_title: str) -> str:
        """Validate full title."""
        if not full_title or not full_title.strip():
            raise ValueError("Full title cannot be empty")

        if len(full_title.strip()) > 1000:
            raise ValueError("Full title cannot exceed 1000 characters")

        return full_title.strip()

    @validates("duration_ms")
    def validate_duration(self, key: str, duration: int) -> int:
        """Validate duration is non-negative."""
        if duration < 0:
            raise ValueError("Duration cannot be negative")
        return duration

    @validates("retry_count")
    def validate_retry_count(self, key: str, retry_count: int) -> int:
        """Validate retry count is reasonable."""
        if retry_count < 0:
            raise ValueError("Retry count cannot be negative")
        if retry_count > 10:
            raise ValueError("Retry count cannot exceed 10")
        return retry_count

    @validates("tags")
    def validate_tags(self, key: str, tags: list[str] | None) -> list[str] | None:
        """Validate tags array."""
        if tags is None:
            return None

        if not isinstance(tags, list):
            raise ValueError("Tags must be a list")

        if len(tags) > 20:
            raise ValueError("Cannot have more than 20 tags")

        # Validate each tag
        validated_tags = []
        for tag in tags:
            if not isinstance(tag, str):
                raise ValueError("All tags must be strings")

            tag = tag.strip()
            if not tag:
                continue  # Skip empty tags

            if len(tag) > 100:
                raise ValueError("Tag cannot exceed 100 characters")

            validated_tags.append(tag.lower())

        return validated_tags if validated_tags else None

    @validates("external_id")
    def validate_external_id(self, key: str, external_id: str | None) -> str | None:
        """Validate external ID format."""
        if external_id is None:
            return None

        external_id = external_id.strip()
        if not external_id:
            return None

        if len(external_id) > 200:
            raise ValueError("External ID cannot exceed 200 characters")

        return external_id

    @validates("config_metadata")
    def validate_config_metadata(
        self, key: str, config_metadata: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        """Validate config_metadata is a proper dictionary."""
        if config_metadata is None:
            return None

        if not isinstance(config_metadata, dict):
            raise ValueError("Config metadata must be a dictionary")

        return config_metadata

    @property
    def duration_seconds(self) -> float:
        """Get duration in seconds."""
        return self.duration_ms / 1000.0

    @property
    def is_failed(self) -> bool:
        """Check if test failed."""
        return self.status == TestStatus.FAILED

    @property
    def is_passed(self) -> bool:
        """Check if test passed."""
        return self.status == TestStatus.PASSED

    @property
    def is_skipped(self) -> bool:
        """Check if test was skipped."""
        return self.status == TestStatus.SKIPPED

    def has_tag(self, tag: str) -> bool:
        """Check if test has a specific tag."""
        if not self.tags:
            return False
        return tag.lower() in [t.lower() for t in self.tags]

    def __str__(self) -> str:
        """String representation."""
        return f"{self.__class__.__name__}(name='{self.test_name}', status={self.status})"
