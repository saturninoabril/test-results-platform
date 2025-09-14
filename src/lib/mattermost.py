"""
Mattermost webhook integration for sending notifications about test results.
Supports various notification types including test failures, suite completion, and alerts.
"""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import httpx
from pydantic import BaseModel, Field

from .config import MattermostSettings

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """Types of notifications that can be sent."""
    TEST_FAILURE = "test_failure"
    SUITE_COMPLETION = "suite_completion"
    HIGH_FAILURE_RATE = "high_failure_rate"
    SYSTEM_ALERT = "system_alert"
    PERFORMANCE_ALERT = "performance_alert"


class MattermostAttachment(BaseModel):
    """Mattermost message attachment model."""
    color: Optional[str] = None
    pretext: Optional[str] = None
    text: Optional[str] = None
    title: Optional[str] = None
    title_link: Optional[str] = None
    author_name: Optional[str] = None
    author_link: Optional[str] = None
    author_icon: Optional[str] = None
    fields: Optional[List[Dict[str, Union[str, bool]]]] = None
    footer: Optional[str] = None
    footer_icon: Optional[str] = None
    timestamp: Optional[str] = None
    thumb_url: Optional[str] = None
    image_url: Optional[str] = None


class MattermostMessage(BaseModel):
    """Mattermost webhook message model."""
    text: Optional[str] = None
    username: Optional[str] = None
    icon_url: Optional[str] = None
    icon_emoji: Optional[str] = None
    channel: Optional[str] = None
    attachments: Optional[List[MattermostAttachment]] = None


