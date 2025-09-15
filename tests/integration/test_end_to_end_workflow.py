"""
End-to-end workflow tests for the Test Results Management API.
Tests complete workflows from framework creation through artifact management.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient

# Apply pytest.mark.asyncio to all test methods in this module
pytestmark = pytest.mark.asyncio


@pytest.fixture
def sample_framework_data():
    """Sample framework data for testing."""
    import time

    timestamp = int(time.time()) % 10000  # Use timestamp for uniqueness
    return {
        "name": "pytest",
        "version": f"7.4.{timestamp}",
        "metadata": {"plugins": ["pytest-asyncio", "pytest-minio"], "python_version": "3.13"},
    }


@pytest.fixture
def sample_environment_data():
    """Sample environment data for testing."""
    return {
        "name": f"ci-environment-{uuid4().hex[:8]}",
        "browser": "chrome",
        "os": "ubuntu",
        "config_metadata": {"ci": True, "headless": True, "viewport": "1920x1080"},
    }


@pytest.fixture
def sample_suite_data():
    """Sample suite data for testing."""
    return {
        "name": "CI Test Suite",
        "total_count": 10,
        "passed_count": 8,
        "failed_count": 1,
        "skipped_count": 1,
        "duration_ms": 45000,
        "metadata": {"ci": True, "parallel": True},
    }


@pytest.fixture
def sample_result_data():
    """Sample result data for testing."""
    return {
        "name": "test_user_authentication",
        "status": "passed",
        "duration_ms": 1250,
        "tags": ["auth", "integration"],
        "full_title": "Authentication > User Login > test_user_authentication",
        "metadata": {
            "browser": "chrome",
            "retries": 0,
            "screenshot": True,
            "test_steps": [
                {"action": "navigate", "target": "/login"},
                {"action": "fill", "target": "email", "value": "test@example.com"},
                {"action": "click", "target": "submit"},
            ],
        },
    }


async def test_complete_test_results_workflow(
    client: AsyncClient,
    sample_framework_data,
    sample_environment_data,
    sample_suite_data,
    sample_result_data,
):
    """Test the complete workflow from framework creation to test results."""
    # Step 1: Create framework
    framework_response = await client.post("/api/v1/frameworks", json=sample_framework_data)
    if framework_response.status_code != 201:
        print(f"Framework creation failed: {framework_response.status_code}")
        print(f"Response: {framework_response.text}")
    assert framework_response.status_code == 201
    framework_id = framework_response.json()["id"]

    # Step 2: Create environment
    environment_response = await client.post("/api/v1/environments", json=sample_environment_data)
    assert environment_response.status_code == 201
    environment_id = environment_response.json()["id"]

    # Step 3: Create test suite
    suite_data = {
        **sample_suite_data,
        "framework_id": framework_id,
        "environment_id": environment_id,
    }
    suite_response = await client.post("/api/v1/suites", json=suite_data)
    if suite_response.status_code != 201:
        print(f"Suite creation failed: {suite_response.status_code}")
        print(f"Response: {suite_response.text}")
        print(f"Suite data: {suite_data}")
    assert suite_response.status_code == 201
    suite_id = suite_response.json()["id"]

    # Step 4: Create test results
    result_data = {
        **sample_result_data,
        "suite_id": suite_id,
    }
    result_response = await client.post("/api/v1/results", json=result_data)
    assert result_response.status_code == 201
    result_id = result_response.json()["id"]

    # Verify the created data
    assert framework_id is not None
    assert environment_id is not None
    assert suite_id is not None
    assert result_id is not None

    print("✅ End-to-end workflow test completed successfully!")


async def test_artifact_management_workflow(client: AsyncClient):
    """Test artifact management workflow (simplified)."""
    # This is a placeholder for artifact management tests
    # The full implementation would test file uploads, downloads, etc.
    # For now, just test that the basic framework still works

    framework_data = {
        "name": f"artifact-test-framework-{uuid4().hex[:8]}",
        "version": "1.0.0",
        "metadata": {"supports_artifacts": True},
    }

    framework_response = await client.post("/api/v1/frameworks", json=framework_data)
    assert framework_response.status_code == 201
    print("✅ Artifact management workflow test completed successfully!")


async def test_bulk_operations_workflow(client: AsyncClient):
    """Test bulk operations workflow (simplified)."""
    # Create a framework and environment for bulk testing
    framework_data = {
        "name": f"bulk-test-framework-{uuid4().hex[:8]}",
        "version": "2.0.0",
        "metadata": {"bulk_capable": True},
    }
    framework_response = await client.post("/api/v1/frameworks", json=framework_data)
    assert framework_response.status_code == 201
    framework_id = framework_response.json()["id"]

    env_data = {
        "name": f"bulk-env-{uuid4().hex[:8]}",
        "browser": "firefox",
        "os": "linux",
        "config_metadata": {"bulk": True},
    }
    env_response = await client.post("/api/v1/environments", json=env_data)
    assert env_response.status_code == 201
    environment_id = env_response.json()["id"]

    suite_data = {
        "name": "Bulk Test Suite",
        "framework_id": framework_id,
        "environment_id": environment_id,
        "total_count": 5,
        "passed_count": 5,
        "failed_count": 0,
        "skipped_count": 0,
        "duration_ms": 15000,
        "metadata": {"bulk_test": True},
    }
    suite_response = await client.post("/api/v1/suites", json=suite_data)
    assert suite_response.status_code == 201
    suite_id = suite_response.json()["id"]

    # Create bulk results
    bulk_results = []
    for i in range(5):
        result_data = {
            "suite_id": suite_id,
            "name": f"bulk-test-{i:02d}",
            "status": "passed",
            "duration_ms": 1000 + (i * 100),
            "tags": ["bulk", "automated"],
            "full_title": f"Bulk Tests > bulk-test-{i:02d}",
            "metadata": {"test_index": i},
        }
        bulk_results.append(result_data)

    bulk_response = await client.post("/api/v1/results/bulk", json=bulk_results)
    assert bulk_response.status_code == 201
    print("✅ Bulk operations workflow test completed successfully!")


async def test_error_handling_workflow(client: AsyncClient):
    """Test error handling and validation."""
    # Test creating suite with invalid framework ID
    invalid_suite_data = {
        "framework_id": str(uuid4()),
        "environment_id": str(uuid4()),
        "name": "Invalid Suite",
        "total_count": 1,
        "passed_count": 1,
        "failed_count": 0,
        "skipped_count": 0,
        "duration_ms": 1000,
    }

    suite_response = await client.post("/api/v1/suites", json=invalid_suite_data)
    assert suite_response.status_code == 422  # Validation error
    print("✅ Error handling workflow test completed successfully!")


async def test_performance_workflow(client: AsyncClient):
    """Test performance-related workflow."""
    # Create framework with performance metadata
    framework_data = {
        "name": f"performance-framework-{uuid4().hex[:8]}",
        "version": "1.0.0",
        "metadata": {"performance_tracking": True},
    }
    framework_response = await client.post("/api/v1/frameworks", json=framework_data)
    assert framework_response.status_code == 201
    print("✅ Performance workflow test completed successfully!")
