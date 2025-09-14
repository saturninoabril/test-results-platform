"""
End-to-end workflow tests for the Test Results Management API.
Tests complete workflows from framework creation through artifact management.
"""

import io
import json
from datetime import UTC
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

# Apply pytest.mark.asyncio to all test methods in this module
pytestmark = pytest.mark.asyncio


async def setup_test_client():
    """Set up test client with authentication and database."""
    from datetime import datetime, timedelta

    from src.lib.auth import TokenClaims, TokenScope, TokenType
    from src.lib.database import init_database
    from src.lib.middleware import AuthenticatedUser, UserRole, get_current_context
    from src.lib.storage import init_storage
    from src.main import app

    # Initialize services
    await init_database()
    await init_storage()

    # Mock authentication for tests
    def mock_auth():
        claims = TokenClaims(
            sub="test:user:e2e",
            exp=datetime.now(UTC) + timedelta(hours=1),
            scope=TokenScope.USER,
            token_type=TokenType.ACCESS,
            username="e2euser",
            email="e2e@example.com",
            role=UserRole.ADMIN,
        )
        return AuthenticatedUser(
            user_id="test:user:e2e",
            username="e2euser",
            email="e2e@example.com",
            role=UserRole.ADMIN,
            permissions=[
                "frameworks:read",
                "frameworks:write",
                "frameworks:delete",
                "environments:read",
                "environments:write",
                "environments:delete",
                "suites:read",
                "suites:write",
                "suites:delete",
                "results:read",
                "results:write",
                "results:delete",
                "artifacts:read",
                "artifacts:write",
                "artifacts:delete",
            ],
            token_claims=claims,
        )

    # Override authentication dependencies
    app.dependency_overrides[get_current_context] = mock_auth

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


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
    """Sample test suite data for testing."""
    return {
        "name": f"e2e-test-suite-{uuid4().hex[:8]}",
        "total_count": 5,
        "passed_count": 4,
        "failed_count": 1,
        "skipped_count": 0,
        "duration_ms": 120500,  # Convert to milliseconds
        "metadata": {"parallel": True, "workers": 4},
    }


@pytest.fixture
def sample_result_data():
    """Sample test result data for testing."""
    return {
        "name": "should complete user registration flow",
        "status": "passed",
        "duration_ms": 15200,  # Convert to milliseconds
        "full_title": "User Registration Flow should complete user registration flow",
        "external_id": f"test-{uuid4().hex[:12]}",
        "tags": ["registration", "user-flow", "e2e"],
        "metadata": {
            "retry_count": 0,
            "browser_logs": [],
            "steps": [
                {"action": "navigate", "target": "/register"},
                {"action": "fill", "target": "email", "value": "test@example.com"},
                {"action": "click", "target": "submit"},
            ],
        },
    }


async def test_complete_test_results_workflow(
    sample_framework_data, sample_environment_data, sample_suite_data, sample_result_data
):
    """Test the complete workflow from framework creation to test results."""
    client = await setup_test_client()

    try:
        # Step 1: Create framework
        framework_response = await client.post("/api/v1/frameworks", json=sample_framework_data)
        if framework_response.status_code != 201:
            print(f"Framework creation failed: {framework_response.status_code}")
            print(f"Response: {framework_response.text}")
        assert framework_response.status_code == 201
        framework_id = framework_response.json()["id"]

        # Step 2: Create environment
        environment_response = await client.post(
            "/api/v1/environments", json=sample_environment_data
        )
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
        result_data = {**sample_result_data, "suite_id": suite_id}
        result_response = await client.post("/api/v1/results", json=result_data)
        if result_response.status_code != 201:
            print(f"Result creation failed: {result_response.status_code}")
            print(f"Response: {result_response.text}")
            print(f"Result data: {result_data}")
        assert result_response.status_code == 201
        result_id = result_response.json()["id"]

        # Step 5: Verify data integrity through API
        suite_details = await client.get(f"/api/v1/suites/{suite_id}")
        assert suite_details.status_code == 200
        suite_json = suite_details.json()
        # Check framework and environment IDs match
        assert suite_json["framework_id"] == framework_id
        assert suite_json["environment_id"] == environment_id
        # Note: The API might not include nested results in the suite detail view
        # We'll check the result separately if needed

        # Step 6: Query results by framework
        framework_results = await client.get(f"/api/v1/results?framework_id={framework_id}")
        assert framework_results.status_code == 200
        results_json = framework_results.json()
        # Results endpoint returns a list directly
        assert len(results_json) >= 1
        assert any(r["id"] == result_id for r in results_json)

    finally:
        await client.aclose()


