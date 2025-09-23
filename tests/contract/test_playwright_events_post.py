"""
Contract tests for POST /playwright/events endpoint.
These tests validate API contracts defined in OpenAPI specification.
Tests must FAIL initially (RED phase) - no implementation exists yet.
"""

from uuid import UUID

import pytest
from httpx import AsyncClient

# Apply pytest.mark.asyncio to all test methods in this module
pytestmark = pytest.mark.asyncio


class TestPlaywrightEventsPostContract:
    """Contract tests for POST /playwright/events endpoint."""

    async def test_create_test_event_success(self, client: AsyncClient):
        """Test POST /playwright/events with valid test_started event."""
        # Create a suite first
        suite_data = {
            "name": "Test Suite",
            "version": "1.55.0",
            "framework_metadata": {
                "name": "playwright",
                "version": "1.55.0",
            },
            "test_count": 1,
            "status": "running",
            "start_time": "2025-09-20T15:30:00Z",
        }
        suite_response = await client.post("/playwright/suites", json=suite_data)
        assert suite_response.status_code == 201
        suite_id = suite_response.json()["id"]

        event_data = {
            "suite_id": suite_id,
            "test_external_id": "test-auth-login",
            "event_type": "test_started",
            "timestamp": "2025-09-20T15:30:15Z",
            "data": {
                "testTitle": "should login successfully",
                "fullTitle": "Authentication › Login › should login successfully",
                "estimatedDuration": 5000,
                "retryIndex": 0,
            },
        }

        response = await client.post("/playwright/events", json=event_data)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert UUID(data["id"])
        assert data["suite_id"] == suite_id
        assert data["test_external_id"] == "test-auth-login"
        assert data["event_type"] == "test_started"
        assert data["timestamp"] == "2025-09-20T15:30:15Z"
        assert data["data"] == event_data["data"]

    async def test_create_suite_started_event(self, client: AsyncClient):
        """Test POST /playwright/events with suite_started event."""
        suite_response = await client.post(
            "/playwright/suites",
            json={
                "name": "Test Suite",
                "version": "1.55.0",
                "framework_metadata": {
                    "name": "playwright",
                    "version": "1.55.0",
                },
                "test_count": 150,
                "status": "running",
                "start_time": "2025-09-20T15:30:00Z",
            },
        )
        suite_id = suite_response.json()["id"]

        event_data = {
            "suite_id": suite_id,
            "event_type": "suite_started",
            "timestamp": "2025-09-20T15:30:00Z",
            "data": {
                "totalTests": 150,
                "estimatedDuration": 300000,
                "projects": ["chromium", "firefox"],
            },
        }

        response = await client.post("/playwright/events", json=event_data)

        assert response.status_code == 201
        data = response.json()
        assert data["event_type"] == "suite_started"
        assert data["test_external_id"] is None

    async def test_create_error_event(self, client: AsyncClient):
        """Test POST /playwright/events with error event."""
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

        event_data = {
            "suite_id": suite_id,
            "test_external_id": "failing-test",
            "event_type": "error",
            "timestamp": "2025-09-20T15:30:30Z",
            "data": {
                "errorType": "api_failure",
                "message": "Failed to upload artifact",
                "testTitle": "should upload screenshot",
                "recoverable": True,
            },
        }

        response = await client.post("/playwright/events", json=event_data)

        assert response.status_code == 201
        data = response.json()
        assert data["event_type"] == "error"

    async def test_create_event_invalid_suite_id(self, client: AsyncClient):
        """Test POST /playwright/events with non-existent suite_id."""
        from uuid import uuid4

        event_data = {
            "suite_id": str(uuid4()),  # Non-existent
            "event_type": "test_started",
            "timestamp": "2025-09-20T15:30:15Z",
        }

        response = await client.post("/playwright/events", json=event_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    async def test_create_event_invalid_event_type(self, client: AsyncClient):
        """Test POST /playwright/events with invalid event type."""
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

        event_data = {
            "suite_id": suite_id,
            "event_type": "invalid_event_type",  # Invalid
            "timestamp": "2025-09-20T15:30:15Z",
        }

        response = await client.post("/playwright/events", json=event_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("event_type" in str(error) for error in data["detail"])

    async def test_create_event_missing_required_fields(self, client: AsyncClient):
        """Test POST /playwright/events with missing required fields."""
        event_data = {
            "event_type": "test_started"
            # Missing: suite_id, timestamp
        }

        response = await client.post("/playwright/events", json=event_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        errors = data["detail"]
        required_fields = ["suite_id", "timestamp"]
        for field in required_fields:
            assert any(field in str(error) for error in errors)
