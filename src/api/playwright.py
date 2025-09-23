"""
Playwright API endpoints for test suite management.
Provides REST API for Playwright-specific test result management with real-time events.
"""

import uuid
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

# Authentication removed for public Playwright API
from ..models.test_suite import SuiteStatus
from ..services.playwright_service import (
    PlaywrightNotFoundError,
    PlaywrightService,
    PlaywrightValidationError,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/playwright", tags=["playwright"])


def get_request_context() -> tuple[str, str | None]:
    """Extract request_id for public API access."""
    request_id = str(uuid.uuid4())
    user_id = None  # No authentication for public Playwright API
    return request_id, user_id


def format_validation_error(error_message: str) -> list[dict[str, Any]]:
    """Format validation error message into FastAPI-compatible error detail format."""
    # Parse common validation error patterns to determine field name
    # Order from most specific to least specific to avoid partial matches
    field_mapping = [
        ("Suite with ID", "suite_id"),
        ("test_count", "test_count"),
        ("duration", "duration"),
        ("timeout", "timeout"),
        ("tags", "tags"),
        ("location", "location"),
        ("event_type", "event_type"),
        ("suite_id", "suite_id"),
        ("end_time", "end_time"),
        ("start_time", "start_time"),
        ("Browser", "browser_name"),
        ("Viewport", "viewport"),
        ("width", "viewport"),
        ("height", "viewport"),
        ("Device", "device_name"),
        ("Suite", "name"),
        ("Framework", "framework"),
        ("Status", "status"),
    ]

    # Try to match error message to field
    field_name = "body"  # default
    for keyword, field in field_mapping:
        if keyword.lower() in error_message.lower():
            field_name = field
            break

    return [{"type": "value_error", "loc": ["body", field_name], "msg": error_message}]


# Playwright-specific Pydantic models
class PlaywrightSuiteCreateRequest(BaseModel):
    """Request model for creating a Playwright test suite."""

    name: str = Field(..., description="Test suite name")
    version: str = Field(..., description="Playwright version")  # Added required version field
    test_count: int = Field(..., description="Number of tests in suite")
    status: SuiteStatus = Field(..., description="Suite status")

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v: Any) -> str:
        if isinstance(v, str):
            return SuiteStatus.normalize(v).value  # Return the value, not the enum object
        return str(v)

    start_time: datetime = Field(..., description="Suite start time")
    end_time: datetime | None = Field(None, description="Suite end time")
    framework_metadata: dict[str, Any] | None = Field(
        None, description="Framework-specific metadata"
    )
    environment_metadata: dict[str, Any] | None = Field(
        None, description="Environment-specific metadata"
    )
    server_metadata: dict[str, Any] | None = Field(None, description="Server-specific metadata")
    ci_run_metadata: dict[str, Any] | None = Field(None, description="CI run-specific metadata")
    playwright_test_files: dict[str, Any] | None = Field(
        None, description="Playwright test files metadata"
    )

    @field_validator("framework_metadata")
    @classmethod
    def validate_framework_metadata(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Validate that framework metadata indicates playwright framework."""
        if v is not None and isinstance(v, dict):
            framework_name = v.get("name", "").lower()
            if framework_name and framework_name != "playwright":
                raise ValueError("Framework metadata name must be 'playwright' for Playwright API")
        return v

    model_config = {"from_attributes": True}


class PlaywrightSuiteUpdateRequest(BaseModel):
    """Request model for updating a Playwright test suite."""

    status: SuiteStatus | None = Field(None, description="Suite status")

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v: Any) -> str | None:
        if isinstance(v, str):
            return SuiteStatus.normalize(v).value  # Return the value, not the enum object
        return str(v) if v is not None else None

    end_time: datetime | None = Field(None, description="Suite end time")
    duration: int | None = Field(None, description="Suite duration in milliseconds")
    test_count: int | None = Field(None, description="Number of tests in suite")

    model_config = {"from_attributes": True}


class PlaywrightSuiteResponse(BaseModel):
    """Response model for Playwright test suite."""

    id: UUID = Field(..., description="Suite unique identifier")
    name: str = Field(..., description="Suite name")
    test_count: int = Field(..., description="Number of tests")
    status: str = Field(..., description="Suite status")
    start_time: datetime = Field(..., description="Suite start time")
    end_time: datetime | None = Field(None, description="Suite end time")
    duration: int | None = Field(None, description="Suite duration in milliseconds")
    framework_metadata: dict[str, Any] | None = Field(
        None, description="Framework-specific metadata"
    )
    environment_metadata: dict[str, Any] | None = Field(
        None, description="Environment-specific metadata"
    )
    server_metadata: dict[str, Any] | None = Field(None, description="Server-specific metadata")
    ci_run_metadata: dict[str, Any] | None = Field(None, description="CI run-specific metadata")
    playwright_test_files: dict[str, Any] | None = Field(
        None, description="Playwright test files metadata"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"from_attributes": True}


class PlaywrightTestResultCreateRequest(BaseModel):
    """Request model for creating a Playwright test result."""

    suite_id: UUID = Field(..., description="Suite ID")
    external_id: str | None = Field(None, description="External test identifier")
    title: str = Field(..., description="Test title")
    full_title: str = Field(..., description="Full test title with hierarchy")
    status: str = Field(..., description="Test status")
    location: dict[str, Any] | None = Field(None, description="Test location information")
    project_name: str | None = Field(None, description="Playwright project name")
    timeout: int | None = Field(None, description="Test timeout in milliseconds")
    tags: list[str] | None = Field(None, description="Test tags")
    start_time: datetime | None = Field(None, description="Test start time")
    duration: int | None = Field(None, description="Test duration in milliseconds")
    error_message: str | None = Field(None, description="Error message if failed")
    retry_count: int = Field(0, description="Number of times the test was retried")

    model_config = {"from_attributes": True}


class PlaywrightTestResultUpdateRequest(BaseModel):
    """Request model for updating a Playwright test result."""

    status: str | None = Field(None, description="Test status")
    duration: int | None = Field(None, description="Test duration in milliseconds")
    end_time: datetime | None = Field(None, description="Test end time")
    error_message: str | None = Field(None, description="Error message if failed")
    stack_trace: str | None = Field(None, description="Stack trace for failed tests")

    model_config = {"from_attributes": True}


class PlaywrightArtifactSummaryResponse(BaseModel):
    """Response model for artifact summary in test results."""

    id: UUID = Field(..., description="Artifact unique identifier")
    type: str = Field(..., description="Artifact type")
    filename: str = Field(..., description="Artifact filename")
    storage_path: str = Field(..., description="Storage path")
    file_size: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="Content type")
    capture_time: datetime | None = Field(None, description="When artifact was captured")
    test_step: str | None = Field(None, description="Test step when captured")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {"from_attributes": True}


class PlaywrightTestResultResponse(BaseModel):
    """Response model for Playwright test result."""

    id: UUID = Field(..., description="Test result unique identifier")
    suite_id: UUID = Field(..., description="Suite ID")
    external_id: str | None = Field(None, description="External test identifier")
    title: str = Field(..., description="Test title")
    full_title: str = Field(..., description="Full test title")
    status: str = Field(..., description="Test status")
    location: dict[str, Any] | None = Field(None, description="Test location")
    project_name: str | None = Field(None, description="Playwright project name")
    timeout: int | None = Field(None, description="Test timeout in milliseconds")
    tags: list[str] | None = Field(None, description="Test tags")
    duration: int | None = Field(None, description="Test duration in milliseconds")
    error_message: str | None = Field(None, description="Error message")
    stack_trace: str | None = Field(None, description="Stack trace")
    retry_count: int = Field(0, description="Number of retry attempts")
    start_time: datetime | None = Field(None, description="Test start time")
    end_time: datetime | None = Field(None, description="Test end time")
    artifacts: list[PlaywrightArtifactSummaryResponse] = Field([], description="Test artifacts")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"from_attributes": True}


class PlaywrightTestResultsSummaryResponse(BaseModel):
    """Response model for test results summary statistics."""

    total_tests: int = Field(..., description="Total number of tests")
    total_duration_ms: int = Field(..., description="Total duration in milliseconds")
    status_counts: dict[str, int] = Field(..., description="Count of tests by status")

    model_config = {"from_attributes": True}


class PlaywrightTestResultsListResponse(BaseModel):
    """Response model for Playwright test results list."""

    total: int = Field(..., description="Total number of results")
    summary: PlaywrightTestResultsSummaryResponse = Field(
        ..., description="Test suite summary statistics"
    )
    results: list[PlaywrightTestResultResponse] = Field(..., description="Test results")

    model_config = {"from_attributes": True}


class PlaywrightArtifactPresignedRequest(BaseModel):
    """Request model for Playwright artifact presigned upload URL."""

    filename: str = Field(..., description="Artifact filename")
    content_type: str = Field(..., description="MIME type of the artifact")
    artifact_type: str = Field(..., description="Type of artifact")
    file_size: int = Field(..., description="File size in bytes")
    suite_id: str = Field(..., description="Test suite ID")
    test_result_id: str = Field(..., description="Test result ID")
    relative_path: str = Field(
        ..., description="Relative path from test-results directory to preserve folder structure"
    )

    model_config = {"from_attributes": True}


class PlaywrightArtifactPresignedResponse(BaseModel):
    """Response model for Playwright artifact presigned upload URL."""

    upload_url: str = Field(..., description="Presigned upload URL")
    fields: dict[str, str] = Field(default_factory=dict, description="Presigned POST form fields")
    storage_path: str = Field(..., description="Storage path in S3")
    expires_in: int = Field(..., description="Expiration time in seconds")

    model_config = {"from_attributes": True}


class PlaywrightArtifactCreateRequest(BaseModel):
    """Request model for creating a Playwright artifact."""

    type: str = Field(..., description="Artifact type")
    filename: str = Field(..., description="Artifact filename")
    storage_path: str = Field(..., description="Storage path in S3")
    file_size: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="MIME type")
    capture_time: datetime = Field(..., description="When artifact was captured")
    test_step: str | None = Field(None, description="Test step when captured")

    model_config = {"from_attributes": True}


class PlaywrightArtifactResponse(BaseModel):
    """Response model for Playwright artifact."""

    id: UUID = Field(..., description="Artifact unique identifier")
    test_result_id: UUID = Field(..., description="Associated test result ID")
    type: str = Field(..., description="Artifact type")
    filename: str = Field(..., description="Artifact filename")
    storage_path: str = Field(..., description="Storage path")
    file_size: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="MIME type")
    capture_time: datetime = Field(..., description="Capture time")
    test_step: str | None = Field(None, description="Test step")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"from_attributes": True}


class PlaywrightEventCreateRequest(BaseModel):
    """Request model for creating a Playwright event."""

    suite_id: UUID = Field(..., description="Suite ID")
    test_external_id: str | None = Field(None, description="External test identifier")
    event_type: str = Field(..., description="Event type")
    timestamp: datetime = Field(..., description="Event timestamp")
    data: dict[str, Any] | None = Field(None, description="Event data")

    model_config = {"from_attributes": True}


class PlaywrightEventResponse(BaseModel):
    """Response model for Playwright event."""

    id: UUID = Field(..., description="Event unique identifier")
    suite_id: UUID = Field(..., description="Suite ID")
    test_external_id: str | None = Field(None, description="External test identifier")
    event_type: str = Field(..., description="Event type")
    timestamp: datetime = Field(..., description="Event timestamp")
    data: dict[str, Any] | None = Field(None, description="Event data")
    request_id: str | None = Field(None, description="Request ID from originating HTTP request")
    user_id: str | None = Field(None, description="User ID from authenticated request context")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"from_attributes": True}


class PlaywrightEventsListResponse(BaseModel):
    """Response model for Playwright events list."""

    total: int = Field(..., description="Total number of events")
    events: list[PlaywrightEventResponse] = Field(..., description="Events")

    model_config = {"from_attributes": True}


@router.post(
    "/suites",
    response_model=PlaywrightSuiteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a Playwright test suite",
    description="Create a new Playwright test suite with framework-specific metadata",
)
async def create_playwright_suite(request: PlaywrightSuiteCreateRequest) -> PlaywrightSuiteResponse:
    """Create a new Playwright test suite."""
    try:
        suite_data = await PlaywrightService.create_suite(
            name=request.name,
            version=request.version,
            test_count=request.test_count,
            status=request.status,
            start_time=request.start_time,
            end_time=request.end_time,
            framework_metadata=request.framework_metadata,
            environment_metadata=request.environment_metadata,
            server_metadata=request.server_metadata,
            ci_run_metadata=request.ci_run_metadata,
            playwright_test_files=request.playwright_test_files,
        )

        logger.info(
            "Playwright suite created via API",
            suite_id=str(suite_data["id"]),
            name=suite_data["name"],
        )

        return PlaywrightSuiteResponse(**suite_data)

    except PlaywrightValidationError as e:
        logger.warning("Playwright suite creation validation error", error=str(e))
        error_detail = format_validation_error(str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error_detail
        ) from e

    except Exception as e:
        logger.error("Playwright suite creation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while creating Playwright suite",
        ) from e


@router.put(
    "/suites/{suite_id}",
    response_model=PlaywrightSuiteResponse,
    summary="Update a Playwright test suite",
    description="Update an existing Playwright test suite's status and timing",
)
async def update_playwright_suite(
    suite_id: UUID, request: PlaywrightSuiteUpdateRequest
) -> PlaywrightSuiteResponse:
    """Update a Playwright test suite."""
    try:
        suite_data = await PlaywrightService.update_suite(
            suite_id=suite_id,
            status=request.status,
            end_time=request.end_time,
            duration=request.duration,
            test_count=request.test_count,
        )

        logger.info(
            "Playwright suite updated via API",
            suite_id=str(suite_id),
            status=request.status,
        )

        return PlaywrightSuiteResponse(**suite_data)

    except PlaywrightNotFoundError as e:
        logger.warning("Playwright suite not found", suite_id=str(suite_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except PlaywrightValidationError as e:
        logger.warning(
            "Playwright suite update validation error", suite_id=str(suite_id), error=str(e)
        )
        error_detail = format_validation_error(str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error_detail
        ) from e

    except Exception as e:
        logger.error("Playwright suite update failed", suite_id=str(suite_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while updating Playwright suite",
        ) from e


@router.post(
    "/test-results",
    response_model=PlaywrightTestResultResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a Playwright test result",
    description="Create a new Playwright test result with execution metadata",
)
async def create_playwright_test_result(
    request: PlaywrightTestResultCreateRequest,
) -> PlaywrightTestResultResponse:
    """Create a new Playwright test result."""
    try:
        result_data = await PlaywrightService.create_test_result(
            suite_id=request.suite_id,
            external_id=request.external_id,
            title=request.title,
            full_title=request.full_title,
            status=request.status,
            location=request.location,
            project_name=request.project_name,
            timeout=request.timeout,
            tags=request.tags,
            start_time=request.start_time,
            duration=request.duration,
            error_message=request.error_message,
            retry_count=request.retry_count,
        )

        logger.info(
            "Playwright test result created via API",
            result_id=str(result_data["id"]),
            external_id=result_data["external_id"],
            status=result_data["status"],
        )

        return PlaywrightTestResultResponse(**result_data)

    except PlaywrightValidationError as e:
        logger.warning("Playwright test result creation validation error", error=str(e))
        error_detail = format_validation_error(str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error_detail
        ) from e

    except Exception as e:
        logger.error("Playwright test result creation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while creating Playwright test result",
        ) from e


@router.put(
    "/test-results/{external_id}",
    response_model=PlaywrightTestResultResponse,
    summary="Update a Playwright test result",
    description="Update an existing Playwright test result's status and execution details",
)
async def update_playwright_test_result(
    external_id: str,
    request: PlaywrightTestResultUpdateRequest,
    suite_id: UUID = Query(..., description="Suite ID to identify the test result"),
) -> PlaywrightTestResultResponse:
    """Update a Playwright test result."""
    try:
        result_data = await PlaywrightService.update_test_result(
            external_id=external_id,
            suite_id=suite_id,
            status=request.status,
            duration=request.duration,
            _end_time=request.end_time,
            error_message=request.error_message,
            stack_trace=request.stack_trace,
        )

        logger.info(
            "Playwright test result updated via API",
            external_id=external_id,
            suite_id=str(suite_id),
            status=request.status,
        )

        return PlaywrightTestResultResponse(**result_data)

    except PlaywrightNotFoundError as e:
        logger.warning(
            "Playwright test result not found", external_id=external_id, suite_id=str(suite_id)
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except PlaywrightValidationError as e:
        logger.warning(
            "Playwright test result update validation error", external_id=external_id, error=str(e)
        )
        error_detail = format_validation_error(str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error_detail
        ) from e

    except Exception as e:
        logger.error("Playwright test result update failed", external_id=external_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while updating Playwright test result",
        ) from e


@router.get(
    "/test-results",
    response_model=PlaywrightTestResultsListResponse,
    summary="Get Playwright test results",
    description="Retrieve Playwright test results with optional filtering",
)
async def get_playwright_test_results(
    suite_id: UUID = Query(..., description="Filter by suite ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
) -> PlaywrightTestResultsListResponse:
    """Get Playwright test results."""
    try:
        results_data = await PlaywrightService.get_test_results(
            suite_id=suite_id,
            limit=limit,
            offset=offset,
        )

        # Convert to response objects
        results = []
        for result_data in results_data["results"]:
            # Convert artifact data to response models
            artifacts = [
                PlaywrightArtifactSummaryResponse(**artifact)
                for artifact in result_data.get("artifacts", [])
            ]

            # Create test result response with artifacts
            result_response = PlaywrightTestResultResponse(
                **{**result_data, "artifacts": artifacts}
            )
            results.append(result_response)

        # Convert summary to response model
        summary = PlaywrightTestResultsSummaryResponse(**results_data["summary"])

        logger.info(
            "Playwright test results retrieved via API",
            suite_id=str(suite_id),
            count=len(results),
        )

        return PlaywrightTestResultsListResponse(
            total=results_data["total"],
            summary=summary,
            results=results,
        )

    except Exception as e:
        logger.error(
            "Playwright test results retrieval failed", suite_id=str(suite_id), error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving Playwright test results",
        ) from e


@router.post(
    "/artifacts/presigned-upload",
    response_model=PlaywrightArtifactPresignedResponse,
    status_code=status.HTTP_200_OK,
    summary="Get presigned URL for artifact upload",
    description="Generate a presigned URL for uploading artifacts to S3",
)
async def get_playwright_artifact_presigned_upload(
    request: PlaywrightArtifactPresignedRequest,
) -> PlaywrightArtifactPresignedResponse:
    """Get presigned URL for artifact upload."""
    try:
        # Import storage utilities

        from ..lib.storage import get_storage

        # Use the original test-results folder structure: playwright/suites/{suite_id}/{relative_path}
        # Example: playwright/suites/{suite_id}/test-results/example-failing-test-for-artifact-upload-demo-chromium/test-failed-1.png
        if not request.relative_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="relative_path is required for artifact uploads",
            )

        storage_key = f"playwright/suites/{request.suite_id}/{request.relative_path}"

        # Use the storage service to generate signed upload URL
        async with get_storage() as storage:
            upload_data = await storage.generate_upload_signed_url(
                storage_key=storage_key,
                content_type=request.content_type,
                expiration=3600,  # 1 hour
            )

        response_data = {
            "upload_url": upload_data["upload_url"],
            "fields": upload_data.get("fields", {}),
            "storage_path": storage_key,
            "expires_in": upload_data["expires_in"],
        }

        logger.info(
            "Playwright artifact presigned URL generated",
            filename=request.filename,
            artifact_type=request.artifact_type,
            storage_path=storage_key,
        )

        return PlaywrightArtifactPresignedResponse(**response_data)

    except Exception as e:
        logger.error("Playwright artifact presigned URL generation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while generating presigned URL",
        ) from e


@router.post(
    "/test-results/{test_result_id}/artifacts",
    response_model=PlaywrightArtifactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a Playwright test artifact",
    description="Register an artifact after successful upload to S3",
)
async def create_playwright_test_artifact(
    test_result_id: UUID,
    request: PlaywrightArtifactCreateRequest,
) -> PlaywrightArtifactResponse:
    """Register a Playwright test artifact."""
    try:
        # Parse capture time - it should already be a datetime from Pydantic
        capture_time = request.capture_time

        # Create artifact using the service layer
        artifact_data = await PlaywrightService.create_artifact(
            test_result_id=test_result_id,
            artifact_type=request.type,
            filename=request.filename,
            storage_path=request.storage_path,
            file_size=request.file_size,
            content_type=request.content_type,
            capture_time=capture_time,
            test_step=request.test_step,
        )

        return PlaywrightArtifactResponse(**artifact_data)

    except Exception as e:
        logger.error(
            "Playwright test artifact registration failed",
            test_result_id=str(test_result_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while registering test artifact",
        ) from e


@router.post(
    "/events",
    response_model=PlaywrightEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a Playwright test event",
    description="Create a new Playwright test execution event for real-time tracking",
)
async def create_playwright_event(
    request: PlaywrightEventCreateRequest,
) -> PlaywrightEventResponse:
    """Create a new Playwright test event."""
    try:
        # Extract request context
        request_id, user_id = get_request_context()

        event_data = await PlaywrightService.create_event(
            suite_id=request.suite_id,
            test_external_id=request.test_external_id,
            event_type=request.event_type,
            timestamp=request.timestamp,
            data=request.data,
            request_id=request_id,
            user_id=user_id,
        )

        logger.info(
            "Playwright event created",
            event_id=str(event_data["id"]),
            suite_id=str(request.suite_id),
            event_type=request.event_type,
            test_external_id=request.test_external_id,
        )

        return PlaywrightEventResponse(**event_data)

    except PlaywrightValidationError as e:
        logger.warning("Playwright event creation validation error", error=str(e))
        error_detail = format_validation_error(str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error_detail
        ) from e

    except Exception as e:
        logger.error("Playwright event creation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while creating Playwright event",
        ) from e


@router.get(
    "/events",
    response_model=PlaywrightEventsListResponse,
    summary="Get Playwright test events",
    description="Retrieve Playwright test events with optional filtering",
)
async def get_playwright_events(
    suite_id: UUID = Query(..., description="Filter by suite ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
) -> PlaywrightEventsListResponse:
    """Get Playwright test events."""
    try:
        events_data = await PlaywrightService.get_events(
            suite_id=suite_id,
            limit=limit,
            offset=offset,
        )

        # Convert to response objects
        events = [PlaywrightEventResponse(**event) for event in events_data["events"]]

        logger.info(
            "Playwright events retrieved",
            suite_id=str(suite_id),
            count=len(events),
        )

        return PlaywrightEventsListResponse(
            total=events_data["total"],
            events=events,
        )

    except Exception as e:
        logger.error("Playwright events retrieval failed", suite_id=str(suite_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving Playwright events",
        ) from e
