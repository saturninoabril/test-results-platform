"""
Unit tests for SQLAlchemy models.
Tests model validation, constraints, and business logic.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.models import (
    ArtifactType,
    TestArtifact,
    TestResult,
    TestStatus,
    TestSuite,
)


class TestTestSuiteModel:
    """Tests for TestSuite model."""

    def test_create_valid_suite(self):
        """Test creating a valid test suite."""
        now = datetime.now(UTC)
        suite = TestSuite(
            name="E2E Tests",
            total_tests=10,
            passed_tests=8,
            failed_tests=1,
            skipped_tests=1,
            duration_ms=5000,
            started_at=now,
            completed_at=now,
            framework_metadata={
                "name": "playwright",
                "version": "1.55.0",
                "config": {"browser": "chrome"},
            },
        )
        assert suite.name == "E2E Tests"
        assert suite.total_tests == 10
        assert suite.passed_tests == 8
        assert suite.failed_tests == 1
        assert suite.skipped_tests == 1
        assert suite.duration_ms == 5000

    def test_suite_name_validation(self):
        """Test suite name validation."""
        # Valid name
        suite = TestSuite(
            name="Test Suite",
            total_tests=0,
            passed_tests=0,
            failed_tests=0,
            skipped_tests=0,
            duration_ms=0,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        assert suite.name == "Test Suite"

        # Invalid name
        with pytest.raises(ValueError, match="Suite name cannot be empty"):
            TestSuite(
                name="",
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                skipped_tests=0,
                duration_ms=0,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )

    def test_suite_test_count_validation(self):
        """Test suite test count validation."""
        # Valid counts
        now = datetime.now(UTC)
        suite = TestSuite(
            name="Test",
            total_tests=5,
            passed_tests=3,
            failed_tests=1,
            skipped_tests=1,
            duration_ms=1000,
            started_at=now,
            completed_at=now,
        )
        suite.validate_consistency()  # Should not raise

        # Invalid negative counts
        with pytest.raises(ValueError, match="cannot be negative"):
            TestSuite(
                name="Test",
                total_tests=-1,
                passed_tests=0,
                failed_tests=0,
                skipped_tests=0,
                duration_ms=0,
                started_at=now,
                completed_at=now,
            )

    def test_suite_success_rate(self):
        """Test suite success rate calculation."""
        suite = TestSuite(
            name="Test",
            total_tests=10,
            passed_tests=8,
            failed_tests=2,
            skipped_tests=0,
            duration_ms=5000,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        assert suite.success_rate == 80.0

        # Zero tests
        suite.total_tests = 0
        suite.passed_tests = 0
        suite.failed_tests = 0
        assert suite.success_rate == 0.0

    def test_suite_duration_seconds(self):
        """Test duration conversion to seconds."""
        suite = TestSuite(
            name="Test",
            total_tests=1,
            passed_tests=1,
            failed_tests=0,
            skipped_tests=0,
            duration_ms=2500,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        assert suite.duration_seconds == 2.5


class TestTestResultModel:
    """Tests for TestResult model."""

    def test_create_valid_result(self):
        """Test creating a valid test result."""
        result = TestResult(
            suite_id=uuid4(),
            test_name="test should pass",
            full_title="Feature > Component > test should pass",
            status=TestStatus.PASSED,
            duration_ms=1000,
            tags=["smoke", "regression"],
            external_id="test-123",
            config_metadata={"retry": True},
        )
        assert result.test_name == "test should pass"
        assert result.status == TestStatus.PASSED
        assert result.duration_ms == 1000
        assert result.tags == ["smoke", "regression"]
        assert result.external_id == "test-123"

    def test_result_status_properties(self):
        """Test result status properties."""
        result = TestResult(
            suite_id=uuid4(),
            test_name="test",
            full_title="test",
            status=TestStatus.PASSED,
            duration_ms=1000,
        )
        assert result.is_passed is True
        assert result.is_failed is False
        assert result.is_skipped is False

        result.status = TestStatus.FAILED
        assert result.is_passed is False
        assert result.is_failed is True
        assert result.is_skipped is False

    def test_result_tags_validation(self):
        """Test result tags validation."""
        # Valid tags
        result = TestResult(
            suite_id=uuid4(),
            test_name="test",
            full_title="test",
            status=TestStatus.PASSED,
            duration_ms=1000,
            tags=["smoke", "regression"],
        )
        assert result.tags == ["smoke", "regression"]

        # Too many tags
        with pytest.raises(ValueError, match="Cannot have more than 20 tags"):
            TestResult(
                suite_id=uuid4(),
                test_name="test",
                full_title="test",
                status=TestStatus.PASSED,
                duration_ms=1000,
                tags=[f"tag{i}" for i in range(25)],
            )

    def test_result_has_tag(self):
        """Test has_tag method."""
        result = TestResult(
            suite_id=uuid4(),
            test_name="test",
            full_title="test",
            status=TestStatus.PASSED,
            duration_ms=1000,
            tags=["smoke", "REGRESSION"],
        )
        assert result.has_tag("smoke") is True
        assert result.has_tag("regression") is True  # Case insensitive
        assert result.has_tag("unit") is False

        # No tags
        result.tags = None
        assert result.has_tag("smoke") is False


class TestTestArtifactModel:
    """Tests for TestArtifact model."""

    def test_create_valid_artifact(self):
        """Test creating a valid test artifact."""
        artifact = TestArtifact(
            result_id=uuid4(),
            artifact_type=ArtifactType.SCREENSHOT,
            file_name="test-screenshot.png",
            file_size=1024,
            mime_type="image/png",
            storage_key="screenshots/test-123.png",
            checksum="a" * 64,
        )
        assert artifact.file_name == "test-screenshot.png"
        assert artifact.artifact_type == ArtifactType.SCREENSHOT
        assert artifact.file_size == 1024
        assert artifact.mime_type == "image/png"
        assert artifact.storage_key == "screenshots/test-123.png"

    def test_artifact_file_size_validation(self):
        """Test file size validation."""
        # Valid size
        artifact = TestArtifact(
            result_id=uuid4(),
            artifact_type=ArtifactType.SCREENSHOT,
            file_name="test.png",
            file_size=1024,
            mime_type="image/png",
            storage_key="test.png",
            checksum="a" * 64,
        )
        assert artifact.file_size == 1024

        # Invalid sizes
        with pytest.raises(ValueError, match="File size must be greater than 0"):
            TestArtifact(
                result_id=uuid4(),
                artifact_type=ArtifactType.SCREENSHOT,
                file_name="test.png",
                file_size=0,
                mime_type="image/png",
                storage_key="test.png",
                checksum="a" * 64,
            )

        with pytest.raises(ValueError, match="File size cannot exceed 100MB"):
            TestArtifact(
                result_id=uuid4(),
                artifact_type=ArtifactType.SCREENSHOT,
                file_name="test.png",
                file_size=101 * 1024 * 1024,  # 101MB
                mime_type="image/png",
                storage_key="test.png",
                checksum="a" * 64,
            )

    def test_artifact_checksum_validation(self):
        """Test checksum validation."""
        # Valid checksum
        artifact = TestArtifact(
            result_id=uuid4(),
            artifact_type=ArtifactType.SCREENSHOT,
            file_name="test.png",
            file_size=1024,
            mime_type="image/png",
            storage_key="test.png",
            checksum="a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
        )
        assert len(artifact.checksum) == 64

        # Invalid checksums
        with pytest.raises(ValueError, match="Checksum must be 64 characters"):
            TestArtifact(
                result_id=uuid4(),
                artifact_type=ArtifactType.SCREENSHOT,
                file_name="test.png",
                file_size=1024,
                mime_type="image/png",
                storage_key="test.png",
                checksum="short",
            )

        with pytest.raises(ValueError, match="Checksum must be valid hexadecimal"):
            TestArtifact(
                result_id=uuid4(),
                artifact_type=ArtifactType.SCREENSHOT,
                file_name="test.png",
                file_size=1024,
                mime_type="image/png",
                storage_key="test.png",
                checksum="g" * 64,  # Invalid hex character
            )

    def test_artifact_file_size_mb(self):
        """Test file size in MB calculation."""
        artifact = TestArtifact(
            result_id=uuid4(),
            artifact_type=ArtifactType.SCREENSHOT,
            file_name="test.png",
            file_size=2 * 1024 * 1024,  # 2MB
            mime_type="image/png",
            storage_key="test.png",
            checksum="a" * 64,
        )
        assert artifact.file_size_mb == 2.0

    def test_artifact_parent_validation(self):
        """Test parent relationship validation."""
        # Valid: has result_id
        artifact = TestArtifact(
            result_id=uuid4(),
            artifact_type=ArtifactType.SCREENSHOT,
            file_name="test.png",
            file_size=1024,
            mime_type="image/png",
            storage_key="test.png",
            checksum="a" * 64,
        )
        artifact.validate_parent_relationship()  # Should not raise

        # Valid: has suite_id
        artifact = TestArtifact(
            suite_id=uuid4(),
            artifact_type=ArtifactType.REPORT,
            file_name="report.html",
            file_size=1024,
            mime_type="text/html",
            storage_key="report.html",
            checksum="b" * 64,
        )
        artifact.validate_parent_relationship()  # Should not raise

        # Invalid: no parent
        artifact = TestArtifact(
            artifact_type=ArtifactType.SCREENSHOT,
            file_name="test.png",
            file_size=1024,
            mime_type="image/png",
            storage_key="test.png",
            checksum="a" * 64,
        )
        with pytest.raises(ValueError, match="must be associated with exactly one parent"):
            artifact.validate_parent_relationship()

        # Invalid: both parents
        artifact = TestArtifact(
            result_id=uuid4(),
            suite_id=uuid4(),
            artifact_type=ArtifactType.SCREENSHOT,
            file_name="test.png",
            file_size=1024,
            mime_type="image/png",
            storage_key="test.png",
            checksum="a" * 64,
        )
        with pytest.raises(ValueError, match="cannot be associated with multiple parents"):
            artifact.validate_parent_relationship()
