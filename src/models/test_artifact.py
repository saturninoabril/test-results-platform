"""
TestArtifact model for managing files associated with test execution.
Represents screenshots, videos, reports, and other test artifacts stored in S3.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional
import uuid

from sqlalchemy import (
    String, Integer, DateTime, ForeignKey, Index, CheckConstraint,
    Enum as SQLEnum, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from .base import BaseModel


class ArtifactType(str, Enum):
    """Test artifact type enumeration."""
    SCREENSHOT = "screenshot"
    VIDEO = "video"
    REPORT = "report"
    LOG = "log"
    TRACE = "trace"
    OTHER = "other"


class TestArtifact(BaseModel):
    """Test artifact file metadata and storage references."""

    __tablename__ = "test_artifacts"

    # Foreign key relationships (one of these must be set)
    result_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_results.id", ondelete="CASCADE"),
        nullable=True,
        comment="Foreign key to test result (for result-level artifacts)",
    )

    suite_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_suites.id", ondelete="CASCADE"),
        nullable=True,
        comment="Foreign key to test suite (for suite-level artifacts)",
    )

    # Artifact metadata
    artifact_type: Mapped[ArtifactType] = mapped_column(
        SQLEnum(ArtifactType, name="artifact_type"),
        nullable=False,
        comment="Type of artifact",
    )

    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Original filename",
    )

    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="File size in bytes",
    )

    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="MIME type of the file",
    )

    # Storage metadata
    storage_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        unique=True,
        comment="S3 object key for the stored file",
    )

    storage_url: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
        comment="Generated signed URL (temporary)",
    )

    checksum: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hash for file integrity verification",
    )

    # Lifecycle management
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Expiration time for automatic cleanup",
    )

    config_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Artifact-specific metadata",
    )

    # Relationships
    test_result: Mapped[Optional["TestResult"]] = relationship(
        "TestResult",
        back_populates="test_artifacts",
        lazy="select"
    )

    test_suite: Mapped[Optional["TestSuite"]] = relationship(
        "TestSuite",
        lazy="select"
    )

    # Constraints and indexes
    __table_args__ = (
        # Ensure exactly one parent is set
        CheckConstraint(
            "(result_id IS NOT NULL AND suite_id IS NULL) OR "
            "(result_id IS NULL AND suite_id IS NOT NULL)",
            name="ck_artifact_has_one_parent"
        ),
        CheckConstraint("file_size > 0", name="ck_file_size_positive"),
        CheckConstraint("file_size <= 104857600", name="ck_file_size_limit_100mb"),
        CheckConstraint("length(checksum) = 64", name="ck_checksum_sha256_length"),
        UniqueConstraint("storage_key", name="uq_artifact_storage_key"),
        Index("ix_test_artifacts_result_id", "result_id"),
        Index("ix_test_artifacts_suite_id", "suite_id"),
        Index("ix_test_artifacts_artifact_type", "artifact_type"),
        Index("ix_test_artifacts_expires_at", "expires_at"),
        Index("ix_test_artifacts_result_type", "result_id", "artifact_type"),
        Index("ix_test_artifacts_suite_type", "suite_id", "artifact_type"),
    )

    # Allowed MIME types for validation
    ALLOWED_MIME_TYPES = {
        ArtifactType.SCREENSHOT: [
            "image/png", "image/jpeg", "image/gif", "image/webp"
        ],
        ArtifactType.VIDEO: [
            "video/mp4", "video/webm", "video/avi", "video/mov"
        ],
        ArtifactType.REPORT: [
            "text/html", "application/json", "application/xml", "text/plain",
            "application/pdf"
        ],
        ArtifactType.LOG: [
            "text/plain", "application/json", "text/csv"
        ],
        ArtifactType.TRACE: [
            "application/json", "text/plain", "application/octet-stream"
        ],
        ArtifactType.OTHER: [
            # Allow any MIME type for "other" artifacts
        ]
    }

    @validates("file_name")
    def validate_file_name(self, key: str, file_name: str) -> str:
        """Validate filename."""
        if not file_name or not file_name.strip():
            raise ValueError("File name cannot be empty")

        file_name = file_name.strip()
        if len(file_name) > 255:
            raise ValueError("File name cannot exceed 255 characters")

        # Basic filename validation - no path separators
        if "/" in file_name or "\\" in file_name:
            raise ValueError("File name cannot contain path separators")

        return file_name

    @validates("file_size")
    def validate_file_size(self, key: str, file_size: int) -> int:
        """Validate file size."""
        if file_size <= 0:
            raise ValueError("File size must be greater than 0")

        if file_size > 100 * 1024 * 1024:  # 100MB limit
            raise ValueError("File size cannot exceed 100MB")

        return file_size

    @validates("mime_type")
    def validate_mime_type(self, key: str, mime_type: str) -> str:
        """Validate MIME type."""
        if not mime_type or not mime_type.strip():
            raise ValueError("MIME type cannot be empty")

        mime_type = mime_type.strip().lower()

        # Basic MIME type format validation
        if "/" not in mime_type:
            raise ValueError("MIME type must be in format 'type/subtype'")

        return mime_type

    @validates("storage_key")
    def validate_storage_key(self, key: str, storage_key: str) -> str:
        """Validate storage key format."""
        if not storage_key or not storage_key.strip():
            raise ValueError("Storage key cannot be empty")

        storage_key = storage_key.strip()
        if len(storage_key) > 500:
            raise ValueError("Storage key cannot exceed 500 characters")

        # Basic S3 key validation - no leading/trailing slashes
        if storage_key.startswith("/") or storage_key.endswith("/"):
            raise ValueError("Storage key cannot start or end with '/'")

        return storage_key

    @validates("checksum")
    def validate_checksum(self, key: str, checksum: str) -> str:
        """Validate SHA-256 checksum."""
        if not checksum or not checksum.strip():
            raise ValueError("Checksum cannot be empty")

        checksum = checksum.strip().lower()
        if len(checksum) != 64:
            raise ValueError("Checksum must be 64 characters (SHA-256)")

        # Validate hex format
        try:
            int(checksum, 16)
        except ValueError:
            raise ValueError("Checksum must be valid hexadecimal")

        return checksum

    @validates("config_metadata")
    def validate_config_metadata(self, key: str, config_metadata: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Validate config_metadata is a proper dictionary."""
        if config_metadata is None:
            return None

        if not isinstance(config_metadata, dict):
            raise ValueError("Config metadata must be a dictionary")

        return config_metadata

    def validate_mime_type_for_artifact_type(self) -> None:
        """Validate MIME type is appropriate for artifact type."""
        if self.artifact_type == ArtifactType.OTHER:
            return  # Allow any MIME type for "other"

        allowed_types = self.ALLOWED_MIME_TYPES.get(self.artifact_type, [])
        if allowed_types and self.mime_type not in allowed_types:
            raise ValueError(
                f"MIME type '{self.mime_type}' not allowed for artifact type '{self.artifact_type.value}'. "
                f"Allowed types: {allowed_types}"
            )

    def validate_parent_relationship(self) -> None:
        """Validate exactly one parent relationship is set."""
        if self.result_id is None and self.suite_id is None:
            raise ValueError("Artifact must be associated with either a test result or test suite")

        if self.result_id is not None and self.suite_id is not None:
            raise ValueError("Artifact cannot be associated with both test result and test suite")

    @property
    def file_size_mb(self) -> float:
        """Get file size in megabytes."""
        return self.file_size / (1024 * 1024)

    @property
    def is_expired(self) -> bool:
        """Check if artifact has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() >= self.expires_at

    def __str__(self) -> str:
        """String representation."""
        parent = f"result={self.result_id}" if self.result_id else f"suite={self.suite_id}"
        return f"TestArtifact(file='{self.file_name}', type={self.artifact_type.value}, {parent})"