"""
Environment service for managing test environment CRUD operations.
Provides business logic for environment management with proper error handling.
"""

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..api.models import EnvironmentCreateRequest, EnvironmentResponse, EnvironmentUpdateRequest
from ..lib.database import get_session
from ..models.test_environment import TestEnvironment

logger = structlog.get_logger()


class EnvironmentNotFoundError(Exception):
    """Environment not found error."""

    pass


class EnvironmentAlreadyExistsError(Exception):
    """Environment already exists error."""

    pass


class EnvironmentService:
    """Service for managing test environments."""

    @staticmethod
    def _convert_to_response(environment: TestEnvironment) -> EnvironmentResponse:
        """Convert database model to API response model."""
        return EnvironmentResponse(
            id=environment.id,
            name=environment.name,
            browser=environment.browser,
            os=environment.os,
            metadata=environment.config_metadata,
            created_at=environment.created_at,
            updated_at=environment.updated_at,
        )

    @staticmethod
    async def create_environment(request: EnvironmentCreateRequest) -> EnvironmentResponse:
        """Create a new test environment."""
        async with get_session() as session:
            # Check if environment with same name/browser/os already exists
            existing = await session.scalar(
                select(TestEnvironment).where(
                    TestEnvironment.name == request.name,
                    TestEnvironment.browser == request.browser,
                    TestEnvironment.os == request.os,
                )
            )

            if existing:
                logger.warning(
                    "Environment already exists",
                    name=request.name,
                    browser=request.browser,
                    os=request.os,
                )
                raise EnvironmentAlreadyExistsError(
                    f"Environment '{request.name}' with browser '{request.browser}' and OS '{request.os}' already exists"
                )

            # Create new environment - map API fields to database fields
            environment = TestEnvironment(
                name=request.name,
                browser=request.browser,
                os=request.os,
                config_metadata=request.metadata,
            )

            session.add(environment)

            try:
                await session.commit()
                await session.refresh(environment)

                logger.info(
                    "Environment created",
                    environment_id=str(environment.id),
                    name=environment.name,
                    browser=environment.browser,
                    os=environment.os,
                )

                return EnvironmentService._convert_to_response(environment)

            except IntegrityError as e:
                await session.rollback()
                logger.error("Environment creation failed", error=str(e))
                raise EnvironmentAlreadyExistsError(
                    f"Environment '{request.name}' with browser '{request.browser}' and OS '{request.os}' already exists"
                )

    @staticmethod
    async def get_environments() -> list[EnvironmentResponse]:
        """Get all test environments."""
        async with get_session() as session:
            result = await session.execute(
                select(TestEnvironment).order_by(TestEnvironment.created_at)
            )
            environments = result.scalars().all()

            logger.debug("Retrieved environments", count=len(environments))
            return [
                EnvironmentService._convert_to_response(environment) for environment in environments
            ]

    @staticmethod
    async def get_environment(environment_id: UUID) -> EnvironmentResponse:
        """Get a test environment by ID."""
        async with get_session() as session:
            environment = await session.get(TestEnvironment, environment_id)

            if not environment:
                logger.warning("Environment not found", environment_id=str(environment_id))
                raise EnvironmentNotFoundError(f"Environment with ID '{environment_id}' not found")

            logger.debug(
                "Retrieved environment", environment_id=str(environment_id), name=environment.name
            )
            return EnvironmentService._convert_to_response(environment)

    @staticmethod
    async def update_environment(
        environment_id: UUID, request: EnvironmentUpdateRequest
    ) -> EnvironmentResponse:
        """Update a test environment."""
        async with get_session() as session:
            environment = await session.get(TestEnvironment, environment_id)

            if not environment:
                logger.warning(
                    "Environment not found for update", environment_id=str(environment_id)
                )
                raise EnvironmentNotFoundError(f"Environment with ID '{environment_id}' not found")

            # Check if updating to a name/browser/os combination that already exists (but not this environment)
            if (
                environment.name != request.name
                or environment.browser != request.browser
                or environment.os != request.os
            ):
                existing = await session.scalar(
                    select(TestEnvironment).where(
                        TestEnvironment.name == request.name,
                        TestEnvironment.browser == request.browser,
                        TestEnvironment.os == request.os,
                        TestEnvironment.id != environment_id,
                    )
                )

                if existing:
                    logger.warning(
                        "Environment update conflict",
                        environment_id=str(environment_id),
                        name=request.name,
                        browser=request.browser,
                        os=request.os,
                    )
                    raise EnvironmentAlreadyExistsError(
                        f"Environment '{request.name}' with browser '{request.browser}' and OS '{request.os}' already exists"
                    )

            # Update environment fields
            environment.name = request.name
            environment.browser = request.browser
            environment.os = request.os
            environment.config_metadata = request.metadata

            try:
                await session.commit()
                await session.refresh(environment)

                logger.info(
                    "Environment updated",
                    environment_id=str(environment.id),
                    name=environment.name,
                    browser=environment.browser,
                    os=environment.os,
                )

                return EnvironmentService._convert_to_response(environment)

            except IntegrityError as e:
                await session.rollback()
                logger.error("Environment update failed", error=str(e))
                raise EnvironmentAlreadyExistsError(
                    f"Environment '{request.name}' with browser '{request.browser}' and OS '{request.os}' already exists"
                )

    @staticmethod
    async def delete_environment(environment_id: UUID) -> None:
        """Delete a test environment."""
        async with get_session() as session:
            environment = await session.get(TestEnvironment, environment_id)

            if not environment:
                logger.warning(
                    "Environment not found for deletion", environment_id=str(environment_id)
                )
                raise EnvironmentNotFoundError(f"Environment with ID '{environment_id}' not found")

            await session.delete(environment)
            await session.commit()

            logger.info(
                "Environment deleted",
                environment_id=str(environment_id),
                name=environment.name,
                browser=environment.browser,
                os=environment.os,
            )

    @staticmethod
    async def get_environments_by_filter(
        name: str | None = None, browser: str | None = None, os: str | None = None
    ) -> list[EnvironmentResponse]:
        """Get environments with optional filters."""
        async with get_session() as session:
            query = select(TestEnvironment)

            if name:
                query = query.where(TestEnvironment.name.ilike(f"%{name}%"))
            if browser:
                query = query.where(TestEnvironment.browser == browser)
            if os:
                query = query.where(TestEnvironment.os.ilike(f"%{os}%"))

            query = query.order_by(TestEnvironment.created_at)
            result = await session.execute(query)
            environments = result.scalars().all()

            logger.debug(
                "Retrieved filtered environments",
                count=len(environments),
                name=name,
                browser=browser,
                os=os,
            )
            return [
                EnvironmentService._convert_to_response(environment) for environment in environments
            ]
