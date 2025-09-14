"""
TestEnvironment model for capturing test execution context.
Represents browser, OS, and environment configuration for test execution.
"""

from typing import Dict, Any, Optional, List

from sqlalchemy import String, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, validates

from .base import BaseModel


class TestEnvironment(BaseModel):
    """Test execution environment model."""

    __tablename__ = "test_environments"

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Environment name (e.g., 'staging', 'production')",
    )

    browser: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Browser used for testing (e.g., 'chromium', 'firefox')",
    )

    os: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Operating system (e.g., 'ubuntu-22.04', 'macos-13')",
    )

    config_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Environment-specific configuration and details",
    )

    # Indexes
    __table_args__ = (
        Index("ix_test_environments_name", "name"),
        Index("ix_test_environments_browser", "browser"),
        Index("ix_test_environments_os", "os"),
        Index("ix_test_environments_name_browser_os", "name", "browser", "os"),
    )

    # Predefined values for validation
    ALLOWED_BROWSERS = [
        "chromium", "chrome", "firefox", "webkit", "safari", "edge", "electron"
    ]

    ALLOWED_OS_PATTERNS = [
        "ubuntu", "macos", "windows", "linux", "darwin", "win32"
    ]

    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        """Validate environment name."""
        if not name or not name.strip():
            raise ValueError("Environment name cannot be empty")

        if len(name.strip()) > 100:
            raise ValueError("Environment name cannot exceed 100 characters")

        return name.strip()

    @validates("browser")
    def validate_browser(self, key: str, browser: Optional[str]) -> Optional[str]:
        """Validate browser type."""
        if browser is None:
            return None

        browser = browser.strip().lower()
        if not browser:
            return None

        # Check if browser is in allowed list or contains allowed pattern
        if not any(allowed in browser for allowed in self.ALLOWED_BROWSERS):
            raise ValueError(f"Browser '{browser}' not recognized. Allowed patterns: {self.ALLOWED_BROWSERS}")

        return browser

    @validates("os")
    def validate_os(self, key: str, os_value: Optional[str]) -> Optional[str]:
        """Validate operating system."""
        if os_value is None:
            return None

        os_value = os_value.strip().lower()
        if not os_value:
            return None

        # Check if OS contains allowed pattern
        if not any(allowed in os_value for allowed in self.ALLOWED_OS_PATTERNS):
            raise ValueError(f"OS '{os_value}' not recognized. Allowed patterns: {self.ALLOWED_OS_PATTERNS}")

        return os_value

    @validates("config_metadata")
    def validate_config_metadata(self, key: str, config_metadata: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Validate config_metadata is a proper dictionary."""
        if config_metadata is None:
            return None

        if not isinstance(config_metadata, dict):
            raise ValueError("Config metadata must be a dictionary")

        return config_metadata

    def __str__(self) -> str:
        """String representation."""
        parts = [self.name]
        if self.browser:
            parts.append(f"browser={self.browser}")
        if self.os:
            parts.append(f"os={self.os}")
        return f"TestEnvironment({', '.join(parts)})"