class MattermostClient:
    """Client for sending messages to Mattermost via webhooks."""

    def __init__(self, settings: MattermostSettings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=30.0)

    async def __aenter__(self) -> "MattermostClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.client.aclose()

    async def send_message(
        self,
        message: MattermostMessage,
        channel: Optional[str] = None
    ) -> bool:
        """
        Send a message to Mattermost.

        Args:
            message: The message to send
            channel: Override channel for this message

        Returns:
            True if message was sent successfully, False otherwise
        """
        if not self.settings.enabled or not self.settings.webhook_url:
            logger.debug("Mattermost notifications disabled or webhook URL not configured")
            return False

        try:
            # Override channel if specified
            if channel:
                message.channel = channel
            elif not message.channel and self.settings.channel:
                message.channel = self.settings.channel

            # Set default username if not specified
            if not message.username:
                message.username = self.settings.username

            # Set default icon if not specified
            if not message.icon_url and self.settings.icon_url:
                message.icon_url = self.settings.icon_url

            payload = message.model_dump(exclude_none=True)

            response = await self.client.post(
                self.settings.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                logger.info(f"Successfully sent Mattermost notification to {message.channel or 'default channel'}")
                return True
            else:
                logger.error(f"Failed to send Mattermost notification: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error sending Mattermost notification: {str(e)}")
            return False

    def _get_color_for_type(self, notification_type: NotificationType) -> str:
        """Get color for notification type."""
        color_map = {
            NotificationType.TEST_FAILURE: "#FF4444",      # Red
            NotificationType.SUITE_COMPLETION: "#00DD00",  # Green
            NotificationType.HIGH_FAILURE_RATE: "#FF8800", # Orange
            NotificationType.SYSTEM_ALERT: "#FF0000",      # Dark Red
            NotificationType.PERFORMANCE_ALERT: "#FFAA00", # Yellow-Orange
        }
        return color_map.get(notification_type, "#0066CC")  # Default blue

    def _format_duration(self, duration_ms: int) -> str:
        """Format duration in milliseconds to human-readable format."""
        if duration_ms < 1000:
            return f"{duration_ms}ms"
        elif duration_ms < 60000:
            return f"{duration_ms / 1000:.1f}s"
        else:
            minutes = duration_ms // 60000
            seconds = (duration_ms % 60000) / 1000
            return f"{minutes}m {seconds:.0f}s"

    async def notify_test_failure(
        self,
        test_name: str,
        suite_name: str,
        framework: str,
        environment: str,
        error_message: Optional[str] = None,
        retry_count: int = 0,
        duration_ms: Optional[int] = None,
        channel: Optional[str] = None
    ) -> bool:
        """
        Send notification for test failure.

        Args:
            test_name: Name of the failed test
            suite_name: Name of the test suite
            framework: Testing framework (e.g., Playwright, Cypress)
            environment: Test environment
            error_message: Error message from the test
            retry_count: Number of retries attempted
            duration_ms: Test duration in milliseconds
            channel: Override channel for this notification

        Returns:
            True if notification was sent successfully
        """
        if not self.settings.notify_test_failures:
            return False

        fields: List[Dict[str, Union[str, bool]]] = [
            {"title": "Suite", "value": suite_name, "short": True},
            {"title": "Framework", "value": framework, "short": True},
            {"title": "Environment", "value": environment, "short": True},
        ]

        if retry_count > 0:
            fields.append({"title": "Retries", "value": str(retry_count), "short": True})

        if duration_ms is not None:
            fields.append({"title": "Duration", "value": self._format_duration(duration_ms), "short": True})

        attachment = MattermostAttachment(
            color=self._get_color_for_type(NotificationType.TEST_FAILURE),
            title=f"❌ Test Failed: {test_name}",
            text=error_message[:500] + "..." if error_message and len(error_message) > 500 else error_message,
            fields=fields,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )

        message = MattermostMessage(
            text="Test failure detected",
            attachments=[attachment]
        )

        return await self.send_message(message, channel)

    async def notify_suite_completion(
        self,
        suite_name: str,
        framework: str,
        environment: str,
        total_tests: int,
        passed_tests: int,
        failed_tests: int,
        skipped_tests: int,
        duration_ms: int,
        started_at: datetime,
        channel: Optional[str] = None
    ) -> bool:
        """
        Send notification for suite completion.

        Args:
            suite_name: Name of the completed suite
            framework: Testing framework
            environment: Test environment
            total_tests: Total number of tests
            passed_tests: Number of passed tests
            failed_tests: Number of failed tests
            skipped_tests: Number of skipped tests
            duration_ms: Total suite duration
            started_at: Suite start time
            channel: Override channel for this notification

        Returns:
            True if notification was sent successfully
        """
        if not self.settings.notify_suite_completion:
            return False

        # Determine emoji and color based on results
        if failed_tests == 0:
            emoji = "✅"
            color = "#00DD00"  # Green
            status = "Passed"
        else:
            emoji = "❌"
            color = "#FF4444"  # Red
            status = "Failed"

        failure_rate = failed_tests / total_tests if total_tests > 0 else 0

        fields: List[Dict[str, Union[str, bool]]] = [
            {"title": "Framework", "value": framework, "short": True},
            {"title": "Environment", "value": environment, "short": True},
            {"title": "Total Tests", "value": str(total_tests), "short": True},
            {"title": "Passed", "value": str(passed_tests), "short": True},
            {"title": "Failed", "value": str(failed_tests), "short": True},
            {"title": "Skipped", "value": str(skipped_tests), "short": True},
            {"title": "Duration", "value": self._format_duration(duration_ms), "short": True},
            {"title": "Failure Rate", "value": f"{failure_rate:.1%}", "short": True},
        ]

        attachment = MattermostAttachment(
            color=color,
            title=f"{emoji} Suite {status}: {suite_name}",
            fields=fields,
            timestamp=started_at.isoformat() + "Z"
        )

        message = MattermostMessage(
            text=f"Test suite completed with {status.lower()} status",
            attachments=[attachment]
        )

        return await self.send_message(message, channel)

    async def notify_high_failure_rate(
        self,
        suite_name: str,
        framework: str,
        environment: str,
        failure_rate: float,
        failed_tests: int,
        total_tests: int,
        recent_failures: Optional[List[str]] = None,
        channel: Optional[str] = None
    ) -> bool:
        """
        Send notification for high failure rate.

        Args:
            suite_name: Name of the suite
            framework: Testing framework
            environment: Test environment
            failure_rate: Failure rate (0.0-1.0)
            failed_tests: Number of failed tests
            total_tests: Total number of tests
            recent_failures: List of recent failed test names
            channel: Override channel for this notification

        Returns:
            True if notification was sent successfully
        """
        if not self.settings.notify_high_failure_rate or failure_rate < self.settings.failure_rate_threshold:
            return False

        fields: List[Dict[str, Union[str, bool]]] = [
            {"title": "Framework", "value": framework, "short": True},
            {"title": "Environment", "value": environment, "short": True},
            {"title": "Failure Rate", "value": f"{failure_rate:.1%}", "short": True},
            {"title": "Failed Tests", "value": f"{failed_tests}/{total_tests}", "short": True},
        ]

        text = f"High failure rate detected in test suite: {failure_rate:.1%}"
        if recent_failures:
            failures_text = "\n".join([f"• {test}" for test in recent_failures[:5]])
            if len(recent_failures) > 5:
                failures_text += f"\n... and {len(recent_failures) - 5} more"
            text += f"\n\n**Recent Failures:**\n{failures_text}"

        attachment = MattermostAttachment(
            color=self._get_color_for_type(NotificationType.HIGH_FAILURE_RATE),
            title=f"⚠️ High Failure Rate: {suite_name}",
            text=text,
            fields=fields,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )

        message = MattermostMessage(
            text="High failure rate alert",
            attachments=[attachment]
        )

        return await self.send_message(message, channel)

    async def notify_system_alert(
        self,
        title: str,
        message: str,
        severity: str = "warning",
        details: Optional[Dict[str, Any]] = None,
        channel: Optional[str] = None
    ) -> bool:
        """
        Send system alert notification.

        Args:
            title: Alert title
            message: Alert message
            severity: Severity level (info, warning, error, critical)
            details: Additional details to include
            channel: Override channel for this notification

        Returns:
            True if notification was sent successfully
        """
        severity_colors = {
            "info": "#0066CC",      # Blue
            "warning": "#FF8800",   # Orange
            "error": "#FF4444",     # Red
            "critical": "#AA0000",  # Dark Red
        }

        severity_emojis = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "critical": "🚨",
        }

        fields: List[Dict[str, Union[str, bool]]] = []
        if details:
            for key, value in details.items():
                fields.append({
                    "title": key.replace("_", " ").title(),
                    "value": str(value),
                    "short": True
                })

        emoji = severity_emojis.get(severity, "ℹ️")
        color = severity_colors.get(severity, "#0066CC")

        attachment = MattermostAttachment(
            color=color,
            title=f"{emoji} {title}",
            text=message,
            fields=fields if fields else None,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )

        mattermost_message = MattermostMessage(
            text=f"System alert: {severity}",
            attachments=[attachment]
        )

        return await self.send_message(mattermost_message, channel)

    async def notify_performance_alert(
        self,
        metric_name: str,
        current_value: Union[int, float],
        threshold_value: Union[int, float],
        unit: str = "",
        context: Optional[str] = None,
        channel: Optional[str] = None
    ) -> bool:
        """
        Send performance alert notification.

        Args:
            metric_name: Name of the performance metric
            current_value: Current metric value
            threshold_value: Threshold that was exceeded
            unit: Unit of measurement
            context: Additional context about the alert
            channel: Override channel for this notification

        Returns:
            True if notification was sent successfully
        """
        fields: List[Dict[str, Union[str, bool]]] = [
            {"title": "Metric", "value": metric_name, "short": True},
            {"title": "Current Value", "value": f"{current_value}{unit}", "short": True},
            {"title": "Threshold", "value": f"{threshold_value}{unit}", "short": True},
        ]

        if context:
            fields.append({"title": "Context", "value": context, "short": False})

        attachment = MattermostAttachment(
            color=self._get_color_for_type(NotificationType.PERFORMANCE_ALERT),
            title=f"📊 Performance Alert: {metric_name}",
            text=f"Performance threshold exceeded for {metric_name}",
            fields=fields,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )

        message = MattermostMessage(
            text="Performance alert triggered",
            attachments=[attachment]
        )

        return await self.send_message(message, channel)


async def get_mattermost_client(settings: MattermostSettings) -> MattermostClient:
    """Get a configured Mattermost client."""
    return MattermostClient(settings)