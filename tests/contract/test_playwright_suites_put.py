"""
Contract tests for PUT /playwright/suites/{suite_id} endpoint.
These tests validate API contracts defined in OpenAPI specification.
Tests must FAIL initially (RED phase) - no implementation exists yet.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient

# Apply pytest.mark.asyncio to all test methods in this module
pytestmark = pytest.mark.asyncio


class TestPlaywrightSuitesPutContract:
    """Contract tests for PUT /playwright/suites/{suite_id} endpoint."""

    async def test_update_suite_success(self, client: AsyncClient):
        """Test PUT /playwright/suites/{suite_id} with valid data."""
        # First create a suite
        suite_data = {
            "name": "Test Suite",
            "version": "1.55.0",
            "framework_metadata": {
                "name": "playwright",
                "version": "1.55.0",
                "type": "e2e_testing",
            },
            "test_count": 10,
            "status": "running",
            "start_time": "2025-09-20T15:30:00Z",
        }
        create_response = await client.post("/playwright/suites", json=suite_data)
        assert create_response.status_code == 201
        suite_id = create_response.json()["id"]

        # Update the suite
        update_data = {
            "status": "passed",
            "end_time": "2025-09-20T15:35:00Z",
            "duration": 300000,  # 5 minutes in milliseconds
        }

        response = await client.put(f"/playwright/suites/{suite_id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == suite_id
        assert data["status"] == "passed"
        assert data["end_time"] == "2025-09-20T15:35:00Z"
        assert data["duration"] == 300000
        assert "updated_at" in data

    async def test_update_suite_to_failed(self, client: AsyncClient):
        """Test PUT /playwright/suites/{suite_id} updating to failed status."""
        # Create a running suite
        suite_data = {
            "name": "Failing Test Suite",
            "version": "1.55.0",
            "framework_metadata": {
                "name": "playwright",
                "version": "1.55.0",
                "type": "e2e_testing",
            },
            "test_count": 5,
            "status": "running",
            "start_time": "2025-09-20T15:30:00Z",
        }
        create_response = await client.post("/playwright/suites", json=suite_data)
        assert create_response.status_code == 201
        suite_id = create_response.json()["id"]

        # Update to failed
        update_data = {
            "status": "failed",
            "end_time": "2025-09-20T15:32:00Z",
            "duration": 120000,  # 2 minutes
        }

        response = await client.put(f"/playwright/suites/{suite_id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["end_time"] == "2025-09-20T15:32:00Z"
        assert data["duration"] == 120000

    async def test_update_suite_to_interrupted(self, client: AsyncClient):
        """Test PUT /playwright/suites/{suite_id} updating to interrupted status."""
        # Create a running suite
        suite_data = {
            "name": "Interrupted Test Suite",
            "version": "1.55.0",
            "framework_metadata": {
                "name": "playwright",
                "version": "1.55.0",
                "type": "e2e_testing",
            },
            "test_count": 20,
            "status": "running",
            "start_time": "2025-09-20T15:30:00Z",
        }
        create_response = await client.post("/playwright/suites", json=suite_data)
        assert create_response.status_code == 201
        suite_id = create_response.json()["id"]

        # Update to interrupted
        update_data = {
            "status": "interrupted",
            "end_time": "2025-09-20T15:31:00Z",
            "duration": 60000,  # 1 minute
        }

        response = await client.put(f"/playwright/suites/{suite_id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "interrupted"

    async def test_update_suite_not_found(self, client: AsyncClient):
        """Test PUT /playwright/suites/{suite_id} with non-existent ID."""
        non_existent_id = str(uuid4())
        update_data = {"status": "passed", "end_time": "2025-09-20T15:35:00Z", "duration": 300000}

        response = await client.put(f"/playwright/suites/{non_existent_id}", json=update_data)

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    async def test_update_suite_invalid_uuid(self, client: AsyncClient):
        """Test PUT /playwright/suites/{suite_id} with invalid UUID."""
        invalid_id = "not-a-uuid"
        update_data = {"status": "passed", "end_time": "2025-09-20T15:35:00Z"}

        response = await client.put(f"/playwright/suites/{invalid_id}", json=update_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    async def test_update_suite_invalid_status(self, client: AsyncClient):
        """Test PUT /playwright/suites/{suite_id} with invalid status."""
        # Create a suite first
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
        create_response = await client.post("/playwright/suites", json=suite_data)
        assert create_response.status_code == 201
        suite_id = create_response.json()["id"]

        # Try to update with invalid status
        update_data = {
            "status": "invalid_status",  # Invalid
            "end_time": "2025-09-20T15:35:00Z",
        }

        response = await client.put(f"/playwright/suites/{suite_id}", json=update_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("status" in str(error) for error in data["detail"])

    async def test_update_suite_end_time_before_start_time(self, client: AsyncClient):
        """Test PUT /playwright/suites/{suite_id} with end_time before start_time."""
        # Create a suite with start_time
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
        create_response = await client.post("/playwright/suites", json=suite_data)
        assert create_response.status_code == 201
        suite_id = create_response.json()["id"]

        # Try to update with end_time before start_time
        update_data = {
            "status": "passed",
            "end_time": "2025-09-20T15:25:00Z",  # Before start_time
        }

        response = await client.put(f"/playwright/suites/{suite_id}", json=update_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    async def test_update_suite_negative_duration(self, client: AsyncClient):
        """Test PUT /playwright/suites/{suite_id} with negative duration."""
        # Create a suite
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
        create_response = await client.post("/playwright/suites", json=suite_data)
        assert create_response.status_code == 201
        suite_id = create_response.json()["id"]

        # Try to update with negative duration
        update_data = {
            "status": "passed",
            "end_time": "2025-09-20T15:35:00Z",
            "duration": -1000,  # Negative duration
        }

        response = await client.put(f"/playwright/suites/{suite_id}", json=update_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("duration" in str(error) for error in data["detail"])

    async def test_update_suite_invalid_datetime_format(self, client: AsyncClient):
        """Test PUT /playwright/suites/{suite_id} with invalid datetime format."""
        # Create a suite
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
        create_response = await client.post("/playwright/suites", json=suite_data)
        assert create_response.status_code == 201
        suite_id = create_response.json()["id"]

        # Try to update with invalid datetime
        update_data = {
            "status": "passed",
            "end_time": "not-a-datetime",  # Invalid format
        }

        response = await client.put(f"/playwright/suites/{suite_id}", json=update_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("end_time" in str(error) for error in data["detail"])

    async def test_update_suite_partial_update(self, client: AsyncClient):
        """Test PUT /playwright/suites/{suite_id} with partial data update."""
        # Create a suite
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
        create_response = await client.post("/playwright/suites", json=suite_data)
        assert create_response.status_code == 201
        suite_id = create_response.json()["id"]

        # Update only status (partial update)
        update_data = {"status": "passed"}

        response = await client.put(f"/playwright/suites/{suite_id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "passed"
        # Other fields should remain unchanged
        assert data["name"] == "Test Suite"
        assert data["test_count"] == 1

    async def test_update_suite_empty_request_body(self, client: AsyncClient):
        """Test PUT /playwright/suites/{suite_id} with empty request body."""
        # Create a suite
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
        create_response = await client.post("/playwright/suites", json=suite_data)
        assert create_response.status_code == 201
        suite_id = create_response.json()["id"]

        # Try to update with empty body
        update_data = {}

        response = await client.put(f"/playwright/suites/{suite_id}", json=update_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
