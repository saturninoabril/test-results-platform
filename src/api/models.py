"""
Pydantic models for API request and response validation.
Defines the contract for all REST API endpoints.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, ValidationInfo, field_validator


class BaseAPIModel(BaseModel):
    """Base API model with common configuration."""

    model_config = {"from_attributes": True, "json_encoders": {datetime: lambda v: v.isoformat()}}


# Suite Models
class SuiteCreateRequest(BaseAPIModel):
    """Request model for creating a test suite."""

    name: str = Field(..., description="Suite name")
    total_count: int = Field(..., ge=0, description="Total number of tests")
    passed_count: int = Field(..., ge=0, description="Number of passed tests")
    failed_count: int = Field(..., ge=0, description="Number of failed tests")
    skipped_count: int = Field(..., ge=0, description="Number of skipped tests")
    duration_ms: int | None = Field(None, ge=0, description="Total duration in milliseconds")
    framework_metadata: dict[str, Any] | None = Field(
        None, description="Framework-specific metadata"
    )
    environment_metadata: dict[str, Any] | None = Field(
        None, description="Environment-specific metadata"
    )
    server_metadata: dict[str, Any] | None = Field(None, description="Server-specific metadata")
    ci_run_metadata: dict[str, Any] | None = Field(None, description="CI-specific metadata")

    @field_validator("passed_count", "failed_count", "skipped_count")
    @classmethod
    def validate_counts_sum(cls, v: int, _info: ValidationInfo) -> int:
        """Validate that counts don't exceed total."""
        # This validation will be done at the model level after all fields are set
        return v

    def model_post_init(self, __context: Any) -> None:
        """Validate count consistency after model creation."""
        calculated_total = self.passed_count + self.failed_count + self.skipped_count
        if calculated_total != self.total_count:
            raise ValueError(
                f"Count mismatch: passed({self.passed_count}) + "
                f"failed({self.failed_count}) + skipped({self.skipped_count}) = "
                f"{calculated_total}, but total_count is {self.total_count}"
            )


class SuiteUpdateRequest(BaseAPIModel):
    """Request model for updating a test suite."""

    name: str = Field(..., description="Suite name")
    total_count: int = Field(..., ge=0, description="Total number of tests")
    passed_count: int = Field(..., ge=0, description="Number of passed tests")
    failed_count: int = Field(..., ge=0, description="Number of failed tests")
    skipped_count: int = Field(..., ge=0, description="Number of skipped tests")
    duration_ms: int | None = Field(None, ge=0, description="Total duration in milliseconds")
    framework_metadata: dict[str, Any] | None = Field(
        None, description="Framework-specific metadata"
    )
    environment_metadata: dict[str, Any] | None = Field(
        None, description="Environment-specific metadata"
    )
    server_metadata: dict[str, Any] | None = Field(None, description="Server-specific metadata")
    ci_run_metadata: dict[str, Any] | None = Field(None, description="CI-specific metadata")

    def model_post_init(self, __context: Any) -> None:
        """Validate count consistency after model creation."""
        calculated_total = self.passed_count + self.failed_count + self.skipped_count
        if calculated_total != self.total_count:
            raise ValueError(
                f"Count mismatch: passed({self.passed_count}) + "
                f"failed({self.failed_count}) + skipped({self.skipped_count}) = "
                f"{calculated_total}, but total_count is {self.total_count}"
            )


class SuiteResponse(BaseAPIModel):
    """Response model for test suite."""

    id: UUID = Field(..., description="Suite unique identifier")
    name: str = Field(..., description="Suite name")
    total_count: int = Field(..., description="Total number of tests")
    passed_count: int = Field(..., description="Number of passed tests")
    failed_count: int = Field(..., description="Number of failed tests")
    skipped_count: int = Field(..., description="Number of skipped tests")
    duration_ms: int | None = Field(None, description="Total duration in milliseconds")
    framework_metadata: dict[str, Any] | None = Field(
        None, description="Framework-specific metadata"
    )
    environment_metadata: dict[str, Any] | None = Field(
        None, description="Environment-specific metadata"
    )
    server_metadata: dict[str, Any] | None = Field(None, description="Server-specific metadata")
    ci_run_metadata: dict[str, Any] | None = Field(None, description="CI-specific metadata")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# Result Models
