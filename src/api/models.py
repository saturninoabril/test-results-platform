"""
Pydantic models for API request and response validation.
Defines the contract for all REST API endpoints.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class BaseAPIModel(BaseModel):
    """Base API model with common configuration."""

    model_config = {
        "from_attributes": True,
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }


# Framework Models
class FrameworkCreateRequest(BaseAPIModel):
    """Request model for creating a test framework."""
    name: str = Field(..., description="Framework name (lowercase, alphanumeric)")
    version: str = Field(..., description="Semantic version (e.g., 1.55.0)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Framework-specific metadata")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate framework name format."""
        if not re.match(r'^[a-z][a-z0-9\-]*$', v):
            raise ValueError("Framework name must be lowercase alphanumeric with optional hyphens")
        return v

    @field_validator('version')
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate semantic version format."""
        if not re.match(r'^\d+\.\d+\.\d+$', v):
            raise ValueError("Version must be semantic version format (e.g., 1.55.0)")
        return v


class FrameworkUpdateRequest(BaseAPIModel):
    """Request model for updating a test framework."""
    name: str = Field(..., description="Framework name (lowercase, alphanumeric)")
    version: str = Field(..., description="Semantic version (e.g., 1.55.0)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Framework-specific metadata")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate framework name format."""
        if not re.match(r'^[a-z][a-z0-9\-]*$', v):
            raise ValueError("Framework name must be lowercase alphanumeric with optional hyphens")
        return v

    @field_validator('version')
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate semantic version format."""
        if not re.match(r'^\d+\.\d+\.\d+$', v):
            raise ValueError("Version must be semantic version format (e.g., 1.55.0)")
        return v


class FrameworkResponse(BaseAPIModel):
    """Response model for test framework."""
    id: UUID = Field(..., description="Framework unique identifier")
    name: str = Field(..., description="Framework name")
    version: str = Field(..., description="Framework version")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Framework-specific metadata")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# Environment Models
class EnvironmentCreateRequest(BaseAPIModel):
    """Request model for creating a test environment."""
    name: str = Field(..., description="Environment name")
    browser: Optional[str] = Field(None, description="Browser name (chrome, firefox, safari, edge)")
    os: Optional[str] = Field(None, description="Operating system")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Environment-specific metadata")

    @field_validator('browser')
    @classmethod
    def validate_browser(cls, v: Optional[str]) -> Optional[str]:
        """Validate browser name."""
        if v is not None:
            allowed_browsers = {'chrome', 'firefox', 'safari', 'edge', 'webkit'}
            if v.lower() not in allowed_browsers:
                raise ValueError(f"Browser must be one of: {', '.join(allowed_browsers)}")
            return v.lower()
        return v


class EnvironmentUpdateRequest(BaseAPIModel):
    """Request model for updating a test environment."""
    name: str = Field(..., description="Environment name")
    browser: Optional[str] = Field(None, description="Browser name (chrome, firefox, safari, edge)")
    os: Optional[str] = Field(None, description="Operating system")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Environment-specific metadata")

    @field_validator('browser')
    @classmethod
    def validate_browser(cls, v: Optional[str]) -> Optional[str]:
        """Validate browser name."""
        if v is not None:
            allowed_browsers = {'chrome', 'firefox', 'safari', 'edge', 'webkit'}
            if v.lower() not in allowed_browsers:
                raise ValueError(f"Browser must be one of: {', '.join(allowed_browsers)}")
            return v.lower()
        return v


class EnvironmentResponse(BaseAPIModel):
    """Response model for test environment."""
    id: UUID = Field(..., description="Environment unique identifier")
    name: str = Field(..., description="Environment name")
    browser: Optional[str] = Field(None, description="Browser name")
    os: Optional[str] = Field(None, description="Operating system")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Environment-specific metadata")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# Suite Models
class SuiteCreateRequest(BaseAPIModel):
    """Request model for creating a test suite."""
    framework_id: UUID = Field(..., description="Framework ID")
    environment_id: UUID = Field(..., description="Environment ID")
    name: str = Field(..., description="Suite name")
    total_count: int = Field(..., ge=0, description="Total number of tests")
    passed_count: int = Field(..., ge=0, description="Number of passed tests")
    failed_count: int = Field(..., ge=0, description="Number of failed tests")
    skipped_count: int = Field(..., ge=0, description="Number of skipped tests")
    duration_ms: Optional[int] = Field(None, ge=0, description="Total duration in milliseconds")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Suite-specific metadata")

    @field_validator('passed_count', 'failed_count', 'skipped_count')
    @classmethod
    def validate_counts_sum(cls, v, info):
        """Validate that counts don't exceed total."""
        # This validation will be done at the model level after all fields are set
        return v

    def model_post_init(self, __context) -> None:
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
    framework_id: UUID = Field(..., description="Framework ID")
    environment_id: UUID = Field(..., description="Environment ID")
    name: str = Field(..., description="Suite name")
    total_count: int = Field(..., ge=0, description="Total number of tests")
    passed_count: int = Field(..., ge=0, description="Number of passed tests")
    failed_count: int = Field(..., ge=0, description="Number of failed tests")
    skipped_count: int = Field(..., ge=0, description="Number of skipped tests")
    duration_ms: Optional[int] = Field(None, ge=0, description="Total duration in milliseconds")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Suite-specific metadata")

    def model_post_init(self, __context) -> None:
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
    framework_id: UUID = Field(..., description="Framework ID")
    environment_id: UUID = Field(..., description="Environment ID")
    name: str = Field(..., description="Suite name")
    total_count: int = Field(..., description="Total number of tests")
    passed_count: int = Field(..., description="Number of passed tests")
    failed_count: int = Field(..., description="Number of failed tests")
    skipped_count: int = Field(..., description="Number of skipped tests")
    duration_ms: Optional[int] = Field(None, description="Total duration in milliseconds")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Suite-specific metadata")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# Result Models
