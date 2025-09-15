"""
Suite service for managing test suite CRUD operations.
Provides business logic for suite management with relationships and statistics.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError

from ..api.models import SuiteCreateRequest, SuiteResponse, SuiteUpdateRequest
from ..lib.database import get_session
from ..models.test_environment import TestEnvironment
from ..models.test_framework import TestFramework
from ..models.test_suite import TestSuite

logger = structlog.get_logger()


class SuiteNotFoundError(Exception):
    """Suite not found error."""

    pass


class SuiteValidationError(Exception):
    """Suite validation error."""

    pass


class SuiteService:
    """Service for managing test suites."""

    @staticmethod
    def _convert_to_response(suite: TestSuite) -> SuiteResponse:
        """Convert database model to API response model."""
        return SuiteResponse(
            id=suite.id,
            framework_id=suite.framework_id,
            environment_id=suite.environment_id,
            name=suite.name,
            total_count=suite.total_tests,
            passed_count=suite.passed_tests,
            failed_count=suite.failed_tests,
            skipped_count=suite.skipped_tests,
            duration_ms=suite.duration_ms,
            metadata=suite.config_metadata,
            created_at=suite.created_at,
            updated_at=suite.updated_at,
        )

    @staticmethod
    async def create_suite(request: SuiteCreateRequest) -> SuiteResponse:
        """Create a new test suite."""
        async with get_session() as session:
            # Validate framework and environment exist
            framework = await session.get(TestFramework, request.framework_id)
            if not framework:
                raise SuiteValidationError(f"Framework with ID '{request.framework_id}' not found")

            environment = await session.get(TestEnvironment, request.environment_id)
            if not environment:
                raise SuiteValidationError(
                    f"Environment with ID '{request.environment_id}' not found"
                )

            # Create new suite - map API fields to database fields
            from datetime import datetime

            now = datetime.now(UTC)

            suite = TestSuite(
                framework_id=request.framework_id,
                environment_id=request.environment_id,
                name=request.name,
                total_tests=request.total_count,
                passed_tests=request.passed_count,
                failed_tests=request.failed_count,
                skipped_tests=request.skipped_count,
                duration_ms=request.duration_ms or 0,
                started_at=now,
                completed_at=now,
                config_metadata=request.metadata,
            )

            session.add(suite)

            try:
                await session.commit()
                await session.refresh(suite)

                logger.info(
                    "Suite created",
                    suite_id=str(suite.id),
                    name=suite.name,
                    framework_id=str(suite.framework_id),
                    environment_id=str(suite.environment_id),
                    total_tests=suite.total_tests,
                )

                return SuiteService._convert_to_response(suite)

            except IntegrityError as e:
                await session.rollback()
                logger.error("Suite creation failed", error=str(e))
                raise SuiteValidationError(f"Suite creation failed: {str(e)}") from e

    @staticmethod
    async def get_suites() -> list[SuiteResponse]:
        """Get all test suites."""
        async with get_session() as session:
            result = await session.execute(select(TestSuite).order_by(TestSuite.created_at.desc()))
            suites = result.scalars().all()

            logger.debug("Retrieved suites", count=len(suites))
            return [SuiteService._convert_to_response(suite) for suite in suites]

    @staticmethod
    async def get_suite(suite_id: UUID) -> SuiteResponse:
        """Get a test suite by ID."""
        async with get_session() as session:
            suite = await session.get(TestSuite, suite_id)

            if not suite:
                logger.warning("Suite not found", suite_id=str(suite_id))
                raise SuiteNotFoundError(f"Suite with ID '{suite_id}' not found")

            logger.debug("Retrieved suite", suite_id=str(suite_id), name=suite.name)
            return SuiteService._convert_to_response(suite)

    @staticmethod
    async def update_suite(suite_id: UUID, request: SuiteUpdateRequest) -> SuiteResponse:
        """Update a test suite."""
        async with get_session() as session:
            suite = await session.get(TestSuite, suite_id)

            if not suite:
                logger.warning("Suite not found for update", suite_id=str(suite_id))
                raise SuiteNotFoundError(f"Suite with ID '{suite_id}' not found")

            # Validate framework and environment exist if they're changing
            if suite.framework_id != request.framework_id:
                framework = await session.get(TestFramework, request.framework_id)
                if not framework:
                    raise SuiteValidationError(
                        f"Framework with ID '{request.framework_id}' not found"
                    )

            if suite.environment_id != request.environment_id:
                environment = await session.get(TestEnvironment, request.environment_id)
                if not environment:
                    raise SuiteValidationError(
                        f"Environment with ID '{request.environment_id}' not found"
                    )

            # Update suite fields - map API fields to database fields
            suite.framework_id = request.framework_id
            suite.environment_id = request.environment_id
            suite.name = request.name
            suite.total_tests = request.total_count
            suite.passed_tests = request.passed_count
            suite.failed_tests = request.failed_count
            suite.skipped_tests = request.skipped_count
            suite.duration_ms = request.duration_ms or 0
            suite.config_metadata = request.metadata

            try:
                await session.commit()
                await session.refresh(suite)

                logger.info(
                    "Suite updated",
                    suite_id=str(suite.id),
                    name=suite.name,
                    total_count=suite.total_tests,
                )

                return SuiteService._convert_to_response(suite)

            except IntegrityError as e:
                await session.rollback()
                logger.error("Suite update failed", error=str(e))
                raise SuiteValidationError(f"Suite update failed: {str(e)}") from e

    @staticmethod
    async def delete_suite(suite_id: UUID) -> None:
        """Delete a test suite."""
        async with get_session() as session:
            suite = await session.get(TestSuite, suite_id)

            if not suite:
                logger.warning("Suite not found for deletion", suite_id=str(suite_id))
                raise SuiteNotFoundError(f"Suite with ID '{suite_id}' not found")

            await session.delete(suite)
            await session.commit()

            logger.info("Suite deleted", suite_id=str(suite_id), name=suite.name)

    @staticmethod
    async def get_suites_by_filter(
        framework_id: UUID | None = None,
        environment_id: UUID | None = None,
        name: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SuiteResponse]:
        """Get suites with filtering and pagination."""
        async with get_session() as session:
            query = select(TestSuite)

            # Apply filters
            conditions = []
            if framework_id:
                conditions.append(TestSuite.framework_id == framework_id)
            if environment_id:
                conditions.append(TestSuite.environment_id == environment_id)
            if name:
                conditions.append(TestSuite.name.ilike(f"%{name}%"))
            if start_date:
                conditions.append(TestSuite.created_at >= start_date)
            if end_date:
                conditions.append(TestSuite.created_at <= end_date)

            if conditions:
                query = query.where(and_(*conditions))

            # Apply ordering, limit and offset
            query = query.order_by(TestSuite.created_at.desc())
            query = query.offset(offset).limit(limit)

            result = await session.execute(query)
            suites = result.scalars().all()

            logger.debug(
                "Retrieved filtered suites",
                count=len(suites),
                framework_id=str(framework_id) if framework_id else None,
                environment_id=str(environment_id) if environment_id else None,
                name=name,
            )
            return [SuiteService._convert_to_response(suite) for suite in suites]

    @staticmethod
    async def get_suite_statistics(
        framework_id: UUID | None = None,
        environment_id: UUID | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        """Get aggregated suite statistics."""
        async with get_session() as session:
            query = select(TestSuite)

            # Apply filters
            conditions = []
            if framework_id:
                conditions.append(TestSuite.framework_id == framework_id)
            if environment_id:
                conditions.append(TestSuite.environment_id == environment_id)
            if start_date:
                conditions.append(TestSuite.created_at >= start_date)
            if end_date:
                conditions.append(TestSuite.created_at <= end_date)

            if conditions:
                query = query.where(and_(*conditions))

            result = await session.execute(query)
            suites = result.scalars().all()

            # Calculate statistics
            total_suites = len(suites)
            total_tests = sum(suite.total_tests for suite in suites)
            total_passed = sum(suite.passed_tests for suite in suites)
            total_failed = sum(suite.failed_tests for suite in suites)
            total_skipped = sum(suite.skipped_tests for suite in suites)
            total_duration = sum(suite.duration_ms or 0 for suite in suites)

            pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

            statistics = {
                "total_suites": total_suites,
                "total_tests": total_tests,
                "total_passed": total_passed,
                "total_failed": total_failed,
                "total_skipped": total_skipped,
                "pass_rate_percent": round(pass_rate, 2),
                "total_duration_ms": total_duration,
                "avg_duration_ms": round(total_duration / total_suites) if total_suites > 0 else 0,
            }

            logger.debug("Calculated suite statistics", **statistics)
            return statistics
