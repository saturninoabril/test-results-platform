"""
Contract tests for POST /playwright/test-results endpoint.
These tests validate API contracts defined in OpenAPI specification.
Tests must FAIL initially (RED phase) - no implementation exists yet.
"""

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

# Apply pytest.mark.asyncio to all test methods in this module
pytestmark = pytest.mark.asyncio


class TestPlaywrightTestResultsPostContract:
    """Contract tests for POST /playwright/test-results endpoint."""

    async def test_create_test_result_success(self, client: AsyncClient):
        """Test POST /playwright/test-results with valid data."""
        # First create a suite
        suite_data = {
            "name": "Test Suite",
            "version": "1.55.0",
            "framework_metadata": {
                "name": "playwright",
                "version": "1.55.0",
                "type": "e2e_testing",
            },
            "test_count": 1,
            "status": "running",
            "start_time": "2025-09-20T15:30:00Z",
        }
        suite_response = await client.post("/playwright/suites", json=suite_data)
        assert suite_response.status_code == 201
        suite_id = suite_response.json()["id"]

        # Create test result
        test_result_data = {
            "suite_id": suite_id,
            "external_id": "test-auth-login-chrome",
            "title": "should login successfully",
            "full_title": "Authentication › Login › should login successfully",
            "status": "running",
            "location": {"file": "./tests/auth.spec.ts", "line": 15, "column": 3},
            "project_name": "Desktop Chrome",
            "timeout": 30000,
            "tags": ["smoke", "auth"],
            "start_time": "2025-09-20T15:30:15Z",
        }

        response = await client.post("/playwright/test-results", json=test_result_data)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert UUID(data["id"])  # Valid UUID
        assert data["suite_id"] == suite_id
        assert data["external_id"] == "test-auth-login-chrome"
        assert data["title"] == "should login successfully"
        assert data["full_title"] == "Authentication › Login › should login successfully"
        assert data["status"] == "running"
        assert data["location"] == test_result_data["location"]
        assert data["project_name"] == "Desktop Chrome"
        assert data["timeout"] == 30000
        assert data["tags"] == ["smoke", "auth"]
        assert data["start_time"] == "2025-09-20T15:30:15Z"
        assert "created_at" in data
        assert "updated_at" in data

    async def test_create_test_result_minimal_data(self, client: AsyncClient):
        """Test POST /playwright/test-results with minimal required data."""
        # Create dependencies
        suite_data = {
            "name": "Minimal Suite",
            "version": "1.55.0",
            "framework_metadata": {
                "name": "playwright",
                "version": "1.55.0",
                "type": "e2e_testing",
            },
            "test_count": 1,
            "status": "running",
            "start_time": "2025-09-20T15:30:00Z",
        }
        suite_response = await client.post("/playwright/suites", json=suite_data)
        suite_id = suite_response.json()["id"]

        # Minimal test result
        test_result_data = {
            "suite_id": suite_id,
            "title": "minimal test",
            "full_title": "minimal test",
            "status": "pending",
        }

        response = await client.post("/playwright/test-results", json=test_result_data)

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "minimal test"
        assert data["status"] == "pending"
        assert data["external_id"] is None
        assert data["location"] is None
        assert data["timeout"] is None

    async def test_create_test_result_with_retry_count(self, client: AsyncClient):
        """Test POST /playwright/test-results with retry information."""
        # Create dependencies
        suite_response = await client.post(
            "/playwright/suites",
            json={
                "name": "Retry Suite",
                "version": "1.55.0",
                "framework_metadata": {
                    "name": "playwright",
                    "version": "1.55.0",
                },
                "test_count": 1,
                "status": "running",
                "start_time": "2025-09-20T15:30:00Z",
            },
        )
        suite_id = suite_response.json()["id"]

        # Test result with retry
        test_result_data = {
            "suite_id": suite_id,
            "title": "flaky test",
            "full_title": "flaky test",
            "status": "running",
            "retry_count": 2,
        }

        response = await client.post("/playwright/test-results", json=test_result_data)

        assert response.status_code == 201
        data = response.json()
        assert data["retry_count"] == 2

    async def test_create_test_result_invalid_suite_id(self, client: AsyncClient):
        """Test POST /playwright/test-results with non-existent suite_id."""

        test_result_data = {
            "suite_id": str(uuid4()),  # Non-existent suite
            "title": "test",
            "full_title": "test",
            "status": "pending",
        }

        response = await client.post("/playwright/test-results", json=test_result_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("suite_id" in str(error) for error in data["detail"])

    async def test_create_test_result_invalid_status(self, client: AsyncClient):
        """Test POST /playwright/test-results with invalid status."""
        # Create dependencies
        suite_response = await client.post(
            "/playwright/suites",
            json={
                "name": "Test Suite",
                "version": "1.55.0",
                "framework_metadata": {
                    "name": "playwright",
                    "version": "1.55.0",
                },
                "test_count": 1,
                "status": "running",
                "start_time": "2025-09-20T15:30:00Z",
            },
        )
        suite_id = suite_response.json()["id"]

        test_result_data = {
            "suite_id": suite_id,
            "title": "test",
            "full_title": "test",
            "status": "invalid_status",  # Invalid status
        }

        response = await client.post("/playwright/test-results", json=test_result_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("status" in str(error) for error in data["detail"])

    async def test_create_test_result_negative_timeout(self, client: AsyncClient):
        """Test POST /playwright/test-results with negative timeout."""
        # Create dependencies
        suite_response = await client.post(
            "/playwright/suites",
            json={
                "name": "Test Suite",
                "version": "1.55.0",
                "framework_metadata": {
                    "name": "playwright",
                    "version": "1.55.0",
                },
                "test_count": 1,
                "status": "running",
                "start_time": "2025-09-20T15:30:00Z",
            },
        )
        suite_id = suite_response.json()["id"]

        test_result_data = {
            "suite_id": suite_id,
            "title": "test",
            "full_title": "test",
            "status": "pending",
            "timeout": -1000,  # Invalid: negative timeout
        }

        response = await client.post("/playwright/test-results", json=test_result_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("timeout" in str(error) for error in data["detail"])

    async def test_create_test_result_excessive_timeout(self, client: AsyncClient):
        """Test POST /playwright/test-results with excessive timeout."""
        # Create dependencies
        suite_response = await client.post(
            "/playwright/suites",
            json={
                "name": "Test Suite",
                "version": "1.55.0",
                "framework_metadata": {
                    "name": "playwright",
                    "version": "1.55.0",
                },
                "test_count": 1,
                "status": "running",
                "start_time": "2025-09-20T15:30:00Z",
            },
        )
        suite_id = suite_response.json()["id"]

        test_result_data = {
            "suite_id": suite_id,
            "title": "test",
            "full_title": "test",
            "status": "pending",
            "timeout": 3600001,  # Invalid: > 1 hour
        }

        response = await client.post("/playwright/test-results", json=test_result_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("timeout" in str(error) for error in data["detail"])

    async def test_create_test_result_missing_required_fields(self, client: AsyncClient):
        """Test POST /playwright/test-results with missing required fields."""
        test_result_data = {
            "title": "test"
            # Missing: suite_id, full_title, status
        }

        response = await client.post("/playwright/test-results", json=test_result_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        errors = data["detail"]
        required_fields = ["suite_id", "full_title", "status"]
        for field in required_fields:
            assert any(field in str(error) for error in errors), (
                f"Missing validation for required field: {field}"
            )

    async def test_create_test_result_too_many_tags(self, client: AsyncClient):
        """Test POST /playwright/test-results with too many tags."""
        # Create dependencies
        suite_response = await client.post(
            "/playwright/suites",
            json={
                "name": "Test Suite",
                "version": "1.55.0",
                "framework_metadata": {
                    "name": "playwright",
                    "version": "1.55.0",
                },
                "test_count": 1,
                "status": "running",
                "start_time": "2025-09-20T15:30:00Z",
            },
        )
        suite_id = suite_response.json()["id"]

        test_result_data = {
            "suite_id": suite_id,
            "title": "test",
            "full_title": "test",
            "status": "pending",
            "tags": [f"tag{i}" for i in range(25)],  # Too many tags (>20)
        }

        response = await client.post("/playwright/test-results", json=test_result_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("tags" in str(error) for error in data["detail"])

    async def test_create_test_result_invalid_location_format(self, client: AsyncClient):
        """Test POST /playwright/test-results with invalid location format."""
        # Create dependencies
        suite_response = await client.post(
            "/playwright/suites",
            json={
                "name": "Test Suite",
                "version": "1.55.0",
                "framework_metadata": {
                    "name": "playwright",
                    "version": "1.55.0",
                },
                "test_count": 1,
                "status": "running",
                "start_time": "2025-09-20T15:30:00Z",
            },
        )
        suite_id = suite_response.json()["id"]

        test_result_data = {
            "suite_id": suite_id,
            "title": "test",
            "full_title": "test",
            "status": "pending",
            "location": "invalid-location-format",  # Should be object
        }

        response = await client.post("/playwright/test-results", json=test_result_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("location" in str(error) for error in data["detail"])
