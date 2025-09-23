"""
TestSuite model for grouping test results from a single execution run.
Represents a collection of tests executed together with summary statistics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .playwright_test_result import PlaywrightTestResult
    from .test_event import TestEvent

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from .base import BaseModel


class SuiteStatus(str, Enum):
    """Test suite execution status enumeration."""

    CREATED = "created"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"

    @classmethod
    def normalize(cls, status: str) -> SuiteStatus:
        """Normalize status input to match database enum values."""
        # Handle direct matches first
        for enum_value in cls:
            if enum_value.value == status:
                return enum_value

        # Handle case-insensitive matches
        status_lower = status.lower()
        if status_lower == "created":
            return cls.CREATED
        elif status_lower == "running":
            return cls.RUNNING
        elif status_lower == "passed":
            return cls.PASSED
        elif status_lower == "failed":
            return cls.FAILED
        elif status_lower == "cancelled":
            return cls.CANCELLED
        elif status_lower == "interrupted":
            return cls.INTERRUPTED
        else:
            raise ValueError(f"Invalid suite status: {status}")


class TestSuite(BaseModel):
    """Test suite grouping multiple test results."""

    __tablename__ = "test_suites"

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Test suite name",
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

    # Framework-specific metadata (e.g., Playwright)
    # name: Playwright, version: 1.20.0, config: {...}
    framework_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Suite-specific framework metadata and configuration",
    )

    # Environment metadata (e.g., OS, arch, Node.js version)
    environment_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Suite-specific environment metadata and configuration",
    )

    # Server metadata (e.g., server: enterprise edition, version: 11.0.0, license: true, ...)
    server_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Suite-specific server metadata and configuration",
    )

    # CI run metadata (e.g., ci: github_actions, workflow: test, run_number: 123, job_id: 123, full_repo: org/repo_name, branch: main, commit_sha: abcdef123456, pr_number: 45, ...)
    ci_run_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Suite-specific CI run metadata and configuration",
    )

    # Playwright-specific test files metadata
    playwright_test_files: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Suite-specific Playwright test files",
    )

    start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Alternative start time for Playwright compatibility",
    )

    end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Alternative end time for Playwright compatibility",
    )

    status: Mapped[str | None] = mapped_column(
        SQLEnum(SuiteStatus, name="suite_status", native_enum=False),
        nullable=True,
        comment="Suite execution status",
    )

    # Relationships

    # Framework-specific test results relationships
    playwright_test_results: Mapped[list[PlaywrightTestResult]] = relationship(
        "PlaywrightTestResult", back_populates="suite", cascade="all, delete-orphan", lazy="select"
    )

    test_events: Mapped[list[TestEvent]] = relationship(
        "TestEvent", back_populates="suite", cascade="all, delete-orphan", lazy="select"
    )

    # Constraints and indexes
    __table_args__ = (
        CheckConstraint("total_tests >= 0", name="ck_total_tests_non_negative"),
        CheckConstraint("passed_tests >= 0", name="ck_passed_tests_non_negative"),
        CheckConstraint("failed_tests >= 0", name="ck_failed_tests_non_negative"),
        CheckConstraint("skipped_tests >= 0", name="ck_skipped_tests_non_negative"),
        CheckConstraint("duration_ms >= 0", name="ck_duration_non_negative"),
        CheckConstraint("completed_at >= started_at", name="ck_completion_after_start"),
        Index("ix_test_suites_started_at", "started_at"),
        Index("ix_test_suites_completed_at", "completed_at"),
        Index("ix_test_suites_name", "name"),
        Index("ix_test_suites_status", "status"),
        Index("ix_test_suites_start_time", "start_time"),
        Index("ix_test_suites_end_time", "end_time"),
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

    @validates("start_time", "end_time")
    def validate_playwright_timestamps(
        self, key: str, timestamp: datetime | None
    ) -> datetime | None:
        """Validate Playwright timestamp values."""
        if timestamp is None:
            return None
        return timestamp

    def validate_consistency(self) -> None:
        """Validate internal consistency of test counts and timing."""
        # Check test count consistency
        if self.total_tests != (self.passed_tests + self.failed_tests + self.skipped_tests):
            raise ValueError("Total tests must equal sum of passed, failed, and skipped tests")

        # Check timing consistency
        if (
            self.completed_at is not None
            and self.started_at is not None
            and self.completed_at < self.started_at
        ):
            raise ValueError("Completion time cannot be before start time")

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

    @property
    def is_running(self) -> bool:
        """Check if suite is currently running."""
        return self.status == SuiteStatus.RUNNING

    @property
    def is_completed(self) -> bool:
        """Check if suite has completed (passed, failed, or cancelled)."""
        return self.status in (SuiteStatus.PASSED, SuiteStatus.FAILED, SuiteStatus.CANCELLED)

    @property
    def effective_start_time(self) -> datetime:
        """Get the effective start time, preferring start_time over started_at."""
        return self.start_time if self.start_time is not None else self.started_at

    @property
    def effective_end_time(self) -> datetime:
        """Get the effective end time, preferring end_time over completed_at."""
        return self.end_time if self.end_time is not None else self.completed_at

    def __str__(self) -> str:
        """String representation."""
        return (
            f"TestSuite(name='{self.name}', tests={self.total_tests}, passed={self.passed_tests})"
        )
