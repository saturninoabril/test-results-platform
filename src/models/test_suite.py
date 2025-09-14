"""
TestSuite model for grouping test results from a single execution run.
Represents a collection of tests executed together with summary statistics.
"""

from datetime import datetime
from typing import Dict, Any, Optional
import uuid

from sqlalchemy import String, Integer, DateTime, ForeignKey, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from .base import BaseModel


class TestSuite(BaseModel):
    """Test suite grouping multiple test results."""

    __tablename__ = "test_suites"

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Test suite name",
    )

    framework_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_frameworks.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Foreign key to test framework",
    )

    environment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_environments.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Foreign key to test environment",
    )

    total_tests: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total number of tests in suite",
    )

    passed_tests: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of passed tests",
    )

    failed_tests: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of failed tests",
    )

    skipped_tests: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of skipped tests",
    )

    duration_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total execution time in milliseconds",
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Suite execution start time",
    )

    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Suite execution completion time",
    )

    config_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Suite-specific metadata and configuration",
    )

    # Relationships
    framework: Mapped["TestFramework"] = relationship(
        "TestFramework",
        lazy="select"
    )

    environment: Mapped["TestEnvironment"] = relationship(
        "TestEnvironment",
        lazy="select"
    )

    test_results: Mapped[list["TestResult"]] = relationship(
        "TestResult",
        back_populates="suite",
        cascade="all, delete-orphan",
        lazy="select"
    )

    # Constraints and indexes
    __table_args__ = (
        CheckConstraint("total_tests >= 0", name="ck_total_tests_non_negative"),
        CheckConstraint("passed_tests >= 0", name="ck_passed_tests_non_negative"),
        CheckConstraint("failed_tests >= 0", name="ck_failed_tests_non_negative"),
        CheckConstraint("skipped_tests >= 0", name="ck_skipped_tests_non_negative"),
        CheckConstraint("duration_ms >= 0", name="ck_duration_non_negative"),
        CheckConstraint("completed_at >= started_at", name="ck_completion_after_start"),
        CheckConstraint(
            "total_tests = passed_tests + failed_tests + skipped_tests",
            name="ck_test_counts_consistent"
        ),
        Index("ix_test_suites_framework_id", "framework_id"),
        Index("ix_test_suites_environment_id", "environment_id"),
        Index("ix_test_suites_started_at", "started_at"),
        Index("ix_test_suites_completed_at", "completed_at"),
        Index("ix_test_suites_name", "name"),
        Index("ix_test_suites_framework_started", "framework_id", "started_at"),
        Index("ix_test_suites_environment_started", "environment_id", "started_at"),
    )

    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        """Validate suite name."""
        if not name or not name.strip():
            raise ValueError("Suite name cannot be empty")

        if len(name.strip()) > 200:
            raise ValueError("Suite name cannot exceed 200 characters")

        return name.strip()

    @validates("total_tests", "passed_tests", "failed_tests", "skipped_tests")
    def validate_test_counts(self, key: str, value: int) -> int:
        """Validate test count values."""
        if value < 0:
            raise ValueError(f"{key} cannot be negative")
        return value

    @validates("duration_ms")
    def validate_duration(self, key: str, duration: int) -> int:
        """Validate duration is non-negative."""
        if duration < 0:
            raise ValueError("Duration cannot be negative")
        return duration

    @validates("started_at", "completed_at")
    def validate_timestamps(self, key: str, timestamp: datetime) -> datetime:
        """Validate timestamp values."""
        if timestamp is None:
            raise ValueError(f"{key} cannot be None")
        return timestamp

    @validates("config_metadata")
    def validate_config_metadata(self, key: str, config_metadata: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Validate config_metadata is a proper dictionary."""
        if config_metadata is None:
            return None

        if not isinstance(config_metadata, dict):
            raise ValueError("Config metadata must be a dictionary")

        return config_metadata

    def validate_consistency(self) -> None:
        """Validate internal consistency of test counts and timing."""
        # Check test count consistency
        if self.total_tests != (self.passed_tests + self.failed_tests + self.skipped_tests):
            raise ValueError("Total tests must equal sum of passed, failed, and skipped tests")

        # Check timing consistency
        if self.completed_at <= self.started_at:
            raise ValueError("Completion time must be after start time")

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_tests == 0:
            return 0.0
        return (self.passed_tests / self.total_tests) * 100.0

    @property
    def duration_seconds(self) -> float:
        """Get duration in seconds."""
        return self.duration_ms / 1000.0

    def __str__(self) -> str:
        """String representation."""
        return f"TestSuite(name='{self.name}', tests={self.total_tests}, passed={self.passed_tests})"