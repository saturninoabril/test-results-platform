"""
Suite API endpoints for test suite management.
Provides REST API for CRUD operations on test suites with relationships and statistics.
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from ..lib.middleware import RequireSuitesRead, RequireSuitesWrite, RequireSuitesDelete
from ..services.suite_service import (
    SuiteService,
    SuiteNotFoundError,
    SuiteValidationError,
)
from ..services.framework_service import FrameworkService
from ..services.environment_service import EnvironmentService
from ..services.notification_service import get_notification_service
from .models import SuiteCreateRequest, SuiteUpdateRequest, SuiteResponse

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/suites", tags=["suites"])


@router.post(
    "",
    response_model=SuiteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a test suite",
    description="Create a new test suite with framework/environment relationships and test counts",
    dependencies=[RequireSuitesWrite]
)
async def create_suite(request: SuiteCreateRequest) -> SuiteResponse:
    """Create a new test suite."""
    try:
        suite = await SuiteService.create_suite(request)
        logger.info(
            "Suite created via API",
            suite_id=str(suite.id),
            name=suite.name,
            framework_id=str(suite.framework_id),
            environment_id=str(suite.environment_id)
        )
        return suite

    except SuiteValidationError as e:
        logger.warning("Suite creation validation error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

    except Exception as e:
        logger.error("Suite creation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while creating suite"
        )


@router.get(
    "",
    response_model=List[SuiteResponse],
    summary="Get suites",
    description="Retrieve test suites with optional filtering by framework, environment, date ranges",
    dependencies=[RequireSuitesRead]
)
async def get_suites(
    framework_id: Optional[UUID] = Query(None, description="Filter by framework ID"),
    environment_id: Optional[UUID] = Query(None, description="Filter by environment ID"),
    name: Optional[str] = Query(None, description="Filter by suite name (partial match)"),
    start_date: Optional[datetime] = Query(None, description="Filter by creation date start"),
    end_date: Optional[datetime] = Query(None, description="Filter by creation date end"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip")
) -> List[SuiteResponse]:
    """Get test suites with optional filtering."""
    try:
        if framework_id or environment_id or name or start_date or end_date:
            suites = await SuiteService.get_suites_by_filter(
                framework_id=framework_id,
                environment_id=environment_id,
                name=name,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                offset=offset
            )
            logger.debug(
                "Filtered suites retrieved via API",
                count=len(suites),
                framework_id=str(framework_id) if framework_id else None,
                environment_id=str(environment_id) if environment_id else None
            )
        else:
            suites = await SuiteService.get_suites()
            # Apply limit/offset to unfiltered results
            suites = suites[offset:offset + limit]
            logger.debug("All suites retrieved via API", count=len(suites))

        return suites

    except Exception as e:
        logger.error("Suite retrieval failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving suites"
        )


@router.get(
    "/statistics",
    summary="Get suite statistics",
    description="Get aggregated statistics for test suites with optional filtering",
    dependencies=[RequireSuitesRead]
)
async def get_suite_statistics(
    framework_id: Optional[UUID] = Query(None, description="Filter by framework ID"),
    environment_id: Optional[UUID] = Query(None, description="Filter by environment ID"),
    start_date: Optional[datetime] = Query(None, description="Filter by creation date start"),
    end_date: Optional[datetime] = Query(None, description="Filter by creation date end")
) -> dict:
    """Get aggregated suite statistics."""
    try:
        statistics = await SuiteService.get_suite_statistics(
            framework_id=framework_id,
            environment_id=environment_id,
            start_date=start_date,
            end_date=end_date
        )
        logger.debug("Suite statistics retrieved via API")
        return statistics

    except Exception as e:
        logger.error("Suite statistics retrieval failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving statistics"
        )


@router.get(
    "/{suite_id}",
    response_model=SuiteResponse,
    summary="Get a suite by ID",
    description="Retrieve a specific test suite by its UUID",
    dependencies=[RequireSuitesRead]
)
async def get_suite(suite_id: UUID) -> SuiteResponse:
    """Get a test suite by ID."""
    try:
        suite = await SuiteService.get_suite(suite_id)
        logger.debug("Suite retrieved via API", suite_id=str(suite_id))
        return suite

    except SuiteNotFoundError as e:
        logger.warning("Suite not found via API", suite_id=str(suite_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    except Exception as e:
        logger.error("Suite retrieval failed", suite_id=str(suite_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving suite"
        )


@router.put(
    "/{suite_id}",
    response_model=SuiteResponse,
    summary="Update a suite",
    description="Update an existing test suite's details",
    dependencies=[RequireSuitesWrite]
)
async def update_suite(suite_id: UUID, request: SuiteUpdateRequest) -> SuiteResponse:
    """Update a test suite."""
    try:
        # Get the original suite to check status changes
        original_suite = await SuiteService.get_suite(suite_id)

        suite = await SuiteService.update_suite(suite_id, request)
        logger.info(
            "Suite updated via API",
            suite_id=str(suite_id),
            name=suite.name
        )

        # Send notification when suite is completed
        if (original_suite.status != "completed" and
            suite.status == "completed" and
            suite.started_at is not None):
            try:
                notification_service = get_notification_service()
                framework = await FrameworkService.get_framework(suite.framework_id)
                environment = await EnvironmentService.get_environment(suite.environment_id)

                await notification_service.notify_suite_completion(
                    suite=suite,
                    framework_name=framework.name,
                    environment_name=environment.name
                )
                logger.debug("Suite completion notification sent", suite_id=str(suite_id))

                # Also check for high failure rate
                if suite.total_tests > 0:
                    failure_rate = suite.failed_tests / suite.total_tests
                    if failure_rate >= 0.3:  # 30% failure threshold
                        # Get recent failed tests for notification
                        from ..services.result_service import ResultService
                        failed_results = await ResultService.get_results_by_filter(
                            suite_id=suite_id,
                            status="failed",
                            limit=10
                        )

                        await notification_service.notify_high_failure_rate(
                            suite=suite,
                            framework_name=framework.name,
                            environment_name=environment.name,
                            failed_tests=failed_results
                        )
                        logger.debug("High failure rate notification sent", suite_id=str(suite_id))

            except Exception as notify_error:
                logger.warning("Failed to send suite completion notification", error=str(notify_error))

        return suite

    except SuiteNotFoundError as e:
        logger.warning("Suite not found for update via API", suite_id=str(suite_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    except SuiteValidationError as e:
        logger.warning("Suite update validation error", suite_id=str(suite_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

    except Exception as e:
        logger.error("Suite update failed", suite_id=str(suite_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while updating suite"
        )


@router.delete(
    "/{suite_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a suite",
    description="Delete a test suite by its UUID",
    dependencies=[RequireSuitesDelete]
)
async def delete_suite(suite_id: UUID) -> Response:
    """Delete a test suite."""
    try:
        await SuiteService.delete_suite(suite_id)
        logger.info("Suite deleted via API", suite_id=str(suite_id))
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except SuiteNotFoundError as e:
        logger.warning("Suite not found for deletion via API", suite_id=str(suite_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    except Exception as e:
        logger.error("Suite deletion failed", suite_id=str(suite_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while deleting suite"
        )