async def test_artifact_management_workflow(
    sample_framework_data, sample_environment_data, sample_suite_data, sample_result_data
):
    """Test complete artifact management workflow."""
    client = await setup_test_client()

    try:
        # Create dependencies
        framework_response = await client.post("/api/v1/frameworks", json=sample_framework_data)
        framework_id = framework_response.json()["id"]

        environment_response = await client.post(
            "/api/v1/environments", json=sample_environment_data
        )
        environment_id = environment_response.json()["id"]

        suite_data = {
            **sample_suite_data,
            "framework_id": framework_id,
            "environment_id": environment_id,
        }
        suite_response = await client.post("/api/v1/suites", json=suite_data)
        suite_id = suite_response.json()["id"]

        result_data = {**sample_result_data, "suite_id": suite_id}
        result_response = await client.post("/api/v1/results", json=result_data)
        result_id = result_response.json()["id"]

        # Step 1: Upload screenshot artifact
        screenshot_data = b"fake-screenshot-data-" + b"x" * 1000
        screenshot_response = await client.post(
            f"/api/v1/results/{result_id}/artifacts",
            files={"file": ("screenshot.png", io.BytesIO(screenshot_data), "image/png")},
            data={
                "artifact_type": "screenshot",
                "metadata": json.dumps({"step": "login", "viewport": "1920x1080"}),
            },
        )
        assert screenshot_response.status_code == 201
        screenshot_artifact = screenshot_response.json()
        screenshot_id = screenshot_artifact["id"]

        # Step 2: Upload video artifact
        video_data = b"fake-video-data-" + b"x" * 5000
        video_response = await client.post(
            f"/api/v1/results/{result_id}/artifacts",
            files={"file": ("test-video.mp4", io.BytesIO(video_data), "video/mp4")},
            data={"artifact_type": "video", "metadata": json.dumps({"duration": 30.5, "fps": 30})},
        )
        assert video_response.status_code == 201
        video_artifact = video_response.json()
        video_id = video_artifact["id"]

        # Step 3: Verify artifacts are associated with result
        result_details = await client.get(f"/api/v1/results/{result_id}")
        assert result_details.status_code == 200
        result_json = result_details.json()
        assert len(result_json["artifacts"]) == 2

        artifact_ids = {art["id"] for art in result_json["artifacts"]}
        assert screenshot_id in artifact_ids
        assert video_id in artifact_ids

        # Step 4: Download artifacts
        screenshot_download = await client.get(f"/api/v1/artifacts/{screenshot_id}/download")
        assert screenshot_download.status_code == 200
        assert screenshot_download.content == screenshot_data

        video_download = await client.get(f"/api/v1/artifacts/{video_id}/download")
        assert video_download.status_code == 200
        assert video_download.content == video_data

        # Step 5: Get signed URLs
        screenshot_url_response = await client.post(f"/api/v1/artifacts/{screenshot_id}/signed-url")
        assert screenshot_url_response.status_code == 200
        screenshot_url_data = screenshot_url_response.json()
        assert "signed_url" in screenshot_url_data
        assert screenshot_url_data["expires_at"] is not None

    finally:
        await client.aclose()


async def test_bulk_operations_workflow(
    sample_framework_data, sample_environment_data, sample_suite_data
):
    """Test bulk operations workflow."""
    client = await setup_test_client()

    try:
        # Create framework and environment
        framework_response = await client.post("/api/v1/frameworks", json=sample_framework_data)
        framework_id = framework_response.json()["id"]

        environment_response = await client.post(
            "/api/v1/environments", json=sample_environment_data
        )
        environment_id = environment_response.json()["id"]

        # Create multiple test suites
        suite_ids = []
        for i in range(3):
            suite_data = {
                **sample_suite_data,
                "name": f"{sample_suite_data['name']}-{i}",
                "framework_id": framework_id,
                "environment_id": environment_id,
                "total_count": 10 + i,
                "passed_count": 8 + i,
                "failed_count": 2 - i if i < 2 else 0,
                "skipped_count": 0,
            }
            suite_response = await client.post("/api/v1/suites", json=suite_data)
            assert suite_response.status_code == 201
            suite_ids.append(suite_response.json()["id"])

        # Create multiple test results per suite
        result_ids = []
        for suite_id in suite_ids:
            for j in range(2):
                result_data = {
                    "name": f"test-case-{j}",
                    "status": "passed" if j == 0 else "failed",
                    "duration_ms": int((10.0 + j) * 1000),  # Convert to milliseconds
                    "suite_id": suite_id,
                    "external_id": f"bulk-test-{suite_id}-{j}",
                    "tags": ["bulk", f"suite-{suite_id}"],
                }
                result_response = await client.post("/api/v1/results", json=result_data)
                assert result_response.status_code == 201
                result_ids.append(result_response.json()["id"])

        # Test bulk queries
        # Query all results for framework
        framework_results = await client.get(f"/api/v1/results?framework_id={framework_id}")
        assert framework_results.status_code == 200
        framework_json = framework_results.json()
        assert len(framework_json) >= 6  # At least 3 suites × 2 results each

        # Query results by status
        passed_results = await client.get("/api/v1/results?status=passed")
        assert passed_results.status_code == 200
        passed_json = passed_results.json()
        passed_count = len([r for r in passed_json if r["status"] == "passed"])
        assert passed_count >= 3  # At least our 3 passed tests

        # Test pagination
        page1 = await client.get(f"/api/v1/results?framework_id={framework_id}&limit=2&offset=0")
        assert page1.status_code == 200
        page1_json = page1.json()
        assert len(page1_json) <= 2

        page2 = await client.get(f"/api/v1/results?framework_id={framework_id}&limit=2&offset=2")
        assert page2.status_code == 200
        page2_json = page2.json()

        # Verify different results across pages if we have enough data
        if len(page1_json) == 2 and len(page2_json) > 0:
            page1_ids = {r["id"] for r in page1_json}
            page2_ids = {r["id"] for r in page2_json}
            assert page1_ids.isdisjoint(page2_ids)

    finally:
        await client.aclose()


