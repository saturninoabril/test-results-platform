"""
Integration tests for complete user workflows with real PostgreSQL.
Tests data consistency across related entities and realistic data volumes.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.lib.auth import TokenClaims, TokenScope, TokenType
from src.lib.database import close_database, init_database
from src.lib.middleware import AuthenticatedUser, UserRole, get_current_context
from src.main import app

# Apply pytest.mark.asyncio to all test methods in this module
pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="session")
async def setup_database():
    """Set up database for integration tests."""
    await init_database()
    yield
    await close_database()


async def setup_test_client():
    """Set up test client with authentication and database."""

    # Mock authentication for integration tests
    def mock_auth():
        claims = TokenClaims(
            sub="integration:user:123",
            exp=datetime.now(UTC) + timedelta(hours=1),
            scope=TokenScope.USER,
            token_type=TokenType.ACCESS,
            username="integration_user",
            email="integration@example.com",
            role=UserRole.ADMIN,
        )
        return AuthenticatedUser(
            user_id="integration:user:123",
            username="integration_user",
            email="integration@example.com",
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

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class TestCompleteWorkflows:
    """Integration tests for complete user workflows."""

    async def test_full_test_execution_workflow(self):
        """Test complete workflow from framework creation to test results."""
        await init_database()  # Ensure database is initialized
        client = await setup_test_client()

        async with client:
            # Step 1: Create a test framework
            framework_data = {
                "name": "playwright",
                "version": f"1.55.{uuid4().hex[:8]}",
                "metadata": {
                    "actualWorkers": 4,
                    "projects": ["setup", "chrome", "firefox", "webkit"],
                },
            }

            framework_response = await client.post("/api/v1/frameworks", json=framework_data)
        assert framework_response.status_code == 201
        framework = framework_response.json()
        framework_id = framework["id"]

        # Step 2: Create test environments
        environments = []
        for browser in ["chrome", "firefox", "webkit"]:
            env_data = {
                "name": f"{browser}-desktop",
                "browser": browser,
                "os": "linux",
                "metadata": {"viewport": "1920x1080", "deviceScaleFactor": 1},
            }
            env_response = await client.post("/api/v1/environments", json=env_data)
            assert env_response.status_code == 201
            environments.append(env_response.json())

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
                "duration_ms": 125000 + (len(suites) * 5000),  # Vary duration
                "metadata": {"browser": env["browser"], "retries": 2, "parallel": True},
            }
            suite_response = await client.post("/api/v1/suites", json=suite_data)
            assert suite_response.status_code == 201
            suites.append(suite_response.json())

        # Step 4: Create individual test results for each suite
        all_results = []
        test_scenarios = [
            {
                "name": "user-login",
                "status": "passed",
                "duration_ms": 2500,
                "tags": ["auth", "critical"],
            },
            {
                "name": "product-search",
                "status": "passed",
                "duration_ms": 1800,
                "tags": ["search", "e2e"],
            },
            {
                "name": "checkout-flow",
                "status": "failed",
                "duration_ms": 5200,
                "tags": ["checkout", "critical"],
                "error_message": "Payment form validation failed",
            },
            {
                "name": "user-profile",
                "status": "passed",
                "duration_ms": 1200,
                "tags": ["profile", "user"],
            },
            {
                "name": "admin-dashboard",
                "status": "skipped",
                "duration_ms": 0,
                "tags": ["admin"],
                "error_message": "Admin user not available",
            },
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
                        "retry_count": 0 if scenario["status"] == "passed" else 1,
                    },
                }
                result_response = await client.post("/api/v1/results", json=result_data)
                assert result_response.status_code == 201
                suite_results.append(result_response.json())

            all_results.extend(suite_results)

        # Step 5: Verify data consistency
        # Check that we created the right number of entities
        assert len(environments) == 3
        assert len(suites) == 3
        assert len(all_results) == 15  # 3 suites × 5 results each

        # Verify frameworks endpoint
        frameworks_response = await client.get("/api/v1/frameworks")
        assert frameworks_response.status_code == 200
        frameworks_list = frameworks_response.json()
        created_framework = next((f for f in frameworks_list if f["id"] == framework_id), None)
        assert created_framework is not None
        assert created_framework["name"] == "playwright"

        # Verify environments endpoint
        environments_response = await client.get("/api/v1/environments")
        assert environments_response.status_code == 200
        environments_list = environments_response.json()
        assert len([e for e in environments_list if e["os"] == "linux"]) >= 3

        # Verify suites endpoint with filtering
        suites_response = await client.get(f"/api/v1/suites?framework_id={framework_id}")
        assert suites_response.status_code == 200
        filtered_suites = suites_response.json()
        assert len(filtered_suites) == 3

        # Verify results endpoint with filtering
        for suite in suites:
            suite_results_response = await client.get(f"/api/v1/results?suite_id={suite['id']}")
            assert suite_results_response.status_code == 200
            suite_results = suite_results_response.json()
            assert len(suite_results) == 5

        # Verify statistics endpoint
        stats_response = await client.get(f"/api/v1/suites/statistics?framework_id={framework_id}")
        assert stats_response.status_code == 200
        stats = stats_response.json()
        assert stats["total_suites"] == 3
        assert stats["total_tests"] == 75  # 25 tests × 3 suites
        assert stats["total_passed"] == 60  # 20 passed × 3 suites
        assert stats["total_failed"] == 9  # 3 failed × 3 suites
        assert stats["total_skipped"] == 6  # 2 skipped × 3 suites

        # Step 6: Test filtering and search capabilities
        # Filter results by status
        failed_results_response = await client.get("/api/v1/results?status=failed")
        assert failed_results_response.status_code == 200
        failed_results = failed_results_response.json()
        assert len(failed_results) == 3  # One failed test per suite

        # Filter results by tags
        critical_results_response = await client.get("/api/v1/results?tags=critical")
        assert critical_results_response.status_code == 200
        critical_results = critical_results_response.json()
        assert len(critical_results) == 6  # 2 critical tests × 3 suites

        # Search environments by browser
        chrome_envs_response = await client.get("/api/v1/environments?browser=chrome")
        assert chrome_envs_response.status_code == 200
        chrome_envs = chrome_envs_response.json()
        assert len(chrome_envs) == 1
        assert chrome_envs[0]["browser"] == "chrome"

    async def test_bulk_operations_performance(self, client: AsyncClient):
        """Test bulk operations with realistic data volumes."""
        # Create framework and environment for bulk testing
        framework_data = {
            "name": "cypress",
            "version": f"7.2.{uuid4().hex[:8]}",
            "metadata": {"mocha": {"version": "7.2.0"}},
        }
        framework_response = await client.post("/api/v1/frameworks", json=framework_data)
        assert framework_response.status_code == 201
        framework = framework_response.json()

        env_data = {
            "name": "bulk-test-env",
            "browser": "chrome",
            "os": "ubuntu",
            "metadata": {"headless": True},
        }
        env_response = await client.post("/api/v1/environments", json=env_data)
        assert env_response.status_code == 201
        environment = env_response.json()

        # Create a test suite for bulk operations
        suite_data = {
            "framework_id": framework["id"],
            "environment_id": environment["id"],
            "name": "Bulk Performance Test Suite",
            "total_count": 100,
            "passed_count": 85,
            "failed_count": 10,
            "skipped_count": 5,
            "duration_ms": 300000,
            "metadata": {"bulk_test": True},
        }
        suite_response = await client.post("/api/v1/suites", json=suite_data)
        assert suite_response.status_code == 201
        suite = suite_response.json()

        # Create bulk test results (100 results)
        bulk_results = []
        for i in range(100):
            status = "passed" if i < 85 else ("failed" if i < 95 else "skipped")
            error_msg = f"Test error #{i}" if status == "failed" else None

            result_data = {
                "suite_id": suite["id"],
                "name": f"bulk-test-{i:03d}",
                "status": status,
                "duration_ms": 1000 + (i * 10),
                "error_message": error_msg,
                "tags": ["bulk", "performance"] + (["slow"] if i % 10 == 0 else []),
                "external_id": f"bulk-{i:03d}",
                "full_title": f"Bulk Performance Tests > bulk-test-{i:03d}",
                "metadata": {"test_number": i, "batch": i // 10},
            }
            bulk_results.append(result_data)

        # Test bulk creation
        import time

        start_time = time.time()

        bulk_response = await client.post("/api/v1/results/bulk", json=bulk_results)
        assert bulk_response.status_code == 201

        end_time = time.time()
        creation_time = end_time - start_time

        created_results = bulk_response.json()
        assert len(created_results) == 100

        # Verify bulk creation performance (should be reasonable)
        print(f"Bulk creation of 100 results took: {creation_time:.3f} seconds")
        assert creation_time < 10.0  # Should complete within 10 seconds

        # Verify data integrity
        suite_results_response = await client.get(f"/api/v1/results?suite_id={suite['id']}")
        assert suite_results_response.status_code == 200
        suite_results = suite_results_response.json()
        assert len(suite_results) == 100

        # Test filtering on large dataset
        failed_results_response = await client.get(
            f"/api/v1/results?suite_id={suite['id']}&status=failed"
        )
        assert failed_results_response.status_code == 200
        failed_results = failed_results_response.json()
        assert len(failed_results) == 10

        # Test pagination
        paginated_response = await client.get(
            f"/api/v1/results?suite_id={suite['id']}&limit=25&offset=0"
        )
        assert paginated_response.status_code == 200
        page1_results = paginated_response.json()
        assert len(page1_results) == 25

        paginated_response = await client.get(
            f"/api/v1/results?suite_id={suite['id']}&limit=25&offset=25"
        )
        assert paginated_response.status_code == 200
        page2_results = paginated_response.json()
        assert len(page2_results) == 25

        # Verify no overlap between pages
        page1_ids = {r["id"] for r in page1_results}
        page2_ids = {r["id"] for r in page2_results}
        assert len(page1_ids.intersection(page2_ids)) == 0

    async def test_data_consistency_across_entities(self, client: AsyncClient):
        """Test data consistency and referential integrity."""
        # Create related entities
        framework_data = {
            "name": "jest",
            "version": f"28.1.{uuid4().hex[:8]}",
            "metadata": {"testEnvironment": "node"},
        }
        framework_response = await client.post("/api/v1/frameworks", json=framework_data)
        assert framework_response.status_code == 201
        framework = framework_response.json()

        env_data = {
            "name": "node-environment",
            "browser": None,
            "os": "linux",
            "metadata": {"node_version": "18.17.0"},
        }
        env_response = await client.post("/api/v1/environments", json=env_data)
        assert env_response.status_code == 201
        environment = env_response.json()

        suite_data = {
            "framework_id": framework["id"],
            "environment_id": environment["id"],
            "name": "Unit Test Suite",
            "total_count": 50,
            "passed_count": 48,
            "failed_count": 2,
            "skipped_count": 0,
            "duration_ms": 15000,
            "metadata": {"test_type": "unit"},
        }
        suite_response = await client.post("/api/v1/suites", json=suite_data)
        assert suite_response.status_code == 201
        suite = suite_response.json()

        # Test foreign key validation - try to create suite with invalid framework
        invalid_suite_data = {
            "framework_id": str(uuid4()),  # Non-existent framework ID
            "environment_id": environment["id"],
            "name": "Invalid Suite",
            "total_count": 1,
            "passed_count": 1,
            "failed_count": 0,
            "skipped_count": 0,
        }
        invalid_suite_response = await client.post("/api/v1/suites", json=invalid_suite_data)
        assert invalid_suite_response.status_code == 422  # Validation error

        # Test foreign key validation - try to create result with invalid suite
        invalid_result_data = {
            "suite_id": str(uuid4()),  # Non-existent suite ID
            "name": "invalid-test",
            "status": "passed",
        }
        invalid_result_response = await client.post("/api/v1/results", json=invalid_result_data)
        assert invalid_result_response.status_code == 422  # Validation error

        # Create valid result
        result_data = {
            "suite_id": suite["id"],
            "name": "valid-unit-test",
            "status": "passed",
            "duration_ms": 125,
            "tags": ["unit", "fast"],
            "metadata": {"test_file": "user.test.js"},
        }
        result_response = await client.post("/api/v1/results", json=result_data)
        assert result_response.status_code == 201
        result = result_response.json()

        # Test cascade behavior - verify entities exist
        framework_get_response = await client.get(f"/api/v1/frameworks/{framework['id']}")
        assert framework_get_response.status_code == 200

        environment_get_response = await client.get(f"/api/v1/environments/{environment['id']}")
        assert environment_get_response.status_code == 200

        suite_get_response = await client.get(f"/api/v1/suites/{suite['id']}")
        assert suite_get_response.status_code == 200

        result_get_response = await client.get(f"/api/v1/results/{result['id']}")
        assert result_get_response.status_code == 200

        # Test entity deletion order (should handle dependencies)
        # Delete result first
        result_delete_response = await client.delete(f"/api/v1/results/{result['id']}")
        assert result_delete_response.status_code == 204

        # Delete suite
        suite_delete_response = await client.delete(f"/api/v1/suites/{suite['id']}")
        assert suite_delete_response.status_code == 204

        # Verify entities are deleted
        deleted_result_response = await client.get(f"/api/v1/results/{result['id']}")
        assert deleted_result_response.status_code == 404

        deleted_suite_response = await client.get(f"/api/v1/suites/{suite['id']}")
        assert deleted_suite_response.status_code == 404

        # Framework and environment should still exist
        framework_get_response = await client.get(f"/api/v1/frameworks/{framework['id']}")
        assert framework_get_response.status_code == 200

        environment_get_response = await client.get(f"/api/v1/environments/{environment['id']}")
        assert environment_get_response.status_code == 200

    async def test_concurrent_operations(self, client: AsyncClient):
        """Test concurrent operations to verify database consistency."""
        # Create shared entities
        framework_data = {
            "name": "mocha",
            "version": f"10.2.{uuid4().hex[:8]}",
            "metadata": {"reporter": "spec"},
        }
        framework_response = await client.post("/api/v1/frameworks", json=framework_data)
        assert framework_response.status_code == 201
        framework = framework_response.json()

        # Create multiple concurrent operations
        async def create_environment_and_suite(browser: str, index: int):
            env_data = {
                "name": f"concurrent-env-{index}",
                "browser": browser,
                "os": "windows",
                "metadata": {"concurrent_test": True, "index": index},
            }
            env_response = await client.post("/api/v1/environments", json=env_data)
            assert env_response.status_code == 201
            environment = env_response.json()

            suite_data = {
                "framework_id": framework["id"],
                "environment_id": environment["id"],
                "name": f"Concurrent Suite {index}",
                "total_count": 10 + index,
                "passed_count": 8 + index,
                "failed_count": 1,
                "skipped_count": 1,
                "duration_ms": 5000 + (index * 1000),
                "metadata": {"concurrent": True, "index": index},
            }
            suite_response = await client.post("/api/v1/suites", json=suite_data)
            assert suite_response.status_code == 201
            return suite_response.json()

        # Run concurrent operations
        tasks = []
        browsers = ["chrome", "firefox", "safari", "edge"]
        for i, browser in enumerate(browsers):
            tasks.append(create_environment_and_suite(browser, i))

        concurrent_suites = await asyncio.gather(*tasks)
        assert len(concurrent_suites) == 4

        # Verify all suites were created successfully
        suites_response = await client.get(f"/api/v1/suites?framework_id={framework['id']}")
        assert suites_response.status_code == 200
        all_suites = suites_response.json()
        created_suite_ids = {suite["id"] for suite in concurrent_suites}
        fetched_suite_ids = {
            suite["id"] for suite in all_suites if "Concurrent Suite" in suite["name"]
        }
        assert created_suite_ids == fetched_suite_ids

        print("✅ All integration tests with real PostgreSQL passed!")
