"""
Playwright service for managing Playwright-specific test operations.
Provides business logic for Playwright test suites, results, events, and artifacts.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from ..lib.database import get_session
from ..models import (
    ArtifactType,
    PlaywrightTestResult,
    SuiteStatus,
    TestArtifact,
    TestEvent,
    TestEventType,
    TestStatus,
    TestSuite,
)

logger = structlog.get_logger()


class PlaywrightNotFoundError(Exception):
    """Playwright entity not found error."""

    pass


class PlaywrightValidationError(Exception):
    """Playwright validation error."""

    pass


class PlaywrightService:
    """Service for managing Playwright test operations."""

    @staticmethod
    async def create_suite(
        name: str,
        version: str,
        test_count: int,
        status: str,
        start_time: datetime,
        end_time: datetime | None = None,
        framework_metadata: dict[str, Any] | None = None,
        environment_metadata: dict[str, Any] | None = None,
        server_metadata: dict[str, Any] | None = None,
        ci_run_metadata: dict[str, Any] | None = None,
        playwright_test_files: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new Playwright test suite."""

        # Validate test_count
        if test_count < 0:
            raise PlaywrightValidationError("Negative test_count is not allowed")

        # Validate suite name
        if not name or not name.strip():
            raise PlaywrightValidationError("Suite name cannot be empty")

        # Validate version
        if not version or not version.strip():
            raise PlaywrightValidationError("Version cannot be empty")

        # Validate status
        try:
            normalized_status = SuiteStatus.normalize(status)
        except ValueError as e:
            raise PlaywrightValidationError(str(e)) from e

        # Validate end_time is not before start_time
        if end_time and end_time < start_time:
            raise PlaywrightValidationError("End time cannot be before start time")

        async with get_session() as session:
            try:
                suite = TestSuite(
                    name=name,
                    total_tests=test_count,
                    started_at=start_time,
                    completed_at=end_time or start_time,  # Use end_time if provided
                    framework_metadata=framework_metadata,
                    environment_metadata=environment_metadata,
                    server_metadata=server_metadata,
                    ci_run_metadata=ci_run_metadata,
                    playwright_test_files=playwright_test_files,
                    # Playwright-specific fields
                    start_time=start_time,
                    end_time=end_time,
                    duration_ms=(
                        int((end_time - start_time).total_seconds() * 1000) if end_time else 0
                    ),
                    status=normalized_status.value,
                )

                session.add(suite)
                await session.commit()

                logger.info(
                    "Playwright suite created",
                    suite_id=str(suite.id),
                    name=suite.name,
                )

                return {
                    "id": suite.id,
                    "name": suite.name,
                    "version": version,
                    "test_count": test_count,
                    "status": status,
                    "start_time": start_time,
                    "end_time": suite.end_time,
                    "duration": suite.duration_ms,
                    "framework_metadata": framework_metadata,
                    "environment_metadata": environment_metadata,
                    "server_metadata": server_metadata,
                    "ci_run_metadata": ci_run_metadata,
                    "playwright_test_files": playwright_test_files,
                    "created_at": suite.created_at,
                    "updated_at": suite.updated_at,
                }

            except IntegrityError as e:
                await session.rollback()
                logger.error("Suite creation integrity error", error=str(e))
                raise PlaywrightValidationError(f"Suite creation failed: {e}") from e
            except Exception as e:
                await session.rollback()
                logger.error("Suite creation failed", error=str(e))
                raise

    @staticmethod
    async def update_suite(
        suite_id: UUID,
        status: str | None = None,
        end_time: datetime | None = None,
        duration: int | None = None,
        test_count: int | None = None,
    ) -> dict[str, Any]:
        """Update a Playwright test suite with proper async context."""

        # Validation
        if all(param is None for param in [status, end_time, duration, test_count]):
            raise PlaywrightValidationError("At least one field must be provided for update")

        normalized_status = None
        if status:
            try:
                normalized_status = SuiteStatus.normalize(status)
            except ValueError as e:
                raise PlaywrightValidationError(str(e)) from e

        if test_count is not None and test_count < 0:
            raise PlaywrightValidationError("Test count must be non-negative")

        if duration is not None and duration < 0:
            raise PlaywrightValidationError("Duration must be non-negative")

        async def _do_update() -> dict[str, Any]:
            """Inner function to ensure proper async context."""
            async with get_session() as session:
                try:
                    stmt = select(TestSuite).where(TestSuite.id == suite_id)
                    result = await session.execute(stmt)
                    suite = result.scalar_one_or_none()

                    if not suite:
                        raise PlaywrightNotFoundError(f"Suite {suite_id} not found")

                    # Check for end_time validation against suite's actual start_time
                    if end_time and suite.start_time and end_time < suite.start_time:
                        raise PlaywrightValidationError("End time cannot be before start time")

                    # Update fields
                    if normalized_status:
                        suite.status = normalized_status.value
                    if end_time:
                        suite.end_time = end_time
                        suite.completed_at = end_time
                    if duration:
                        suite.duration_ms = duration
                    if test_count:
                        suite.total_tests = test_count

                    await session.commit()
                    await session.refresh(suite)

                    logger.info("Playwright suite updated", suite_id=str(suite_id), status=status)

                    return {
                        "id": suite.id,
                        "name": suite.name,
                        "test_count": suite.total_tests,
                        "status": suite.status if suite.status else "unknown",
                        "start_time": suite.start_time or suite.started_at,
                        "end_time": suite.end_time or suite.completed_at,
                        "duration": suite.duration_ms,
                        "framework_metadata": suite.framework_metadata,
                        "environment_metadata": suite.environment_metadata,
                        "server_metadata": suite.server_metadata,
                        "ci_run_metadata": suite.ci_run_metadata,
                        "playwright_test_files": suite.playwright_test_files,
                        "created_at": suite.created_at,
                        "updated_at": suite.updated_at,
                    }

                except PlaywrightNotFoundError:
                    raise
                except IntegrityError as e:
                    await session.rollback()
                    logger.error(
                        "Suite update integrity error", suite_id=str(suite_id), error=str(e)
                    )
                    raise PlaywrightValidationError(f"Suite update failed: {e}") from e
                except Exception as e:
                    await session.rollback()
                    logger.error("Suite update failed", suite_id=str(suite_id), error=str(e))
                    raise

        # Execute directly - no need for task creation
        return await _do_update()

    @staticmethod
    async def create_test_result(
        suite_id: UUID,
        external_id: str | None,
        title: str,
        full_title: str,
        status: str,
        location: dict[str, Any] | None = None,
        project_name: str | None = None,
        timeout: int | None = None,
        tags: list[str] | None = None,
        start_time: datetime | None = None,
        duration: int | None = None,
        error_message: str | None = None,
        retry_count: int = 0,
    ) -> dict[str, Any]:
        """Create a new Playwright test result."""
        from datetime import datetime

        # Validation
        if tags and len(tags) > 20:
            raise PlaywrightValidationError("Cannot have more than 20 tags")

        if timeout and timeout < 0:
            raise PlaywrightValidationError("Test timeout must be non-negative")

        if timeout and timeout > 3600000:  # 1 hour in ms
            raise PlaywrightValidationError("Test timeout cannot exceed 1 hour (3600000ms)")

        if status not in [s.value for s in TestStatus]:
            raise PlaywrightValidationError(f"Invalid test status '{status}'")

        # Generate defaults if not provided
        if start_time is None:
            start_time = datetime.utcnow()

        async with get_session() as session:
            try:
                # Verify suite exists
                suite_stmt = select(TestSuite).where(TestSuite.id == suite_id)
                suite_result = await session.execute(suite_stmt)
                if not suite_result.scalar_one_or_none():
                    raise PlaywrightValidationError(f"Suite with ID {suite_id} does not exist")

            except PlaywrightValidationError:
                raise
            except Exception as e:
                await session.rollback()
                logger.error("Test result validation failed", error=str(e))
                raise PlaywrightValidationError(f"Validation failed: {e}") from e

            try:
                # Set timestamps - use provided start_time or current time
                now = datetime.utcnow() if start_time is None else start_time

                test_result = PlaywrightTestResult(
                    suite_id=suite_id,
                    test_name=title,
                    full_title=full_title,
                    status=status,
                    duration_ms=duration or 0,
                    started_at=now,
                    completed_at=now,  # Will be updated when test completes
                    error_message=error_message,
                    tags=tags,
                    external_id=external_id,
                    retry_count=retry_count,
                    # Playwright-specific fields
                    location=location,
                    project_name=project_name,
                    timeout_ms=timeout,
                )

                session.add(test_result)
                await session.commit()

                logger.info(
                    "Playwright test result created",
                    result_id=str(test_result.id),
                    external_id=external_id,
                    status=status,
                )

                return {
                    "id": test_result.id,
                    "suite_id": suite_id,
                    "external_id": external_id,
                    "title": title,
                    "full_title": full_title,
                    "status": status,
                    "location": location,
                    "project_name": project_name,
                    "timeout": timeout,
                    "tags": tags,
                    "start_time": start_time,
                    "end_time": None,  # TODO: Add end_time support when test completes
                    "duration": duration,
                    "error_message": error_message,
                    "metadata": test_result.config_metadata,
                    "stack_trace": test_result.stack_trace,
                    "retry_count": test_result.retry_count,
                    "created_at": test_result.created_at,
                    "updated_at": test_result.updated_at,
                }

            except IntegrityError as e:
                await session.rollback()
                logger.error("Test result creation integrity error", error=str(e))
                if "foreign key constraint" in str(e).lower():
                    if "suite_id" in str(e):
                        raise PlaywrightValidationError(
                            f"Suite with ID {suite_id} does not exist"
                        ) from e
                    else:
                        raise PlaywrightValidationError(f"Invalid reference: {e}") from e
                else:
                    raise PlaywrightValidationError(f"Test result creation failed: {e}") from e
            except Exception as e:
                await session.rollback()
                logger.error("Test result creation failed", error=str(e))
                raise

    @staticmethod
    async def update_test_result(
        external_id: str,
        suite_id: UUID,
        status: str | None = None,
        duration: int | None = None,
        _end_time: datetime | None = None,
        error_message: str | None = None,
        stack_trace: str | None = None,
    ) -> dict[str, Any]:
        """Update a Playwright test result with proper async context."""

        async def _do_update() -> dict[str, Any]:
            """Inner function to ensure proper async context."""
            async with get_session() as session:
                try:
                    stmt = select(PlaywrightTestResult).where(
                        PlaywrightTestResult.external_id == external_id,
                        PlaywrightTestResult.suite_id == suite_id,
                    )
                    result = await session.execute(stmt)
                    test_result = result.scalar_one_or_none()

                    if not test_result:
                        raise PlaywrightNotFoundError(
                            f"Test result {external_id} not found in suite {suite_id}"
                        )

                    # Update fields
                    if status:
                        test_result.status = status
                    if duration is not None:
                        test_result.duration_ms = duration
                    if error_message is not None:
                        test_result.error_message = error_message
                    if stack_trace is not None:
                        test_result.stack_trace = stack_trace

                    # Force commit in new task to ensure proper greenlet context
                    await session.commit()
                    await session.refresh(test_result)

                    logger.info(
                        "Playwright test result updated", external_id=external_id, status=status
                    )

                    return {
                        "id": test_result.id,
                        "suite_id": test_result.suite_id,
                        "external_id": external_id,
                        "title": test_result.test_name,
                        "full_title": test_result.full_title,
                        "status": test_result.status,
                        "location": test_result.location,
                        "project_name": test_result.project_name,
                        "timeout": test_result.timeout_ms,
                        "tags": test_result.tags,
                        "duration": test_result.duration_ms,
                        "error_message": test_result.error_message,
                        "stack_trace": test_result.stack_trace,
                        "retry_count": test_result.retry_count,
                        "created_at": test_result.created_at,
                        "updated_at": test_result.updated_at,
                    }

                except Exception as e:
                    await session.rollback()
                    logger.error("Test result update failed", external_id=external_id, error=str(e))
                    raise

        # Execute directly - no need for task creation
        return await _do_update()

    @staticmethod
    async def get_test_results(suite_id: UUID, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        """Get Playwright test results for a suite with summary statistics and artifacts."""
        async with get_session() as session:
            try:
                # Get test results with their artifacts
                stmt = (
                    select(PlaywrightTestResult)
                    .options(selectinload(PlaywrightTestResult.test_artifacts))
                    .where(PlaywrightTestResult.suite_id == suite_id)
                    .limit(limit)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                test_results = result.scalars().all()

                # Get summary statistics for the entire suite
                summary_stmt = select(
                    func.count(PlaywrightTestResult.id).label("total_tests"),
                    func.sum(PlaywrightTestResult.duration_ms).label("total_duration"),
                    func.count()
                    .filter(PlaywrightTestResult.status == TestStatus.PASSED)
                    .label("passed"),
                    func.count()
                    .filter(PlaywrightTestResult.status == TestStatus.FAILED)
                    .label("failed"),
                    func.count()
                    .filter(PlaywrightTestResult.status == TestStatus.SKIPPED)
                    .label("skipped"),
                    func.count()
                    .filter(PlaywrightTestResult.status == TestStatus.RUNNING)
                    .label("running"),
                ).where(PlaywrightTestResult.suite_id == suite_id)
                summary_result = await session.execute(summary_stmt)
                summary_row = summary_result.first()

                # Build results with artifact information
                results = []
                for test_result in test_results:
                    # Format artifacts if they exist
                    artifacts = []
                    if test_result.test_artifacts:
                        for artifact in test_result.test_artifacts:
                            artifacts.append(
                                {
                                    "id": artifact.id,
                                    "type": artifact.artifact_type,
                                    "filename": artifact.file_name,
                                    "storage_path": artifact.storage_key,
                                    "file_size": artifact.file_size,
                                    "content_type": artifact.effective_content_type,
                                    "capture_time": artifact.capture_time,
                                    "test_step": artifact.test_step,
                                    "created_at": artifact.created_at,
                                }
                            )

                    results.append(
                        {
                            "id": test_result.id,
                            "suite_id": test_result.suite_id,
                            "external_id": test_result.external_id,
                            "title": test_result.test_name,
                            "full_title": test_result.full_title,
                            "status": test_result.status,
                            "location": test_result.location,
                            "project_name": test_result.project_name,
                            "timeout": test_result.timeout_ms,
                            "tags": test_result.tags,
                            "duration": test_result.duration_ms,
                            "error_message": test_result.error_message,
                            "stack_trace": test_result.stack_trace,
                            "retry_count": test_result.retry_count,
                            "artifacts": artifacts,
                            "created_at": test_result.created_at,
                            "updated_at": test_result.updated_at,
                        }
                    )

                # Build summary
                summary = {
                    "total_tests": summary_row.total_tests
                    if summary_row and summary_row.total_tests
                    else 0,
                    "total_duration_ms": summary_row.total_duration
                    if summary_row and summary_row.total_duration
                    else 0,
                    "status_counts": {
                        "passed": summary_row.passed if summary_row and summary_row.passed else 0,
                        "failed": summary_row.failed if summary_row and summary_row.failed else 0,
                        "skipped": summary_row.skipped
                        if summary_row and summary_row.skipped
                        else 0,
                        "running": summary_row.running
                        if summary_row and summary_row.running
                        else 0,
                    },
                }

                logger.info(
                    "Playwright test results retrieved", suite_id=str(suite_id), count=len(results)
                )

                return {
                    "total": len(results),
                    "summary": summary,
                    "results": results,
                }

            except Exception as e:
                logger.error("Test results retrieval failed", suite_id=str(suite_id), error=str(e))
                raise

    @staticmethod
    async def create_event(
        suite_id: UUID,
        test_external_id: str | None,
        event_type: str,
        timestamp: datetime,
        data: dict[str, Any] | None = None,
        request_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new Playwright test event."""
        # Validation
        if event_type not in [e.value for e in TestEventType]:
            raise PlaywrightValidationError(f"Invalid event type '{event_type}'")

        async with get_session() as session:
            try:
                # Verify suite exists
                suite_stmt = select(TestSuite).where(TestSuite.id == suite_id)
                suite_result = await session.execute(suite_stmt)
                if not suite_result.scalar_one_or_none():
                    raise PlaywrightValidationError(f"Suite with ID {suite_id} does not exist")

            except PlaywrightValidationError:
                raise
            except Exception as e:
                await session.rollback()
                logger.error("Event validation failed", error=str(e))
                raise PlaywrightValidationError(f"Validation failed: {e}") from e

            try:
                event = TestEvent(
                    suite_id=suite_id,
                    test_external_id=test_external_id,
                    event_type=event_type,
                    timestamp=timestamp,
                    data=data,
                    request_id=request_id,
                    user_id=user_id,
                )

                session.add(event)
                await session.commit()

                logger.info(
                    "Playwright event created",
                    event_id=str(event.id),
                    suite_id=str(suite_id),
                    event_type=event_type,
                )

                return {
                    "id": event.id,
                    "suite_id": suite_id,
                    "test_external_id": test_external_id,
                    "event_type": event_type,
                    "timestamp": timestamp,
                    "data": data,
                    "request_id": request_id,
                    "user_id": user_id,
                    "created_at": event.created_at,
                    "updated_at": event.updated_at,
                }

            except IntegrityError as e:
                await session.rollback()
                logger.error("Event creation integrity error", error=str(e))
                if "foreign key constraint" in str(e).lower():
                    if "suite_id" in str(e):
                        raise PlaywrightValidationError(
                            f"Suite with ID {suite_id} does not exist"
                        ) from e
                    else:
                        raise PlaywrightValidationError(f"Invalid reference: {e}") from e
                else:
                    raise PlaywrightValidationError(f"Event creation failed: {e}") from e
            except Exception as e:
                await session.rollback()
                logger.error("Event creation failed", error=str(e))
                raise

    @staticmethod
    async def get_events(suite_id: UUID, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        """Get Playwright events for a suite."""
        async with get_session() as session:
            try:
                stmt = (
                    select(TestEvent)
                    .where(TestEvent.suite_id == suite_id)
                    .limit(limit)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                events = result.scalars().all()

                event_list = []
                for event in events:
                    event_list.append(
                        {
                            "id": event.id,
                            "suite_id": event.suite_id,
                            "test_external_id": event.test_external_id,
                            "event_type": event.event_type,
                            "timestamp": event.timestamp,
                            "data": event.data,
                            "request_id": event.request_id,
                            "user_id": event.user_id,
                            "created_at": event.created_at,
                            "updated_at": event.updated_at,
                        }
                    )

                logger.info(
                    "Playwright events retrieved", suite_id=str(suite_id), count=len(event_list)
                )

                return {
                    "total": len(event_list),
                    "events": event_list,
                }

            except Exception as e:
                logger.error("Events retrieval failed", suite_id=str(suite_id), error=str(e))
                raise

    @staticmethod
    async def create_artifact(
        test_result_id: UUID,
        artifact_type: str,
        filename: str,
        storage_path: str,
        file_size: int,
        content_type: str,
        capture_time: datetime,
        test_step: str | None = None,
    ) -> dict[str, Any]:
        """Create a test artifact for a Playwright test result."""
        async with get_session() as session:
            try:
                # Verify test result exists and get suite_id
                result = await session.get(PlaywrightTestResult, test_result_id)
                if not result:
                    raise PlaywrightNotFoundError(f"Test result with ID {test_result_id} not found")

                # Map artifact type string to enum
                try:
                    artifact_type_enum = ArtifactType(artifact_type.lower())
                except ValueError:
                    # Default to OTHER for unknown types
                    artifact_type_enum = ArtifactType.OTHER

                # Generate a simple checksum placeholder for now (would be calculated from actual file in production)
                import hashlib

                checksum = hashlib.sha256(
                    f"{storage_path}{filename}{file_size}".encode()
                ).hexdigest()

                # Create artifact with all required fields
                # Note: Only set playwright_result_id, not suite_id, due to constraint requiring exactly one parent
                artifact = TestArtifact(
                    playwright_result_id=test_result_id,
                    artifact_type=artifact_type_enum,
                    file_name=filename,
                    storage_key=storage_path,
                    file_size=file_size,
                    mime_type=content_type,  # Use content_type as mime_type (required field)
                    content_type=content_type,  # Keep for Playwright compatibility
                    checksum=checksum,  # Required SHA-256 hash
                    capture_time=capture_time,
                    test_step=test_step,
                )

                session.add(artifact)
                await session.commit()

                logger.info(
                    "Playwright test artifact created",
                    artifact_id=str(artifact.id),
                    test_result_id=str(test_result_id),
                    artifact_type=artifact_type,
                    filename=filename,
                )

                return {
                    "id": artifact.id,
                    "test_result_id": artifact.playwright_result_id,
                    "type": artifact.artifact_type,
                    "filename": artifact.file_name,
                    "storage_path": artifact.storage_key,
                    "file_size": artifact.file_size,
                    "content_type": artifact.content_type,
                    "capture_time": artifact.capture_time,
                    "test_step": artifact.test_step,
                    "created_at": artifact.created_at,
                    "updated_at": artifact.updated_at,
                }

            except IntegrityError as e:
                await session.rollback()
                logger.error("Artifact creation failed - database constraint", error=str(e))
                raise PlaywrightValidationError(
                    "Failed to create artifact due to data constraints"
                ) from e
            except Exception as e:
                await session.rollback()
                logger.error(
                    "Artifact creation failed", test_result_id=str(test_result_id), error=str(e)
                )
                raise
