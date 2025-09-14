"""
Result service for managing test result CRUD operations.
Provides business logic for individual test result management with bulk operations.
"""

from typing import List, Optional
from uuid import UUID

import structlog
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from ..lib.database import get_session
from ..models.test_result import TestResult
from ..models.test_suite import TestSuite
from ..api.models import ResultCreateRequest, ResultUpdateRequest, ResultResponse

logger = structlog.get_logger()


class ResultNotFoundError(Exception):
    """Result not found error."""
    pass


class ResultValidationError(Exception):
    """Result validation error."""
    pass


class ResultService:
    """Service for managing test results."""

    @staticmethod
    def _convert_to_response(result: TestResult) -> ResultResponse:
        """Convert database model to API response model."""
        return ResultResponse(
            id=result.id,
            suite_id=result.suite_id,
            name=result.test_name,
            status=result.status,
            duration_ms=result.duration_ms,
            error_message=result.error_message,
            tags=result.tags,
            external_id=result.external_id,
            full_title=result.full_title,
            metadata=result.config_metadata,
            created_at=result.created_at,
            updated_at=result.updated_at
        )

    @staticmethod
    async def create_result(request: ResultCreateRequest) -> ResultResponse:
        """Create a new test result."""
        async with get_session() as session:
            # Validate suite exists
            suite = await session.get(TestSuite, request.suite_id)
            if not suite:
                raise ResultValidationError(f"Suite with ID '{request.suite_id}' not found")

            # Create new result - map API fields to database fields
            result = TestResult(
                suite_id=request.suite_id,
                test_name=request.name,
                status=request.status,
                duration_ms=request.duration_ms,
                error_message=request.error_message,
                tags=request.tags,
                external_id=request.external_id,
                full_title=request.full_title,
                config_metadata=request.metadata
            )

            session.add(result)

            try:
                await session.commit()
                await session.refresh(result)

                logger.info(
                    "Result created",
                    result_id=str(result.id),
                    name=result.test_name,
                    status=result.status,
                    suite_id=str(result.suite_id)
                )

                return ResultService._convert_to_response(result)

            except IntegrityError as e:
                await session.rollback()
                logger.error("Result creation failed", error=str(e))
                raise ResultValidationError(f"Result creation failed: {str(e)}")

    @staticmethod
    async def create_results_bulk(requests: List[ResultCreateRequest]) -> List[ResultResponse]:
        """Create multiple test results in bulk."""
        async with get_session() as session:
            # Validate all suite IDs exist
            suite_ids = {request.suite_id for request in requests}
            suite_query = select(TestSuite.id).where(TestSuite.id.in_(suite_ids))
            existing_suite_ids = set((await session.execute(suite_query)).scalars().all())

            invalid_suite_ids = suite_ids - existing_suite_ids
            if invalid_suite_ids:
                raise ResultValidationError(
                    f"Suites not found: {', '.join(str(id) for id in invalid_suite_ids)}"
                )

            # Create results
            results = []
            for request in requests:
                result = TestResult(
                    suite_id=request.suite_id,
                    test_name=request.name,
                    status=request.status,
                    duration_ms=request.duration_ms,
                    error_message=request.error_message,
                    tags=request.tags,
                    external_id=request.external_id,
                    full_title=request.full_title,
                    config_metadata=request.metadata
                )
                results.append(result)
                session.add(result)

            try:
                await session.commit()

                # Refresh all results
                for result in results:
                    await session.refresh(result)

                logger.info("Bulk results created", count=len(results))
                return [ResultService._convert_to_response(result) for result in results]

            except IntegrityError as e:
                await session.rollback()
                logger.error("Bulk result creation failed", error=str(e))
                raise ResultValidationError(f"Bulk result creation failed: {str(e)}")

    @staticmethod
    async def get_results() -> List[ResultResponse]:
        """Get all test results."""
        async with get_session() as session:
            result = await session.execute(
                select(TestResult).order_by(TestResult.created_at.desc())
            )
            results = result.scalars().all()

            logger.debug("Retrieved results", count=len(results))
            return [ResultService._convert_to_response(result) for result in results]

    @staticmethod
    async def get_result(result_id: UUID) -> ResultResponse:
        """Get a test result by ID."""
        async with get_session() as session:
            result = await session.get(TestResult, result_id)

            if not result:
                logger.warning("Result not found", result_id=str(result_id))
                raise ResultNotFoundError(f"Result with ID '{result_id}' not found")

            logger.debug("Retrieved result", result_id=str(result_id), name=result.test_name)
            return ResultService._convert_to_response(result)

    @staticmethod
    async def update_result(result_id: UUID, request: ResultUpdateRequest) -> ResultResponse:
        """Update a test result."""
        async with get_session() as session:
            result = await session.get(TestResult, result_id)

            if not result:
                logger.warning("Result not found for update", result_id=str(result_id))
                raise ResultNotFoundError(f"Result with ID '{result_id}' not found")

            # Validate suite exists if it's changing
            if result.suite_id != request.suite_id:
                suite = await session.get(TestSuite, request.suite_id)
                if not suite:
                    raise ResultValidationError(f"Suite with ID '{request.suite_id}' not found")

            # Update result fields - map API fields to database fields
            result.suite_id = request.suite_id
            result.test_name = request.name
            result.status = request.status
            result.duration_ms = request.duration_ms
            result.error_message = request.error_message
            result.tags = request.tags
            result.external_id = request.external_id
            result.full_title = request.full_title
            result.config_metadata = request.metadata

            try:
                await session.commit()
                await session.refresh(result)

                logger.info(
                    "Result updated",
                    result_id=str(result.id),
                    name=result.test_name,
                    status=result.status
                )

                return ResultService._convert_to_response(result)

            except IntegrityError as e:
                await session.rollback()
                logger.error("Result update failed", error=str(e))
                raise ResultValidationError(f"Result update failed: {str(e)}")

    @staticmethod
    async def delete_result(result_id: UUID) -> None:
        """Delete a test result."""
        async with get_session() as session:
            result = await session.get(TestResult, result_id)

            if not result:
                logger.warning("Result not found for deletion", result_id=str(result_id))
                raise ResultNotFoundError(f"Result with ID '{result_id}' not found")

            await session.delete(result)
            await session.commit()

            logger.info(
                "Result deleted",
                result_id=str(result_id),
                name=result.test_name
            )

    @staticmethod
    async def get_results_by_filter(
        suite_id: Optional[UUID] = None,
        status: Optional[str] = None,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[ResultResponse]:
        """Get results with filtering and pagination."""
        async with get_session() as session:
            query = select(TestResult)

            # Apply filters
            conditions = []
            if suite_id:
                conditions.append(TestResult.suite_id == suite_id)
            if status:
                conditions.append(TestResult.status == status)
            if name:
                conditions.append(TestResult.name.ilike(f"%{name}%"))
            if tags:
                # Check if result has any of the specified tags
                for tag in tags:
                    conditions.append(TestResult.tags.any(tag))

            if conditions:
                query = query.where(and_(*conditions))

            # Apply ordering, limit and offset
            query = query.order_by(TestResult.created_at.desc())
            query = query.offset(offset).limit(limit)

            result = await session.execute(query)
            results = result.scalars().all()

            logger.debug(
                "Retrieved filtered results",
                count=len(results),
                suite_id=str(suite_id) if suite_id else None,
                status=status,
                name=name,
                tags=tags
            )
            return [ResultService._convert_to_response(result) for result in results]