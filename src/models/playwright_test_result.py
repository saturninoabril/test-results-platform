"""
PlaywrightTestResult model extending BaseTestResult with Playwright-specific fields.
Represents test execution results specific to the Playwright testing framework.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .test_artifact import TestArtifact
    from .test_suite import TestSuite

from sqlalchemy import CheckConstraint, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from .base_test_result import BaseTestResult


class PlaywrightTestResult(BaseTestResult):
    """Playwright-specific test result model."""

    __tablename__ = "playwright_test_results"

    # Playwright-specific fields
    location: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Test location: file path, line, and column number",
    )

    project_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Playwright project name (e.g., Desktop Chrome)",
    )

    timeout_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Test timeout in milliseconds",
    )

    # Worker information (specific to Playwright parallel execution)
    worker_index: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Playwright worker index for parallel execution",
    )

    # Browser/Environment details (duplicated for performance, normalized via suite)
    browser_name: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Browser used (chromium, firefox, webkit)",
    )

    # Relationships
    suite: Mapped[TestSuite] = relationship(
        "TestSuite", back_populates="playwright_test_results", lazy="select"
    )

    test_artifacts: Mapped[list[TestArtifact]] = relationship(
        "TestArtifact",
        back_populates="playwright_test_result",
        cascade="all, delete-orphan",
        lazy="select",
    )

    # Constraints and indexes (override base class)
    __table_args__: tuple[Any, ...] = (
        # Inherit base constraints
        CheckConstraint("duration_ms >= 0", name="ck_playwright_test_duration_non_negative"),
        CheckConstraint("retry_count >= 0", name="ck_playwright_retry_count_non_negative"),
        CheckConstraint("retry_count <= 10", name="ck_playwright_retry_count_reasonable"),
        # Playwright-specific constraints
        CheckConstraint(
            "timeout_ms IS NULL OR (timeout_ms >= 1000 AND timeout_ms <= 3600000)",
            name="ck_playwright_timeout_ms_reasonable",
        ),
        CheckConstraint(
            "worker_index IS NULL OR worker_index >= 0",
            name="ck_playwright_worker_index_non_negative",
        ),
        # Indexes
        Index("ix_playwright_test_results_suite_id", "suite_id"),
        Index("ix_playwright_test_results_test_name", "test_name"),
        Index("ix_playwright_test_results_status", "status"),
        Index("ix_playwright_test_results_suite_status", "suite_id", "status"),
        Index("ix_playwright_test_results_external_id", "external_id"),
        Index("ix_playwright_test_results_project_name", "project_name"),
        Index("ix_playwright_test_results_browser_name", "browser_name"),
        Index("ix_playwright_test_results_worker_index", "worker_index"),
        Index("ix_playwright_test_results_started_at", "started_at"),
    )

    @validates("location")
    def validate_location(self, key: str, location: dict[str, Any] | None) -> dict[str, Any] | None:
        """Validate location format for Playwright test files."""
        if location is None:
            return None

        if not isinstance(location, dict):
            raise ValueError("Location must be a dictionary")

        # Validate required fields if location is provided
        if location:
            if "file" not in location:
                raise ValueError("Location must include 'file' field")

            file_path = location.get("file")
            if not isinstance(file_path, str) or not file_path.strip():
                raise ValueError("Location file must be a non-empty string")

            # Validate line and column if provided
            line = location.get("line")
            if line is not None and (not isinstance(line, int) or line < 1):
                raise ValueError("Location line must be a positive integer")

            column = location.get("column")
            if column is not None and (not isinstance(column, int) or column < 0):
                raise ValueError("Location column must be a non-negative integer")

        return location

    @validates("project_name")
    def validate_project_name(self, key: str, project_name: str | None) -> str | None:
        """Validate Playwright project name."""
        if project_name is None:
            return None

        project_name = project_name.strip()
        if not project_name:
            return None

        if len(project_name) > 100:
            raise ValueError("Project name cannot exceed 100 characters")

        return project_name

    @validates("timeout_ms")
    def validate_timeout_ms(self, key: str, timeout_ms: int | None) -> int | None:
        """Validate test timeout in milliseconds."""
        if timeout_ms is None:
            return None

        if timeout_ms < 1000:
            raise ValueError("Timeout must be at least 1000ms (1 second)")

        if timeout_ms > 3600000:
            raise ValueError("Timeout cannot exceed 3600000ms (1 hour)")

        return timeout_ms

    @validates("worker_index")
    def validate_worker_index(self, key: str, worker_index: int | None) -> int | None:
        """Validate Playwright worker index."""
        if worker_index is None:
            return None

        if worker_index < 0:
            raise ValueError("Worker index must be non-negative")

        return worker_index

    @validates("browser_name")
    def validate_browser_name(self, key: str, browser_name: str | None) -> str | None:
        """Validate browser name."""
        if browser_name is None:
            return None

        browser_name = browser_name.strip().lower()
        if not browser_name:
            return None

        valid_browsers = ["chromium", "firefox", "webkit", "chrome", "edge", "safari"]
        if browser_name not in valid_browsers:
            raise ValueError(f"Browser name must be one of: {valid_browsers}")

        return browser_name

    @property
    def file_path(self) -> str | None:
        """Get test file path from location."""
        if not self.location or "file" not in self.location:
            return None
        file_value = self.location["file"]
        return str(file_value) if file_value is not None else None

    @property
    def line_number(self) -> int | None:
        """Get test line number from location."""
        if not self.location or "line" not in self.location:
            return None
        line_value = self.location["line"]
        return int(line_value) if line_value is not None else None

    @property
    def timeout_seconds(self) -> float | None:
        """Get timeout in seconds."""
        if self.timeout_ms is None:
            return None
        return self.timeout_ms / 1000.0

    def __str__(self) -> str:
        """String representation."""
        project_info = f" [{self.project_name}]" if self.project_name else ""
        return f"PlaywrightTestResult(name='{self.test_name}', status={self.status}{project_info})"
