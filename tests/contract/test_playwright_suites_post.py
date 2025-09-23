"""
Contract tests for POST /playwright/suites endpoint.
These tests validate API contracts defined in OpenAPI specification.
Tests must FAIL initially (RED phase) - no implementation exists yet.
"""

from uuid import UUID

import pytest
from httpx import AsyncClient

from src.lib.middleware import get_current_context

# Apply pytest.mark.asyncio to all test methods in this module
pytestmark = pytest.mark.asyncio


class TestPlaywrightSuitesPostContract:
    """Contract tests for POST /playwright/suites endpoint."""

    async def test_create_suite_success(self, client: AsyncClient):
        """Test POST /playwright/suites with valid data."""
        suite_data = {
            "name": "Playwright E2E Test Suite - 2025-09-20T15:30:00Z",
            "version": "1.55.0",
            "test_count": 150,
            "status": "running",
            "start_time": "2025-09-20T15:30:00Z",
            "framework_metadata": {
                "name": "playwright",
                "version": "1.55.0",
                "workers": 4,
                "fullyParallel": True,
                "retries": 2,
                "timeout": 30000,
                "projects": ["chromium", "firefox", "webkit"],
            },
        }

        response = await client.post("/playwright/suites", json=suite_data)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert UUID(data["id"])  # Valid UUID
        assert data["name"] == suite_data["name"]
        assert data["test_count"] == 150
        assert data["status"] == "running"
        assert data["start_time"] == "2025-09-20T15:30:00Z"
        # Verify framework metadata includes both service-added info and user-provided config
        assert data.get("framework_metadata", {}).get("name") == "playwright"
        assert data["framework_metadata"]["version"] == "1.55.0"
        # Verify user-provided framework metadata is preserved
        assert data["framework_metadata"]["workers"] == 4
        assert data["framework_metadata"]["fullyParallel"] is True
        assert data["framework_metadata"]["retries"] == 2
        assert data["framework_metadata"]["timeout"] == 30000
        assert data["framework_metadata"]["projects"] == ["chromium", "firefox", "webkit"]
        # Verify new metadata fields are present (should be None since not provided)
        assert data.get("environment_metadata") is None
        assert data.get("server_metadata") is None
        assert data.get("ci_run_metadata") is None
        assert data.get("playwright_test_files") is None
        assert "created_at" in data
        assert "updated_at" in data

    async def test_create_suite_minimal_data(self, client: AsyncClient):
        """Test POST /playwright/suites with minimal required data."""
        suite_data = {
            "name": "Minimal Test Suite",
            "version": "1.55.0",
            "framework_metadata": {
                "name": "playwright",
                "version": "1.55.0",
                "type": "e2e_testing",
            },
            "test_count": 1,
            "status": "created",
            "start_time": "2025-09-20T15:30:00Z",
        }

        response = await client.post("/playwright/suites", json=suite_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal Test Suite"
        assert data["test_count"] == 1
        assert data["status"] == "created"
        # Framework metadata should be created automatically with framework info
        assert data.get("framework_metadata", {}).get("name") == "playwright"
        assert data["framework_metadata"]["version"] == "1.55.0"
        # Other metadata fields should be None for minimal data
        assert data.get("environment_metadata") is None
        assert data.get("server_metadata") is None
        assert data.get("ci_run_metadata") is None
        assert data.get("playwright_test_files") is None

    async def test_create_suite_without_framework_field(self, client: AsyncClient):
        """Test POST /playwright/suites without framework field (framework info in metadata)."""
        suite_data = {
            "name": "Test Suite Without Framework Field",
            "version": "1.55.0",
            "test_count": 1,
            "status": "created",
            "start_time": "2025-09-20T15:30:00Z",
            "framework_metadata": {
                "name": "playwright",
                "version": "1.55.0",
            },
        }

        response = await client.post("/playwright/suites", json=suite_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Suite Without Framework Field"
        assert data["test_count"] == 1
        assert data["status"] == "created"
        # Framework metadata should still be created automatically from the provided framework_metadata
        # Note: framework and version are now only stored in framework_metadata, not as top-level fields

    async def test_create_suite_with_all_metadata_fields(self, client: AsyncClient):
        """Test POST /playwright/suites with all metadata fields."""
        suite_data = {
            "name": "Complete Metadata Test Suite",
            "version": "1.55.0",
            "test_count": 25,
            "status": "running",
            "start_time": "2025-09-21T15:30:00Z",
            "framework_metadata": {
                "name": "playwright",
                "version": "1.55.0",
                "browser_engines": ["chromium", "firefox", "webkit"],
                "test_runner": "playwright-test",
                "config": {"timeout": 30000, "retries": 3},
                "suite_config": {"timeout": 30000, "retries": 3},
            },
            "environment_metadata": {
                "os": "linux",
                "node_version": "18.17.0",
                "ci_provider": "github_actions",
            },
            "server_metadata": {
                "hostname": "test-runner-01",
                "region": "us-west-2",
                "instance_type": "large",
            },
            "ci_run_metadata": {
                "build_id": "12345",
                "commit_sha": "abc123def456",
                "pr_number": 789,
                "branch": "feature/test-improvements",
            },
            "playwright_test_files": {
                "total_files": 15,
                "test_files": [
                    {"file": "tests/auth.spec.ts", "tests": 5},
                    {"file": "tests/dashboard.spec.ts", "tests": 8},
                    {"file": "tests/settings.spec.ts", "tests": 12},
                ],
                "coverage": {"lines": 85.2, "functions": 90.1},
            },
        }

        response = await client.post("/playwright/suites", json=suite_data)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert UUID(data["id"])  # Valid UUID
        assert data["name"] == suite_data["name"]
        assert data["test_count"] == 25
        assert data["status"] == "running"
        assert data["start_time"] == "2025-09-21T15:30:00Z"

        # Verify new metadata fields are stored correctly
        assert data["environment_metadata"] == suite_data["environment_metadata"]
        assert data["server_metadata"] == suite_data["server_metadata"]
        assert data["ci_run_metadata"] == suite_data["ci_run_metadata"]
        assert data["playwright_test_files"] == suite_data["playwright_test_files"]

        # Verify framework metadata includes user-provided config
        # Note: The service now passes through the framework_metadata as-is
        assert (
            data["framework_metadata"]["browser_engines"]
            == suite_data["framework_metadata"]["browser_engines"]
        )
        assert (
            data["framework_metadata"]["test_runner"]
            == suite_data["framework_metadata"]["test_runner"]
        )
        assert data["framework_metadata"]["config"] == suite_data["framework_metadata"]["config"]
        assert (
            data["framework_metadata"]["suite_config"]
            == suite_data["framework_metadata"]["suite_config"]
        )

        assert "created_at" in data
        assert "updated_at" in data

    async def test_create_suite_invalid_framework_metadata(self, client: AsyncClient):
        """Test POST /playwright/suites with non-playwright framework in metadata."""
        suite_data = {
            "name": "Test Suite",
            "version": "1.55.0",
            "test_count": 1,
            "status": "created",
            "start_time": "2025-09-20T15:30:00Z",
            "framework_metadata": {
                "name": "cypress",  # Invalid: should be 'playwright'
                "version": "1.55.0",
            },
        }

        response = await client.post("/playwright/suites", json=suite_data)

        assert response.status_code == 422

    async def test_create_suite_invalid_status(self, client: AsyncClient):
        """Test POST /playwright/suites with invalid status."""
        suite_data = {
            "name": "Test Suite",
            "version": "1.55.0",
            "framework_metadata": {
                "name": "playwright",
                "version": "1.55.0",
                "type": "e2e_testing",
            },
            "test_count": 1,
            "status": "invalid_status",  # Invalid status
            "start_time": "2025-09-20T15:30:00Z",
        }

        response = await client.post("/playwright/suites", json=suite_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("status" in str(error) for error in data["detail"])

    async def test_create_suite_negative_test_count(self, client: AsyncClient):
        """Test POST /playwright/suites with negative test count."""
        suite_data = {
            "name": "Test Suite",
            "version": "1.55.0",
            "framework_metadata": {
                "name": "playwright",
                "version": "1.55.0",
                "type": "e2e_testing",
            },
            "test_count": -1,  # Invalid: negative
            "status": "created",
            "start_time": "2025-09-20T15:30:00Z",
        }

        response = await client.post("/playwright/suites", json=suite_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("test_count" in str(error) for error in data["detail"])

    async def test_create_suite_missing_required_fields(self, client: AsyncClient):
        """Test POST /playwright/suites with missing required fields."""
        suite_data = {
            "name": "playwright",
            # Missing: version, test_count, status, start_time
        }

        response = await client.post("/playwright/suites", json=suite_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        errors = data["detail"]
        required_fields = ["version", "test_count", "status", "start_time"]
        for field in required_fields:
            assert any(field in str(error) for error in errors), (
                f"Missing validation for required field: {field}"
            )

    async def test_create_suite_invalid_datetime_format(self, client: AsyncClient):
        """Test POST /playwright/suites with invalid datetime format."""
        suite_data = {
            "name": "Test Suite",
            "version": "1.55.0",
            "framework_metadata": {
                "name": "playwright",
                "version": "1.55.0",
                "type": "e2e_testing",
            },
            "test_count": 1,
            "status": "created",
            "start_time": "not-a-datetime",  # Invalid datetime format
        }

        response = await client.post("/playwright/suites", json=suite_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("start_time" in str(error) for error in data["detail"])

    async def test_create_suite_empty_name(self, client: AsyncClient):
        """Test POST /playwright/suites with empty name."""
        suite_data = {
            "name": "",  # Invalid: empty name
            "version": "1.55.0",
            "framework_metadata": {
                "name": "playwright",
                "version": "1.55.0",
                "type": "e2e_testing",
            },
            "test_count": 1,
            "status": "created",
            "start_time": "2025-09-20T15:30:00Z",
        }

        response = await client.post("/playwright/suites", json=suite_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("name" in str(error) for error in data["detail"])

    async def test_create_suite_invalid_framework_metadata_format(self, client: AsyncClient):
        """Test POST /playwright/suites with invalid framework_metadata format."""
        suite_data = {
            "name": "Test Suite",
            "version": "1.55.0",
            "test_count": 1,
            "status": "created",
            "start_time": "2025-09-20T15:30:00Z",
            "framework_metadata": "invalid-metadata",  # Should be object, not string
        }

        response = await client.post("/playwright/suites", json=suite_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("framework_metadata" in str(error) for error in data["detail"])

    async def test_create_suite_with_end_time_before_start_time(self, client: AsyncClient):
        """Test POST /playwright/suites with end_time before start_time."""
        suite_data = {
            "name": "Test Suite",
            "version": "1.55.0",
            "framework_metadata": {
                "name": "playwright",
                "version": "1.55.0",
                "type": "e2e_testing",
            },
            "test_count": 1,
            "status": "created",
            "start_time": "2025-09-20T15:30:00Z",
            "end_time": "2025-09-20T15:25:00Z",  # Before start_time
        }

        response = await client.post("/playwright/suites", json=suite_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        # Should validate that end_time >= start_time

    async def test_create_suite_public_access(self, client: AsyncClient):
        """Test POST /playwright/suites works without authentication (public API for CI/CD)."""
        # Remove authentication override to test public access
        from src.main import app

        app.dependency_overrides.clear()

        suite_data = {
            "name": "Test Suite",
            "version": "1.55.0",
            "framework_metadata": {
                "name": "playwright",
                "version": "1.55.0",
                "type": "e2e_testing",
            },
            "test_count": 1,
            "status": "created",
            "start_time": "2025-09-20T15:30:00Z",
        }

        response = await client.post("/playwright/suites", json=suite_data)

        # Playwright API should work without authentication for CI/CD automation
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == "Test Suite"

        # Restore mock authentication
        def mock_auth():
            from datetime import datetime, timedelta
            from zoneinfo import ZoneInfo

            from src.lib.auth import TokenClaims, TokenScope, TokenType
            from src.lib.middleware import AuthenticatedUser, UserRole

            UTC = ZoneInfo("UTC")
            claims = TokenClaims(
                sub="test:user:contract",
                exp=datetime.now(UTC) + timedelta(hours=1),
                scope=TokenScope.USER,
                token_type=TokenType.ACCESS,
                username="contract_user",
                email="contract@example.com",
                role=UserRole.ADMIN,
            )
            return AuthenticatedUser(
                user_id="test:user:contract",
                username="contract_user",
                email="contract@example.com",
                role=UserRole.ADMIN,
                permissions=["suites:write"],
                token_claims=claims,
            )

        app.dependency_overrides[get_current_context] = mock_auth
