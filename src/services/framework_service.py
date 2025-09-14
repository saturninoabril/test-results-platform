"""
Framework service for managing test framework CRUD operations.
Provides business logic for framework management with proper error handling.
"""

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..api.models import FrameworkCreateRequest, FrameworkResponse, FrameworkUpdateRequest
from ..lib.database import get_session
from ..models.test_framework import TestFramework

logger = structlog.get_logger()


class FrameworkNotFoundError(Exception):
    """Framework not found error."""

    pass


class FrameworkAlreadyExistsError(Exception):
    """Framework already exists error."""

    pass


class FrameworkService:
    """Service for managing test frameworks."""

    @staticmethod
    def _convert_to_response(framework: TestFramework) -> FrameworkResponse:
        """Convert database model to API response model."""
        return FrameworkResponse(
            id=framework.id,
            name=framework.name,
            version=framework.version,
            metadata=framework.config_metadata,
            created_at=framework.created_at,
            updated_at=framework.updated_at,
        )

    @staticmethod
    async def create_framework(request: FrameworkCreateRequest) -> FrameworkResponse:
        """Create a new test framework."""
        async with get_session() as session:
            # Check if framework with same name/version already exists
            existing = await session.scalar(
                select(TestFramework).where(
                    TestFramework.name == request.name, TestFramework.version == request.version
                )
            )

            if existing:
                logger.warning(
                    "Framework already exists", name=request.name, version=request.version
                )
                raise FrameworkAlreadyExistsError(
                    f"Framework '{request.name}' version '{request.version}' already exists"
                )

            # Create new framework - map API fields to database fields
            framework = TestFramework(
                name=request.name, version=request.version, config_metadata=request.metadata
            )

            session.add(framework)

            try:
                await session.commit()
                await session.refresh(framework)

                logger.info(
                    "Framework created",
                    framework_id=str(framework.id),
                    name=framework.name,
                    version=framework.version,
                )

                return FrameworkService._convert_to_response(framework)

            except IntegrityError as e:
                await session.rollback()
                logger.error("Framework creation failed", error=str(e))
                raise FrameworkAlreadyExistsError(
                    f"Framework '{request.name}' version '{request.version}' already exists"
                )

    @staticmethod
    async def get_frameworks() -> list[FrameworkResponse]:
        """Get all test frameworks."""
        async with get_session() as session:
            result = await session.execute(select(TestFramework).order_by(TestFramework.created_at))
            frameworks = result.scalars().all()

            logger.debug("Retrieved frameworks", count=len(frameworks))
            return [FrameworkService._convert_to_response(framework) for framework in frameworks]

    @staticmethod
    async def get_framework(framework_id: UUID) -> FrameworkResponse:
        """Get a test framework by ID."""
        async with get_session() as session:
            framework = await session.get(TestFramework, framework_id)

            if not framework:
                logger.warning("Framework not found", framework_id=str(framework_id))
                raise FrameworkNotFoundError(f"Framework with ID '{framework_id}' not found")

            logger.debug("Retrieved framework", framework_id=str(framework_id), name=framework.name)
            return FrameworkService._convert_to_response(framework)

    @staticmethod
    async def update_framework(
        framework_id: UUID, request: FrameworkUpdateRequest
    ) -> FrameworkResponse:
        """Update a test framework."""
        async with get_session() as session:
            framework = await session.get(TestFramework, framework_id)

            if not framework:
                logger.warning("Framework not found for update", framework_id=str(framework_id))
                raise FrameworkNotFoundError(f"Framework with ID '{framework_id}' not found")

            # Check if updating to a name/version that already exists (but not this framework)
            if framework.name != request.name or framework.version != request.version:
                existing = await session.scalar(
                    select(TestFramework).where(
                        TestFramework.name == request.name,
                        TestFramework.version == request.version,
                        TestFramework.id != framework_id,
                    )
                )

                if existing:
                    logger.warning(
                        "Framework update conflict",
                        framework_id=str(framework_id),
                        name=request.name,
                        version=request.version,
                    )
                    raise FrameworkAlreadyExistsError(
                        f"Framework '{request.name}' version '{request.version}' already exists"
                    )

            # Update framework fields
            framework.name = request.name
            framework.version = request.version
            framework.config_metadata = request.metadata

            try:
                await session.commit()
                await session.refresh(framework)

                logger.info(
                    "Framework updated",
                    framework_id=str(framework.id),
                    name=framework.name,
                    version=framework.version,
                )

                return FrameworkService._convert_to_response(framework)

            except IntegrityError as e:
                await session.rollback()
                logger.error("Framework update failed", error=str(e))
                raise FrameworkAlreadyExistsError(
                    f"Framework '{request.name}' version '{request.version}' already exists"
                )

    @staticmethod
    async def delete_framework(framework_id: UUID) -> None:
        """Delete a test framework."""
        async with get_session() as session:
            framework = await session.get(TestFramework, framework_id)

            if not framework:
                logger.warning("Framework not found for deletion", framework_id=str(framework_id))
                raise FrameworkNotFoundError(f"Framework with ID '{framework_id}' not found")

            await session.delete(framework)
            await session.commit()

            logger.info(
                "Framework deleted",
                framework_id=str(framework_id),
                name=framework.name,
                version=framework.version,
            )

    @staticmethod
    async def get_framework_by_name_version(name: str, version: str) -> FrameworkResponse | None:
        """Get a framework by name and version."""
        async with get_session() as session:
            framework = await session.scalar(
                select(TestFramework).where(
                    TestFramework.name == name, TestFramework.version == version
                )
            )

            if framework:
                logger.debug(
                    "Retrieved framework by name/version",
                    name=name,
                    version=version,
                    framework_id=str(framework.id),
                )
                return FrameworkService._convert_to_response(framework)

            return None
