"""
Framework API endpoints for test framework management.
Provides REST API for CRUD operations on test frameworks.
"""

from typing import List
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from ..lib.middleware import RequireFrameworksRead, RequireFrameworksWrite, RequireFrameworksDelete
from ..services.framework_service import (
    FrameworkService,
    FrameworkNotFoundError,
    FrameworkAlreadyExistsError,
)
from .models import FrameworkCreateRequest, FrameworkUpdateRequest, FrameworkResponse

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/frameworks", tags=["frameworks"])


@router.post(
    "",
    response_model=FrameworkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a test framework",
    description="Create a new test framework with name, version, and optional metadata",
    dependencies=[RequireFrameworksWrite]
)
async def create_framework(request: FrameworkCreateRequest) -> FrameworkResponse:
    """Create a new test framework."""
    try:
        framework = await FrameworkService.create_framework(request)
        logger.info(
            "Framework created via API",
            framework_id=str(framework.id),
            name=framework.name,
            version=framework.version
        )
        return framework

    except FrameworkAlreadyExistsError as e:
        logger.warning("Framework creation conflict", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )

    except Exception as e:
        logger.error("Framework creation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while creating framework"
        )


@router.get(
    "",
    response_model=List[FrameworkResponse],
    summary="Get all frameworks",
    description="Retrieve a list of all test frameworks",
    dependencies=[RequireFrameworksRead]
)
async def get_frameworks() -> List[FrameworkResponse]:
    """Get all test frameworks."""
    try:
        frameworks = await FrameworkService.get_frameworks()
        logger.debug("Frameworks retrieved via API", count=len(frameworks))
        return frameworks

    except Exception as e:
        logger.error("Framework retrieval failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving frameworks"
        )


@router.get(
    "/{framework_id}",
    response_model=FrameworkResponse,
    summary="Get a framework by ID",
    description="Retrieve a specific test framework by its UUID",
    dependencies=[RequireFrameworksRead]
)
async def get_framework(framework_id: UUID) -> FrameworkResponse:
    """Get a test framework by ID."""
    try:
        framework = await FrameworkService.get_framework(framework_id)
        logger.debug("Framework retrieved via API", framework_id=str(framework_id))
        return framework

    except FrameworkNotFoundError as e:
        logger.warning("Framework not found via API", framework_id=str(framework_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    except Exception as e:
        logger.error("Framework retrieval failed", framework_id=str(framework_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving framework"
        )


@router.put(
    "/{framework_id}",
    response_model=FrameworkResponse,
    summary="Update a framework",
    description="Update an existing test framework's details",
    dependencies=[RequireFrameworksWrite]
)
async def update_framework(framework_id: UUID, request: FrameworkUpdateRequest) -> FrameworkResponse:
    """Update a test framework."""
    try:
        framework = await FrameworkService.update_framework(framework_id, request)
        logger.info(
            "Framework updated via API",
            framework_id=str(framework_id),
            name=framework.name,
            version=framework.version
        )
        return framework

    except FrameworkNotFoundError as e:
        logger.warning("Framework not found for update via API", framework_id=str(framework_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    except FrameworkAlreadyExistsError as e:
        logger.warning("Framework update conflict", framework_id=str(framework_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )

    except Exception as e:
        logger.error("Framework update failed", framework_id=str(framework_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while updating framework"
        )


@router.delete(
    "/{framework_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a framework",
    description="Delete a test framework by its UUID",
    dependencies=[RequireFrameworksDelete]
)
async def delete_framework(framework_id: UUID) -> Response:
    """Delete a test framework."""
    try:
        await FrameworkService.delete_framework(framework_id)
        logger.info("Framework deleted via API", framework_id=str(framework_id))
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except FrameworkNotFoundError as e:
        logger.warning("Framework not found for deletion via API", framework_id=str(framework_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    except Exception as e:
        logger.error("Framework deletion failed", framework_id=str(framework_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while deleting framework"
        )