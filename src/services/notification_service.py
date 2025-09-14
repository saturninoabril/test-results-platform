"""
Notification service for sending alerts and updates about test results.
Integrates with Mattermost and other notification channels.
"""

import logging
from typing import Any

from ..lib.config import get_settings
from ..lib.mattermost import MattermostClient, get_mattermost_client
from ..models.test_result import TestResult
from ..models.test_suite import TestSuite

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications about test results and system events."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._mattermost_client: MattermostClient | None = None

    async def _get_mattermost_client(self) -> MattermostClient | None:
        """Get or create Mattermost client if enabled."""
        if not self.settings.mattermost.enabled:
            return None

        if self._mattermost_client is None:
            self._mattermost_client = await get_mattermost_client(self.settings.mattermost)

        return self._mattermost_client

    async def notify_test_failure(
        self,
        test_result: TestResult,
        suite: TestSuite,
        framework_name: str,
        environment_name: str,
        channel: str | None = None,
    ) -> bool:
        """
        Send notification when a test fails.

        Args:
            test_result: The failed test result
            suite: The test suite containing the failed test
            framework_name: Name of the testing framework
            environment_name: Name of the test environment
            channel: Optional channel override

        Returns:
            True if notification was sent successfully
        """
        try:
            mattermost = await self._get_mattermost_client()
            if mattermost:
                return await mattermost.notify_test_failure(
                    test_name=test_result.test_name,
                    suite_name=suite.name,
                    framework=framework_name,
                    environment=environment_name,
                    error_message=test_result.error_message,
                    retry_count=test_result.retry_count,
                    duration_ms=test_result.duration_ms,
                    channel=channel,
                )
            return False

        except Exception as e:
            logger.error(f"Error sending test failure notification: {str(e)}")
            return False

    async def notify_suite_completion(
        self,
        suite: TestSuite,
        framework_name: str,
        environment_name: str,
        channel: str | None = None,
    ) -> bool:
        """
        Send notification when a test suite completes.

        Args:
            suite: The completed test suite
            framework_name: Name of the testing framework
            environment_name: Name of the test environment
            channel: Optional channel override

        Returns:
            True if notification was sent successfully
        """
        try:
            mattermost = await self._get_mattermost_client()
            if mattermost:
                return await mattermost.notify_suite_completion(
                    suite_name=suite.name,
                    framework=framework_name,
                    environment=environment_name,
                    total_tests=suite.total_tests,
                    passed_tests=suite.passed_tests,
                    failed_tests=suite.failed_tests,
                    skipped_tests=suite.skipped_tests,
                    duration_ms=suite.duration_ms,
                    started_at=suite.started_at,
                    channel=channel,
                )
            return False

        except Exception as e:
            logger.error(f"Error sending suite completion notification: {str(e)}")
            return False

    async def notify_high_failure_rate(
        self,
        suite: TestSuite,
        framework_name: str,
        environment_name: str,
        failed_tests: list[TestResult],
        channel: str | None = None,
    ) -> bool:
        """
        Send notification for high failure rate in a test suite.

        Args:
            suite: The test suite with high failure rate
            framework_name: Name of the testing framework
            environment_name: Name of the test environment
            failed_tests: List of failed test results
            channel: Optional channel override

        Returns:
            True if notification was sent successfully
        """
        try:
            if suite.total_tests == 0:
                return False

            failure_rate = suite.failed_tests / suite.total_tests
            recent_failures = [
                test.test_name for test in failed_tests[:10]
            ]  # Limit to 10 recent failures

            mattermost = await self._get_mattermost_client()
            if mattermost:
                return await mattermost.notify_high_failure_rate(
                    suite_name=suite.name,
                    framework=framework_name,
                    environment=environment_name,
                    failure_rate=failure_rate,
                    failed_tests=suite.failed_tests,
                    total_tests=suite.total_tests,
                    recent_failures=recent_failures,
                    channel=channel,
                )
            return False

        except Exception as e:
            logger.error(f"Error sending high failure rate notification: {str(e)}")
            return False

    async def notify_system_alert(
        self,
        title: str,
        message: str,
        severity: str = "warning",
        details: dict[str, Any] | None = None,
        channel: str | None = None,
    ) -> bool:
        """
        Send system alert notification.

        Args:
            title: Alert title
            message: Alert message
            severity: Severity level (info, warning, error, critical)
            details: Additional details
            channel: Optional channel override

        Returns:
            True if notification was sent successfully
        """
        try:
            mattermost = await self._get_mattermost_client()
            if mattermost:
                return await mattermost.notify_system_alert(
                    title=title,
                    message=message,
                    severity=severity,
                    details=details,
                    channel=channel,
                )
            return False

        except Exception as e:
            logger.error(f"Error sending system alert notification: {str(e)}")
            return False

    async def notify_performance_alert(
        self,
        metric_name: str,
        current_value: float,
        threshold_value: float,
        unit: str = "",
        context: str | None = None,
        channel: str | None = None,
    ) -> bool:
        """
        Send performance alert notification.

        Args:
            metric_name: Name of the performance metric
            current_value: Current metric value
            threshold_value: Threshold that was exceeded
            unit: Unit of measurement
            context: Additional context
            channel: Optional channel override

        Returns:
            True if notification was sent successfully
        """
        try:
            mattermost = await self._get_mattermost_client()
            if mattermost:
                return await mattermost.notify_performance_alert(
                    metric_name=metric_name,
                    current_value=current_value,
                    threshold_value=threshold_value,
                    unit=unit,
                    context=context,
                    channel=channel,
                )
            return False

        except Exception as e:
            logger.error(f"Error sending performance alert notification: {str(e)}")
            return False

    async def notify_bulk_failure_analysis(
        self,
        failed_results: list[TestResult],
        suite_name: str,
        framework_name: str,
        environment_name: str,
        analysis: dict[str, Any] | None = None,
        channel: str | None = None,
    ) -> bool:
        """
        Send notification with analysis of multiple test failures.

        Args:
            failed_results: List of failed test results
            suite_name: Name of the test suite
            framework_name: Name of the testing framework
            environment_name: Name of the test environment
            analysis: Optional analysis data
            channel: Optional channel override

        Returns:
            True if notification was sent successfully
        """
        try:
            if not failed_results:
                return False

            # Group failures by error pattern
            error_patterns: dict[str, list[TestResult]] = {}
            for result in failed_results:
                error_key = result.error_message[:100] if result.error_message else "Unknown error"
                if error_key not in error_patterns:
                    error_patterns[error_key] = []
                error_patterns[error_key].append(result)

            # Create analysis summary
            analysis_details = {
                "Total Failures": len(failed_results),
                "Unique Error Patterns": len(error_patterns),
                "Average Duration": f"{sum(r.duration_ms for r in failed_results) / len(failed_results):.0f}ms",
                "Tests with Retries": sum(1 for r in failed_results if r.retry_count > 0),
            }

            if analysis:
                analysis_details.update(analysis)

            # Send system alert with analysis
            title = f"Bulk Test Failure Analysis: {suite_name}"
            message = f"Analysis of {len(failed_results)} test failures in {framework_name} on {environment_name}"

            if len(error_patterns) <= 3:
                message += "\n\n**Common Error Patterns:**"
                for pattern, tests in error_patterns.items():
                    message += f"\n• {pattern} ({len(tests)} tests)"

            return await self.notify_system_alert(
                title=title,
                message=message,
                severity="error",
                details=analysis_details,
                channel=channel,
            )

        except Exception as e:
            logger.error(f"Error sending bulk failure analysis notification: {str(e)}")
            return False

    async def close(self) -> None:
        """Close notification service and clean up resources."""
        if self._mattermost_client:
            await self._mattermost_client.__aexit__(None, None, None)
            self._mattermost_client = None


# Global notification service instance
_notification_service: NotificationService | None = None


def get_notification_service() -> NotificationService:
    """Get the global notification service instance."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


async def close_notification_service() -> None:
    """Close the global notification service."""
    global _notification_service
    if _notification_service:
        await _notification_service.close()
        _notification_service = None
