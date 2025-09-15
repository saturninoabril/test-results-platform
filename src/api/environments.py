"""
Environment API endpoints for test environment management.
Provides REST API for CRUD operations on test environments.
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response

from ..lib.middleware import (
    RequireEnvironmentsDelete,
    RequireEnvironmentsRead,
    RequireEnvironmentsWrite,
)
from ..services.environment_service import (
    EnvironmentAlreadyExistsError,
    EnvironmentNotFoundError,
    EnvironmentService,
)
from .models import EnvironmentCreateRequest, EnvironmentResponse, EnvironmentUpdateRequest

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/environments", tags=["environments"])


@router.post(
    "",
    response_model=EnvironmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a test environment",
    description="Create a new test environment with name, browser, OS, and optional metadata",
    dependencies=[RequireEnvironmentsWrite],
)
async def create_environment(request: EnvironmentCreateRequest) -> EnvironmentResponse:
    """Create a new test environment."""
    try:
        environment = await EnvironmentService.create_environment(request)
        logger.info(
            "Environment created via API",
            environment_id=str(environment.id),
            name=environment.name,
            browser=environment.browser,
            os=environment.os,
        )
        return environment

    except EnvironmentAlreadyExistsError as e:
        logger.warning("Environment creation conflict", error=str(e))
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    except Exception as e:
        logger.error("Environment creation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while creating environment",
        ) from e


@router.get(
    "",
    response_model=list[EnvironmentResponse],
    summary="Get environments",
    description="Retrieve a list of test environments with optional filtering",
    dependencies=[RequireEnvironmentsRead],
)
async def get_environments(
    name: str | None = Query(None, description="Filter by environment name (partial match)"),
    browser: str | None = Query(None, description="Filter by browser"),
    os: str | None = Query(None, description="Filter by OS (partial match)"),
) -> list[EnvironmentResponse]:
    """Get test environments with optional filtering."""
    try:
        if name or browser or os:
            environments = await EnvironmentService.get_environments_by_filter(
                name=name, browser=browser, os=os
            )
            logger.debug(
                "Filtered environments retrieved via API",
                count=len(environments),
                name=name,
                browser=browser,
                os=os,
            )
        else:
            environments = await EnvironmentService.get_environments()
            logger.debug("All environments retrieved via API", count=len(environments))

        return environments

    except Exception as e:
        logger.error("Environment retrieval failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving environments",
        ) from e


@router.get(
    "/{environment_id}",
    response_model=EnvironmentResponse,
    summary="Get an environment by ID",
    description="Retrieve a specific test environment by its UUID",
    dependencies=[RequireEnvironmentsRead],
)
async def get_environment(environment_id: UUID) -> EnvironmentResponse:
    """Get a test environment by ID."""
    try:
        environment = await EnvironmentService.get_environment(environment_id)
        logger.debug("Environment retrieved via API", environment_id=str(environment_id))
        return environment

    except EnvironmentNotFoundError as e:
        logger.warning("Environment not found via API", environment_id=str(environment_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except Exception as e:
        logger.error(
            "Environment retrieval failed", environment_id=str(environment_id), error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving environment",
        ) from e


@router.put(
    "/{environment_id}",
    response_model=EnvironmentResponse,
    summary="Update an environment",
    description="Update an existing test environment's details",
    dependencies=[RequireEnvironmentsWrite],
)
async def update_environment(
    environment_id: UUID, request: EnvironmentUpdateRequest
) -> EnvironmentResponse:
    """Update a test environment."""
    try:
        environment = await EnvironmentService.update_environment(environment_id, request)
        logger.info(
            "Environment updated via API",
            environment_id=str(environment_id),
            name=environment.name,
            browser=environment.browser,
            os=environment.os,
        )
        return environment

    except EnvironmentNotFoundError as e:
        logger.warning(
            "Environment not found for update via API", environment_id=str(environment_id)
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except EnvironmentAlreadyExistsError as e:
        logger.warning(
            "Environment update conflict", environment_id=str(environment_id), error=str(e)
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    except Exception as e:
        logger.error("Environment update failed", environment_id=str(environment_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while updating environment",
        ) from e


@router.delete(
    "/{environment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an environment",
    description="Delete a test environment by its UUID",
    dependencies=[RequireEnvironmentsDelete],
)
async def delete_environment(environment_id: UUID) -> Response:
    """Delete a test environment."""
    try:
        await EnvironmentService.delete_environment(environment_id)
        logger.info("Environment deleted via API", environment_id=str(environment_id))
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except EnvironmentNotFoundError as e:
        logger.warning(
            "Environment not found for deletion via API", environment_id=str(environment_id)
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except Exception as e:
        logger.error(
            "Environment deletion failed", environment_id=str(environment_id), error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while deleting environment",
        ) from e
