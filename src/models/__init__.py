"""
SQLAlchemy models for the Test Results Management API.
Provides data models for test frameworks, environments, suites, results, and artifacts.
"""

from .base import Base, BaseModel, TimestampMixin, UUIDMixin
from .test_framework import TestFramework
from .test_environment import TestEnvironment
from .test_suite import TestSuite
from .test_result import TestResult, TestStatus
from .test_artifact import TestArtifact, ArtifactType

__all__ = [
    "Base",
    "BaseModel",
    "TimestampMixin",
    "UUIDMixin",
    "TestFramework",
    "TestEnvironment",
    "TestSuite",
    "TestResult",
    "TestStatus",
    "TestArtifact",
    "ArtifactType",
]