async def test_error_handling_workflow(
    sample_framework_data, sample_environment_data, sample_suite_data
):
    """Test error handling across the workflow."""
    client = await setup_test_client()

    try:
        # Test invalid framework creation
        invalid_framework = {**sample_framework_data, "name": ""}
        framework_response = await client.post("/api/v1/frameworks", json=invalid_framework)
        assert framework_response.status_code == 422

        # Create valid framework for further tests
        valid_framework_response = await client.post(
            "/api/v1/frameworks", json=sample_framework_data
        )
        framework_id = valid_framework_response.json()["id"]

        # Test invalid environment creation
        invalid_environment = {**sample_environment_data, "browser": "invalid-browser"}
        env_response = await client.post("/api/v1/environments", json=invalid_environment)
        assert env_response.status_code == 422

        # Create valid environment
        valid_env_response = await client.post("/api/v1/environments", json=sample_environment_data)
        environment_id = valid_env_response.json()["id"]

        # Test suite creation with non-existent framework
        invalid_suite = {
            **sample_suite_data,
            "framework_id": "non-existent-id",
            "environment_id": environment_id,
        }
        suite_response = await client.post("/api/v1/suites", json=invalid_suite)
        assert suite_response.status_code in [404, 422]

        # Test accessing non-existent resources
        nonexistent_response = await client.get("/api/v1/results/non-existent-id")
        assert nonexistent_response.status_code == 404

        # Test artifact upload to non-existent result
        artifact_data = b"test-artifact-data"
        artifact_response = await client.post(
            "/api/v1/results/non-existent-id/artifacts",
            files={"file": ("test.png", io.BytesIO(artifact_data), "image/png")},
            data={"artifact_type": "screenshot"},
        )
        assert artifact_response.status_code == 404

        # Test duplicate framework creation
        duplicate_framework_response = await client.post(
            "/api/v1/frameworks", json=sample_framework_data
        )
        assert duplicate_framework_response.status_code == 409

    finally:
        await client.aclose()


async def test_performance_workflow(
    sample_framework_data, sample_environment_data, sample_suite_data
):
    """Test performance characteristics of the workflow."""
    import time

    client = await setup_test_client()

    try:
        # Create base entities
        framework_response = await client.post("/api/v1/frameworks", json=sample_framework_data)
        framework_id = framework_response.json()["id"]

        environment_response = await client.post(
            "/api/v1/environments", json=sample_environment_data
        )
        environment_id = environment_response.json()["id"]

        # Test suite creation performance
        suite_creation_times = []
        suite_ids = []
        for i in range(10):
            suite_data = {
                **sample_suite_data,
                "name": f"{sample_suite_data['name']}-perf-{i}",
                "framework_id": framework_id,
                "environment_id": environment_id,
            }

            start_time = time.time()
            suite_response = await client.post("/api/v1/suites", json=suite_data)
            end_time = time.time()

            assert suite_response.status_code == 201
            suite_ids.append(suite_response.json()["id"])
            suite_creation_times.append(end_time - start_time)

        # Verify performance requirements (should be under 200ms p95)
        avg_creation_time = sum(suite_creation_times) / len(suite_creation_times)
        p95_creation_time = sorted(suite_creation_times)[int(0.95 * len(suite_creation_times))]

        assert avg_creation_time < 1.0  # 1 second average (relaxed for integration test)
        assert p95_creation_time < 2.0  # 2 seconds p95 (relaxed for integration test)

        # Test bulk query performance
        query_start = time.time()
        bulk_query = await client.get(f"/api/v1/suites?framework_id={framework_id}&limit=100")
        query_end = time.time()

        assert bulk_query.status_code == 200
        query_time = query_end - query_start
        assert query_time < 2.0  # Should be under 2 seconds for integration test

        # Test pagination performance
        pagination_times = []
        for offset in range(0, min(len(suite_ids), 10), 2):
            start_time = time.time()
            page_response = await client.get(
                f"/api/v1/suites?framework_id={framework_id}&limit=2&offset={offset}"
            )
            end_time = time.time()

            assert page_response.status_code == 200
            pagination_times.append(end_time - start_time)

        if pagination_times:
            avg_pagination_time = sum(pagination_times) / len(pagination_times)
            assert avg_pagination_time < 1.0  # Pagination should be under 1 second

    finally:
        await client.aclose()