class ResultCreateRequest(BaseAPIModel):
    """Request model for creating a test result."""

    suite_id: UUID = Field(..., description="Suite ID")
    name: str = Field(..., description="Test name")
    status: str = Field(..., description="Test status (passed, failed, skipped)")
    duration_ms: int | None = Field(None, ge=0, description="Test duration in milliseconds")
    error_message: str | None = Field(None, description="Error message if failed")
    tags: list[str] = Field(default_factory=list, description="Test tags")
    external_id: str | None = Field(None, description="External test ID")
    full_title: str | None = Field(None, description="Full test title/path")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate test result status."""
        allowed_statuses = {"passed", "failed", "skipped"}
        if v.lower() not in allowed_statuses:
            raise ValueError(f"Status must be one of: {', '.join(allowed_statuses)}")
        return v.lower()


class ResultUpdateRequest(BaseAPIModel):
    """Request model for updating a test result."""

    suite_id: UUID = Field(..., description="Suite ID")
    name: str = Field(..., description="Test name")
    status: str = Field(..., description="Test status (passed, failed, skipped)")
    duration_ms: int | None = Field(None, ge=0, description="Test duration in milliseconds")
    error_message: str | None = Field(None, description="Error message if failed")
    tags: list[str] = Field(default_factory=list, description="Test tags")
    external_id: str | None = Field(None, description="External test ID")
    full_title: str | None = Field(None, description="Full test title/path")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate test result status."""
        allowed_statuses = {"passed", "failed", "skipped"}
        if v.lower() not in allowed_statuses:
            raise ValueError(f"Status must be one of: {', '.join(allowed_statuses)}")
        return v.lower()


class ResultResponse(BaseAPIModel):
    """Response model for test result."""

    id: UUID = Field(..., description="Result unique identifier")
    suite_id: UUID = Field(..., description="Suite ID")
    name: str = Field(..., description="Test name")
    status: str = Field(..., description="Test status")
    duration_ms: int | None = Field(None, description="Test duration in milliseconds")
    error_message: str | None = Field(None, description="Error message if failed")
    tags: list[str] = Field(..., description="Test tags")
    external_id: str | None = Field(None, description="External test ID")
    full_title: str | None = Field(None, description="Full test title/path")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# Artifact Models
class ArtifactCreateRequest(BaseAPIModel):
    """Request model for creating a test artifact."""

    result_id: UUID | None = Field(None, description="Associated result ID")
    suite_id: UUID | None = Field(None, description="Associated suite ID")
    name: str = Field(..., description="Artifact name")
    artifact_type: str = Field(..., description="Artifact type (screenshot, video, log, report)")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    content_type: str = Field(..., description="MIME content type")
    checksum: str = Field(..., description="SHA-256 checksum")

    @field_validator("artifact_type")
    @classmethod
    def validate_artifact_type(cls, v: str) -> str:
        """Validate artifact type."""
        allowed_types = {"screenshot", "video", "log", "report", "trace", "attachment"}
        if v.lower() not in allowed_types:
            raise ValueError(f"Artifact type must be one of: {', '.join(allowed_types)}")
        return v.lower()


class ArtifactResponse(BaseAPIModel):
    """Response model for test artifact."""

    id: UUID = Field(..., description="Artifact unique identifier")
    result_id: UUID | None = Field(None, description="Associated result ID")
    suite_id: UUID | None = Field(None, description="Associated suite ID")
    name: str = Field(..., description="Artifact name")
    artifact_type: str = Field(..., description="Artifact type")
    file_size: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="MIME content type")
    checksum: str = Field(..., description="SHA-256 checksum")
    storage_key: str = Field(..., description="Storage key/path")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# Authentication Models
class TokenRequest(BaseAPIModel):
    """Request model for token generation."""

    grant_type: str = Field(..., description="Grant type (github_oauth)")
    code: str = Field(..., description="OAuth authorization code")
    state: str = Field(..., description="OAuth state parameter")


class AutomationTokenRequest(BaseAPIModel):
    """Request model for automation token generation."""

    automation_name: str = Field(..., description="Automation system name")
    permissions: list[str] = Field(..., description="Requested permissions")
    expiration_days: int | None = Field(None, ge=1, le=365, description="Token expiration in days")


class TokenResponse(BaseAPIModel):
    """Response model for token generation."""

    access_token: str = Field(..., description="Access token")
    refresh_token: str | None = Field(None, description="Refresh token")
    token_type: str = Field(..., description="Token type (Bearer)")
    expires_in: int = Field(..., description="Token expiration in seconds")
    permissions: list[str] | None = Field(None, description="Token permissions")


class UserProfileResponse(BaseAPIModel):
    """Response model for user profile."""

    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    role: str = Field(..., description="User role")
    permissions: list[str] = Field(..., description="User permissions")
    github_id: int | None = Field(None, description="GitHub user ID")


# Error Models
class ErrorDetail(BaseAPIModel):
    """Error detail model."""

    type: str = Field(..., description="Error type")
    msg: str = Field(..., description="Error message")
    input: Any | None = Field(None, description="Input that caused error")


class ErrorResponse(BaseAPIModel):
    """Response model for API errors."""

    detail: str = Field(..., description="Error message")
    errors: list[ErrorDetail] | None = Field(None, description="Validation errors")
