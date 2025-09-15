"""
TestFramework model for managing testing framework metadata.
Represents testing tools like Playwright, Cypress with versions and configuration.
"""

from typing import Any

from sqlalchemy import Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, validates

from .base import BaseModel


class TestFramework(BaseModel):
    """Test framework model (Playwright, Cypress, etc.)."""

    __tablename__ = "test_frameworks"

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Framework name (e.g., 'playwright', 'cypress')",
    )

    version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Framework version (e.g., '1.55.0', '7.2.0')",
    )

    config_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Framework-specific configuration and metadata",
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_framework_name_version"),
        Index("ix_test_frameworks_name", "name"),
        Index("ix_test_frameworks_version", "version"),
    )

    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        """Validate framework name format."""
        if not name:
            raise ValueError("Framework name cannot be empty")

        # Lowercase, alphanumeric with hyphens only
        if not name.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Framework name must be alphanumeric with hyphens/underscores only")

        return name.lower().strip()

    @validates("version")
    def validate_version(self, key: str, version: str) -> str:
        """Validate semantic version format."""
        if not version:
            raise ValueError("Framework version cannot be empty")

        # Basic semantic version validation (x.y.z format)
        parts = version.split(".")
        if len(parts) < 2 or len(parts) > 4:
            raise ValueError("Version must follow semantic versioning (e.g., '1.2.3')")

        try:
            for i, part in enumerate(parts[:3]):  # Major, minor, patch should be numeric
                # Handle pre-release tags (e.g., "1.0.0-beta")
                if i == 2 and "-" in part:  # Patch version with pre-release tag
                    part = part.split("-")[0]  # Extract numeric part only
                int(part)
        except ValueError:
            raise ValueError("Version parts must be numeric") from None

        return version.strip()

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

    def __str__(self) -> str:
        """String representation."""
        return f"{self.name}@{self.version}"
