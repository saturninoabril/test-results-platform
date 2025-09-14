"""
Simple integration test to verify complete workflows with real PostgreSQL.
Tests data consistency across related entities and realistic data volumes.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from httpx import AsyncClient, ASGITransport
from src.main import app
from src.lib.middleware import get_current_context, AuthenticatedUser, UserRole
from src.lib.auth import TokenClaims, TokenScope, TokenType
from src.lib.database import init_database
from datetime import datetime, timezone, timedelta
from uuid import uuid4


def mock_auth():
    claims = TokenClaims(
        sub="integration:user:123",
        exp=datetime.now(timezone.utc) + timedelta(hours=1),
        scope=TokenScope.USER,
        token_type=TokenType.ACCESS,
        username="integration_user",
        email="integration@example.com",
        role=UserRole.ADMIN
    )
    return AuthenticatedUser(
        user_id="integration:user:123",
        username="integration_user",
        email="integration@example.com",
        role=UserRole.ADMIN,
        permissions=[
            "frameworks:read", "frameworks:write", "frameworks:delete",
            "environments:read", "environments:write", "environments:delete",
            "suites:read", "suites:write", "suites:delete",
            "results:read", "results:write", "results:delete",
            "artifacts:read", "artifacts:write", "artifacts:delete"
        ],
        token_claims=claims
    )


async def test_complete_workflow():
    """Test complete workflow from framework creation to test results."""
    await init_database()
    app.dependency_overrides[get_current_context] = mock_auth

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        print("🚀 Starting integration test workflow...")

        # Step 1: Create a test framework
        import random
        framework_data = {
            "name": "playwright",
            "version": f"1.55.{random.randint(1000, 9999)}",
            "metadata": {
                "actualWorkers": 4,
                "projects": ["setup", "chrome", "firefox", "webkit"]
            }
        }

        framework_response = await client.post("/api/v1/frameworks", json=framework_data)
        assert framework_response.status_code == 201, f"Framework creation failed: {framework_response.text}"
        framework = framework_response.json()
        framework_id = framework["id"]
        print(f"✅ Created framework: {framework['name']} v{framework['version']}")

        # Step 2: Create test environments
        environments = []
        import time
        timestamp = int(time.time())
        for browser in ["chrome", "firefox", "webkit"]:
            env_data = {
                "name": f"{browser}-desktop-{timestamp}",
                "browser": browser,
                "os": "linux",
                "metadata": {
                    "viewport": "1920x1080",
                    "deviceScaleFactor": 1
                }
            }
            env_response = await client.post("/api/v1/environments", json=env_data)
            assert env_response.status_code == 201, f"Environment creation failed: {env_response.text}"
            environments.append(env_response.json())

        print(f"✅ Created {len(environments)} test environments")

        # Step 3: Create test suites for each environment
        suites = []
        for env in environments:
            suite_data = {
                "framework_id": framework_id,
                "environment_id": env["id"],
                "name": f"E2E Tests - {env['browser']}",
                "total_count": 25,
                "passed_count": 20,
                "failed_count": 3,
                "skipped_count": 2,
                "duration_ms": 125000 + (len(suites) * 5000),
                "metadata": {
                    "browser": env["browser"],
                    "retries": 2,
                    "parallel": True
                }
            }
            suite_response = await client.post("/api/v1/suites", json=suite_data)
            assert suite_response.status_code == 201, f"Suite creation failed: {suite_response.text}"
            suites.append(suite_response.json())

        print(f"✅ Created {len(suites)} test suites")

        # Step 4: Create test results for each suite
        all_results = []
        test_scenarios = [
            {"name": "user-login", "status": "passed", "duration_ms": 2500, "tags": ["auth", "critical"]},
            {"name": "product-search", "status": "passed", "duration_ms": 1800, "tags": ["search", "e2e"]},
            {"name": "checkout-flow", "status": "failed", "duration_ms": 5200, "tags": ["checkout", "critical"],
             "error_message": "Payment form validation failed"},
            {"name": "user-profile", "status": "passed", "duration_ms": 1200, "tags": ["profile", "user"]},
            {"name": "admin-dashboard", "status": "skipped", "duration_ms": 0, "tags": ["admin"],
             "error_message": "Admin user not available"}
        ]

        for suite in suites:
            suite_results = []
            for i, scenario in enumerate(test_scenarios):
                result_data = {
                    "suite_id": suite["id"],
                    "name": scenario["name"],
                    "status": scenario["status"],
                    "duration_ms": scenario["duration_ms"],
                    "error_message": scenario.get("error_message"),
                    "tags": scenario["tags"],
                    "external_id": f"test-{i + 1}",
                    "full_title": f"E2E Tests > {scenario['name']}",
                    "metadata": {
                        "browser": suite["metadata"]["browser"],
                        "retry_count": 0 if scenario["status"] == "passed" else 1
                    }
                }
                result_response = await client.post("/api/v1/results", json=result_data)
                assert result_response.status_code == 201, f"Result creation failed: {result_response.text}"
                suite_results.append(result_response.json())

            all_results.extend(suite_results)

        print(f"✅ Created {len(all_results)} test results")

        # Step 5: Test bulk operations
        print("🧪 Testing bulk operations...")

        # Create bulk test results
        bulk_results = []
        for i in range(20):
            result_data = {
                "suite_id": suites[0]["id"],  # Use first suite
                "name": f"bulk-test-{i:02d}",
                "status": "passed" if i % 5 != 0 else "failed",
                "duration_ms": 1000 + (i * 50),
                "tags": ["bulk", "performance"],
                "external_id": f"bulk-{i:02d}",
                "full_title": f"Bulk Tests > bulk-test-{i:02d}",
                "metadata": {"batch_index": i}
            }
            bulk_results.append(result_data)

        bulk_response = await client.post("/api/v1/results/bulk", json=bulk_results)
        assert bulk_response.status_code == 201, f"Bulk creation failed: {bulk_response.text}"
        print(f"✅ Created {len(bulk_results)} results in bulk")

        # Step 6: Test filtering and statistics
        print("📊 Testing filtering and statistics...")

        # Test suite statistics
        stats_response = await client.get(f"/api/v1/suites/statistics?framework_id={framework_id}")
        assert stats_response.status_code == 200, f"Statistics failed: {stats_response.text}"
        stats = stats_response.json()
        print(f"📈 Statistics: {stats['total_suites']} suites, {stats['total_tests']} tests, {stats['pass_rate_percent']:.1f}% pass rate")

        # Test filtering by status
        failed_results_response = await client.get("/api/v1/results?status=failed")
        assert failed_results_response.status_code == 200
        failed_results = failed_results_response.json()
        print(f"🔍 Found {len(failed_results)} failed results")

        # Test filtering by tags
        critical_results_response = await client.get("/api/v1/results?tags=critical")
        assert critical_results_response.status_code == 200
        critical_results = critical_results_response.json()
        print(f"🔍 Found {len(critical_results)} critical results")

        # Step 7: Test data consistency
        print("🔍 Testing data consistency...")

        # Verify all created entities exist
        frameworks_response = await client.get("/api/v1/frameworks")
        assert frameworks_response.status_code == 200
        frameworks_list = frameworks_response.json()
        created_framework = next((f for f in frameworks_list if f["id"] == framework_id), None)
        assert created_framework is not None, "Created framework not found"

        environments_response = await client.get("/api/v1/environments")
        assert environments_response.status_code == 200
        environments_list = environments_response.json()
        linux_envs = [e for e in environments_list if e["os"] == "linux"]
        assert len(linux_envs) >= 3, "Created environments not found"

        suites_response = await client.get(f"/api/v1/suites?framework_id={framework_id}")
        assert suites_response.status_code == 200
        filtered_suites = suites_response.json()
        assert len(filtered_suites) == 3, "Created suites not found"

        print("✅ Data consistency verified")

        # Step 8: Test foreign key validation
        print("🔒 Testing foreign key validation...")

        # Try to create suite with invalid framework ID
        invalid_suite_data = {
            "framework_id": str(uuid4()),
            "environment_id": environments[0]["id"],
            "name": "Invalid Suite",
            "total_count": 1,
            "passed_count": 1,
            "failed_count": 0,
            "skipped_count": 0
        }
        invalid_suite_response = await client.post("/api/v1/suites", json=invalid_suite_data)
        assert invalid_suite_response.status_code == 422, "Foreign key validation failed"
        print("✅ Foreign key validation working")

        print("🎉 All integration tests passed successfully!")
        return True


async def test_performance():
    """Test performance with larger data volumes."""
    await init_database()
    app.dependency_overrides[get_current_context] = mock_auth

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        print("⚡ Starting performance test...")

        # Create framework and environment for performance testing
        import random
        framework_data = {
            "name": "cypress",
            "version": f"7.2.{random.randint(1000, 9999)}",
            "metadata": {"mocha": {"version": "7.2.0"}}
        }
        framework_response = await client.post("/api/v1/frameworks", json=framework_data)
        assert framework_response.status_code == 201
        framework = framework_response.json()

        import time
        timestamp = int(time.time())
        env_data = {
            "name": f"performance-test-env-{timestamp}",
            "browser": "chrome",
            "os": "ubuntu",
            "metadata": {"headless": True}
        }
        env_response = await client.post("/api/v1/environments", json=env_data)
        assert env_response.status_code == 201
        environment = env_response.json()

        suite_data = {
            "framework_id": framework["id"],
            "environment_id": environment["id"],
            "name": "Performance Test Suite",
            "total_count": 100,
            "passed_count": 85,
            "failed_count": 10,
            "skipped_count": 5,
            "duration_ms": 300000,
            "metadata": {"performance_test": True}
        }
        suite_response = await client.post("/api/v1/suites", json=suite_data)
        assert suite_response.status_code == 201
        suite = suite_response.json()

        # Create 100 test results in bulk
        bulk_results = []
        for i in range(100):
            status = "passed" if i < 85 else ("failed" if i < 95 else "skipped")
            result_data = {
                "suite_id": suite["id"],
                "name": f"perf-test-{i:03d}",
                "status": status,
                "duration_ms": 1000 + (i * 10),
                "tags": ["performance", "bulk"],
                "external_id": f"perf-{i:03d}",
                "full_title": f"Performance Test Suite > perf-test-{i:03d}",
                "metadata": {"test_number": i}
            }
            bulk_results.append(result_data)

        import time
        start_time = time.time()
        bulk_response = await client.post("/api/v1/results/bulk", json=bulk_results)
        end_time = time.time()

        assert bulk_response.status_code == 201
        creation_time = end_time - start_time
        print(f"⚡ Created 100 results in {creation_time:.3f} seconds")

        # Test filtering performance
        start_time = time.time()
        filtered_response = await client.get(f"/api/v1/results?suite_id={suite['id']}&status=failed")
        end_time = time.time()

        assert filtered_response.status_code == 200
        failed_results = filtered_response.json()
        filter_time = end_time - start_time
        print(f"🔍 Filtered results in {filter_time:.3f} seconds, found {len(failed_results)} failed")

        assert len(failed_results) == 10  # Should find 10 failed results
        print("✅ Performance test passed!")
        return True


if __name__ == "__main__":
    async def run_all_tests():
        success1 = await test_complete_workflow()
        success2 = await test_performance()
        return success1 and success2

    success = asyncio.run(run_all_tests())
    if success:
        print("🎉 All integration tests with real PostgreSQL passed!")
    else:
        print("❌ Integration tests failed!")
        sys.exit(1)