class ResultCreateRequest(BaseAPIModel):
    """Request model for creating a test result."""
    suite_id: UUID = Field(..., description="Suite ID")
    name: str = Field(..., description="Test name")
    status: str = Field(..., description="Test status (passed, failed, skipped)")
    duration_ms: Optional[int] = Field(None, ge=0, description="Test duration in milliseconds")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    tags: List[str] = Field(default_factory=list, description="Test tags")
    external_id: Optional[str] = Field(None, description="External test ID")
    full_title: Optional[str] = Field(None, description="Full test title/path")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Test-specific metadata")

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate test result status."""
        allowed_statuses = {'passed', 'failed', 'skipped'}
        if v.lower() not in allowed_statuses:
            raise ValueError(f"Status must be one of: {', '.join(allowed_statuses)}")
        return v.lower()


class ResultUpdateRequest(BaseAPIModel):
    """Request model for updating a test result."""
    suite_id: UUID = Field(..., description="Suite ID")
    name: str = Field(..., description="Test name")
    status: str = Field(..., description="Test status (passed, failed, skipped)")
    duration_ms: Optional[int] = Field(None, ge=0, description="Test duration in milliseconds")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    tags: List[str] = Field(default_factory=list, description="Test tags")
    external_id: Optional[str] = Field(None, description="External test ID")
    full_title: Optional[str] = Field(None, description="Full test title/path")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Test-specific metadata")

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate test result status."""
        allowed_statuses = {'passed', 'failed', 'skipped'}
        if v.lower() not in allowed_statuses:
            raise ValueError(f"Status must be one of: {', '.join(allowed_statuses)}")
        return v.lower()


class ResultResponse(BaseAPIModel):
    """Response model for test result."""
    id: UUID = Field(..., description="Result unique identifier")
    suite_id: UUID = Field(..., description="Suite ID")
    name: str = Field(..., description="Test name")
    status: str = Field(..., description="Test status")
    duration_ms: Optional[int] = Field(None, description="Test duration in milliseconds")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    tags: List[str] = Field(..., description="Test tags")
    external_id: Optional[str] = Field(None, description="External test ID")
    full_title: Optional[str] = Field(None, description="Full test title/path")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Test-specific metadata")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# Artifact Models
class ArtifactCreateRequest(BaseAPIModel):
    """Request model for creating a test artifact."""
    result_id: Optional[UUID] = Field(None, description="Associated result ID")
    suite_id: Optional[UUID] = Field(None, description="Associated suite ID")
    name: str = Field(..., description="Artifact name")
    artifact_type: str = Field(..., description="Artifact type (screenshot, video, log, report)")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    content_type: str = Field(..., description="MIME content type")
    checksum: str = Field(..., description="SHA-256 checksum")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Artifact-specific metadata")

    @field_validator('artifact_type')
    @classmethod
    def validate_artifact_type(cls, v: str) -> str:
        """Validate artifact type."""
        allowed_types = {'screenshot', 'video', 'log', 'report', 'trace', 'attachment'}
        if v.lower() not in allowed_types:
            raise ValueError(f"Artifact type must be one of: {', '.join(allowed_types)}")
        return v.lower()


class ArtifactResponse(BaseAPIModel):
    """Response model for test artifact."""
    id: UUID = Field(..., description="Artifact unique identifier")
    result_id: Optional[UUID] = Field(None, description="Associated result ID")
    suite_id: Optional[UUID] = Field(None, description="Associated suite ID")
    name: str = Field(..., description="Artifact name")
    artifact_type: str = Field(..., description="Artifact type")
    file_size: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="MIME content type")
    checksum: str = Field(..., description="SHA-256 checksum")
    storage_key: str = Field(..., description="Storage key/path")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Artifact-specific metadata")
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
    permissions: List[str] = Field(..., description="Requested permissions")
    expiration_days: Optional[int] = Field(None, ge=1, le=365, description="Token expiration in days")


class TokenResponse(BaseAPIModel):
    """Response model for token generation."""
    access_token: str = Field(..., description="Access token")
    refresh_token: Optional[str] = Field(None, description="Refresh token")
    token_type: str = Field(..., description="Token type (Bearer)")
    expires_in: int = Field(..., description="Token expiration in seconds")
    permissions: Optional[List[str]] = Field(None, description="Token permissions")


class UserProfileResponse(BaseAPIModel):
    """Response model for user profile."""
    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    role: str = Field(..., description="User role")
    permissions: List[str] = Field(..., description="User permissions")
    github_id: Optional[int] = Field(None, description="GitHub user ID")


# Error Models
class ErrorDetail(BaseAPIModel):
    """Error detail model."""
    type: str = Field(..., description="Error type")
    msg: str = Field(..., description="Error message")
    input: Optional[Any] = Field(None, description="Input that caused error")


class ErrorResponse(BaseAPIModel):
    """Response model for API errors."""
    detail: str = Field(..., description="Error message")
    errors: Optional[List[ErrorDetail]] = Field(None, description="Validation errors")