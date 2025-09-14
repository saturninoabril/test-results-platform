"""
Result API endpoints for test result management.
Provides REST API for CRUD operations on test results with bulk operations and filtering.
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response

from ..lib.middleware import RequireResultsDelete, RequireResultsRead, RequireResultsWrite
from ..services.environment_service import EnvironmentService
from ..services.framework_service import FrameworkService
from ..services.notification_service import get_notification_service
from ..services.result_service import (
    ResultNotFoundError,
    ResultService,
    ResultValidationError,
)
from ..services.suite_service import SuiteService
from .models import ResultCreateRequest, ResultResponse, ResultUpdateRequest

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/results", tags=["results"])


@router.post(
    "",
    response_model=ResultResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a test result",
    description="Create a new test result with status, duration, and metadata",
    dependencies=[RequireResultsWrite],
)
async def create_result(request: ResultCreateRequest) -> ResultResponse:
    """Create a new test result."""
    try:
        result = await ResultService.create_result(request)
        logger.info(
            "Result created via API",
            result_id=str(result.id),
            name=result.name,
            status=result.status,
        )

        # Send notification for test failures
        if result.status == "failed":
            try:
                from ..lib.database import get_session
                from ..models.test_result import TestResult
                from ..models.test_suite import TestSuite

                notification_service = get_notification_service()

                # Fetch actual database models for notification
                async with get_session() as session:
                    # Get the actual TestResult model
                    test_result_model = await session.get(TestResult, result.id)
                    if test_result_model:
                        # Get related suite and framework/environment info
                        suite_response = await SuiteService.get_suite(result.suite_id)
                        framework_response = await FrameworkService.get_framework(suite_response.framework_id)
                        environment_response = await EnvironmentService.get_environment(suite_response.environment_id)

                        # Get the actual TestSuite model
                        test_suite_model = await session.get(TestSuite, result.suite_id)
                        if test_suite_model:
                            await notification_service.notify_test_failure(
                                test_result=test_result_model,
                                suite=test_suite_model,
                                framework_name=framework_response.name,
                                environment_name=environment_response.name,
                            )
                            logger.debug("Test failure notification sent", result_id=str(result.id))
            except Exception as notify_error:
                logger.warning("Failed to send test failure notification", error=str(notify_error))

        return result

    except ResultValidationError as e:
        logger.warning("Result creation validation error", error=str(e))
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    except Exception as e:
        logger.error("Result creation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while creating result",
        )


@router.post(
    "/bulk",
    response_model=list[ResultResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create multiple test results",
    description="Create multiple test results in a single batch operation",
    dependencies=[RequireResultsWrite],
)
async def create_results_bulk(requests: list[ResultCreateRequest]) -> list[ResultResponse]:
    """Create multiple test results in bulk."""
    try:
        results = await ResultService.create_results_bulk(requests)
        logger.info("Bulk results created via API", count=len(results))

        # Send notifications for failed tests and bulk analysis
        failed_results = [r for r in results if r.status == "failed"]
        if failed_results:
            try:
                from ..lib.database import get_session
                from ..models.test_result import TestResult
                from ..models.test_suite import TestSuite

                notification_service = get_notification_service()

                # Group failures by suite for proper notification context
                suite_failures: dict[UUID, list[ResultResponse]] = {}
                for result in failed_results:
                    if result.suite_id not in suite_failures:
                        suite_failures[result.suite_id] = []
                    suite_failures[result.suite_id].append(result)

                # Send notifications per suite
                async with get_session() as session:
                    for suite_id, suite_failed_results in suite_failures.items():
                        suite_response = await SuiteService.get_suite(suite_id)
                        framework_response = await FrameworkService.get_framework(suite_response.framework_id)
                        environment_response = await EnvironmentService.get_environment(suite_response.environment_id)

                        # Get actual database models
                        test_suite_model = await session.get(TestSuite, suite_id)
                        if test_suite_model:
                            # Send bulk failure analysis for multiple failures in same suite
                            if len(suite_failed_results) > 1:
                                # Convert to TestResult models for bulk analysis
                                test_result_models = []
                                for result_response in suite_failed_results:
                                    test_result_model = await session.get(TestResult, result_response.id)
                                    if test_result_model:
                                        test_result_models.append(test_result_model)

                                if test_result_models:
                                    await notification_service.notify_bulk_failure_analysis(
                                        failed_results=test_result_models,
                                        suite_name=suite_response.name,
                                        framework_name=framework_response.name,
                                        environment_name=environment_response.name,
                                    )
                            else:
                                # Single failure notification
                                test_result_model = await session.get(TestResult, suite_failed_results[0].id)
                                if test_result_model:
                                    await notification_service.notify_test_failure(
                                        test_result=test_result_model,
                                        suite=test_suite_model,
                                        framework_name=framework_response.name,
                                        environment_name=environment_response.name,
                                    )

                logger.debug("Bulk failure notifications sent", failed_count=len(failed_results))
            except Exception as notify_error:
                logger.warning("Failed to send bulk failure notifications", error=str(notify_error))

        return results

    except ResultValidationError as e:
        logger.warning("Bulk result creation validation error", error=str(e))
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    except Exception as e:
        logger.error("Bulk result creation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while creating bulk results",
        )


@router.get(
    "",
    response_model=list[ResultResponse],
    summary="Get results",
    description="Retrieve test results with optional filtering by status, tags, test names",
    dependencies=[RequireResultsRead],
)
async def get_results(
    suite_id: UUID | None = Query(None, description="Filter by suite ID"),
    status: str | None = Query(None, description="Filter by result status"),
    name: str | None = Query(None, description="Filter by test name (partial match)"),
    tags: str | None = Query(None, description="Filter by tags (comma-separated)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
) -> list[ResultResponse]:
    """Get test results with optional filtering."""
    try:
        # Parse comma-separated tags
        tag_list = None
        if tags:
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

        if suite_id or status or name or tag_list:
            results = await ResultService.get_results_by_filter(
                suite_id=suite_id,
                status=status,
                name=name,
                tags=tag_list,
                limit=limit,
                offset=offset,
            )
            logger.debug("Filtered results retrieved via API", count=len(results))
        else:
            results = await ResultService.get_results()
            # Apply limit/offset to unfiltered results
            results = results[offset : offset + limit]
            logger.debug("All results retrieved via API", count=len(results))

        return results

    except Exception as e:
        logger.error("Result retrieval failed", error=str(e))
        raise HTTPException(
            status_code=500,  # HTTP_500_INTERNAL_SERVER_ERROR
            detail="Internal server error occurred while retrieving results",
        )


@router.get(
    "/{result_id}",
    response_model=ResultResponse,
    summary="Get a result by ID",
    description="Retrieve a specific test result by its UUID",
    dependencies=[RequireResultsRead],
)
async def get_result(result_id: UUID) -> ResultResponse:
    """Get a test result by ID."""
    try:
        result = await ResultService.get_result(result_id)
        logger.debug("Result retrieved via API", result_id=str(result_id))
        return result

    except ResultNotFoundError as e:
        logger.warning("Result not found via API", result_id=str(result_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    except Exception as e:
        logger.error("Result retrieval failed", result_id=str(result_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving result",
        )


@router.put(
    "/{result_id}",
    response_model=ResultResponse,
    summary="Update a result",
    description="Update an existing test result's details",
    dependencies=[RequireResultsWrite],
)
async def update_result(result_id: UUID, request: ResultUpdateRequest) -> ResultResponse:
    """Update a test result."""
    try:
        result = await ResultService.update_result(result_id, request)
        logger.info(
            "Result updated via API",
            result_id=str(result_id),
            name=result.name,
            status=result.status,
        )
        return result

    except ResultNotFoundError as e:
        logger.warning("Result not found for update via API", result_id=str(result_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    except ResultValidationError as e:
        logger.warning("Result update validation error", result_id=str(result_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    except Exception as e:
        logger.error("Result update failed", result_id=str(result_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while updating result",
        )


@router.delete(
    "/{result_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a result",
    description="Delete a test result by its UUID",
    dependencies=[RequireResultsDelete],
)
async def delete_result(result_id: UUID) -> Response:
    """Delete a test result."""
    try:
        await ResultService.delete_result(result_id)
        logger.info("Result deleted via API", result_id=str(result_id))
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except ResultNotFoundError as e:
        logger.warning("Result not found for deletion via API", result_id=str(result_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    except Exception as e:
        logger.error("Result deletion failed", result_id=str(result_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while deleting result",
        )
