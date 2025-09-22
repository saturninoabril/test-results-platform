"""
SQLAlchemy models for the Test Results Management API.
Provides data models for test frameworks, environments, suites, results, and artifacts.
"""

from .base import Base, BaseModel, TimestampMixin, UUIDMixin
from .base_test_result import BaseTestResult, TestStatus
from .playwright_test_result import PlaywrightTestResult
from .test_artifact import ArtifactType, TestArtifact
from .test_event import TestEvent, TestEventType

# Legacy - remove after migration
from .test_result import TestResult
from .test_suite import SuiteStatus, TestSuite

__all__ = [
    "Base",
    "BaseModel",
    "TimestampMixin",
    "UUIDMixin",
    "TestSuite",
    "SuiteStatus",
    "BaseTestResult",
    "PlaywrightTestResult",
    "TestStatus",
    "TestArtifact",
    "ArtifactType",
    "TestEvent",
    "TestEventType",
    # Legacy
    "TestResult",
]
