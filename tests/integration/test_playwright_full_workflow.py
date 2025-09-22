"""
Integration tests for complete Playwright test run workflow.
These tests validate end-to-end scenarios from test suite creation to final results.
"""

import pytest
from httpx import AsyncClient

# Apply pytest.mark.asyncio to all test methods in this module
pytestmark = pytest.mark.asyncio


class TestPlaywrightFullWorkflowIntegration:
    """Integration tests for complete Playwright workflow."""

    async def test_playwright_workflow_with_test_failure(self, client: AsyncClient):
        """Test workflow where a test fails and generates retry attempts."""

        # Create suite with environment metadata
        suite_response = await client.post(
            "/playwright/suites",
            json={
                "name": "Flaky Tests Suite",
                "version": "1.55.0",
                "test_count": 1,
                "status": "running",
                "start_time": "2025-09-20T15:45:00Z",
                "environment_metadata": {
                    "name": "Firefox Desktop",
                    "browser_name": "firefox",
                    "os": "linux",
                },
                "framework_metadata": {
                    "name": "playwright",
                    "version": "1.55.0",
                },
            },
        )
        suite_id = suite_response.json()["id"]

        # Create a test that will fail first, then retry and pass
        test_data = {
            "suite_id": suite_id,
            "external_id": "test-flaky-operation",
            "title": "should handle flaky operation",
            "full_title": "Flaky Tests › should handle flaky operation",
            "status": "running",
            "retry_count": 0,
            "start_time": "2025-09-20T15:45:05Z",
        }
        test_response = await client.post("/playwright/test-results", json=test_data)
        assert test_response.status_code == 201

        # First attempt - fail
        first_attempt_update = {
            "status": "failed",
            "duration": 5000,
            "end_time": "2025-09-20T15:45:10Z",
            "error_message": "Timeout: Element not found after 5000ms",
        }
        await client.put(
            f"/playwright/test-results/test-flaky-operation?suite_id={suite_id}",
            json=first_attempt_update,
        )

        # Create retry attempt
        retry_test_data = {
            "suite_id": suite_id,
            "external_id": "test-flaky-operation-retry1",
            "title": "should handle flaky operation",
            "full_title": "Flaky Tests › should handle flaky operation",
            "status": "running",
            "retry_count": 1,
            "start_time": "2025-09-20T15:45:15Z",
        }
        retry_response = await client.post("/playwright/test-results", json=retry_test_data)
        assert retry_response.status_code == 201

        # Retry attempt succeeds
        retry_update = {"status": "passed", "duration": 3500, "end_time": "2025-09-20T15:45:19Z"}
        await client.put(
            f"/playwright/test-results/test-flaky-operation-retry1?suite_id={suite_id}",
            json=retry_update,
        )

        # Complete suite as passed (retry succeeded)
        suite_update = {"status": "passed", "end_time": "2025-09-20T15:45:25Z", "duration": 25000}
        await client.put(f"/playwright/suites/{suite_id}", json=suite_update)

        # Verify results show both attempts
        results_response = await client.get(f"/playwright/test-results?suite_id={suite_id}")
        assert results_response.status_code == 200
        results_data = results_response.json()

        assert results_data["total"] == 2  # Original + retry

        # Find the failed and passed attempts
        failed_result = next((r for r in results_data["results"] if r["status"] == "failed"), None)
        passed_result = next((r for r in results_data["results"] if r["status"] == "passed"), None)

        assert failed_result is not None
        assert failed_result["retry_count"] == 0
        assert failed_result["error_message"] == "Timeout: Element not found after 5000ms"

        assert passed_result is not None
        assert passed_result["retry_count"] == 1
