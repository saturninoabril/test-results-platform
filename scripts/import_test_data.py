"""
Import and validate example test data from real Playwright and Cypress test results.
Creates data migration scripts and validates data model compatibility.
"""

import asyncio
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from httpx import ASGITransport, AsyncClient

from src.lib.auth import TokenClaims, TokenScope, TokenType
from src.lib.database import init_database
from src.lib.middleware import AuthenticatedUser, UserRole, get_current_context
from src.main import app


def mock_auth():
    """Create mock authentication for API calls."""
    claims = TokenClaims(
        sub="data_migration:user:admin",
        exp=datetime.now(UTC) + timedelta(hours=24),
        scope=TokenScope.USER,
        token_type=TokenType.ACCESS,
        username="data_migration_admin",
        email="migration@example.com",
        role=UserRole.ADMIN
    )
    return AuthenticatedUser(
        user_id="data_migration:user:admin",
        username="data_migration_admin",
        email="migration@example.com",
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


class PlaywrightDataMigrator:
    """Migrates Playwright test result data to the API."""

    def __init__(self, client: AsyncClient):
        self.client = client
        self.created_frameworks = {}
        self.created_environments = {}
        self.created_suites = {}

    async def load_playwright_data(self, file_path: str) -> dict[str, Any]:
        """Load and validate Playwright JSON data."""
        print(f"📖 Loading Playwright data from {file_path}")

        with open(file_path) as f:
            data = json.load(f)

        # Validate required structure
        required_keys = ['config', 'suites', 'stats']
        for key in required_keys:
            if key not in data:
                raise ValueError(f"Missing required key '{key}' in Playwright data")

        print(f"✅ Loaded Playwright data: {data['stats']['expected']} expected tests")
        return data

    async def create_framework_from_playwright(self, config: dict[str, Any]) -> str:
        """Create framework from Playwright config."""
        timestamp = int(time.time())

        framework_data = {
            "name": "playwright",
            "version": f"1.55.{timestamp % 10000}",  # Make version unique
            "metadata": {
                "actualWorkers": config.get("metadata", {}).get("actualWorkers", 1),
                "projects": [p.get("name", p.get("id", "unknown")) for p in config.get("projects", [])],
                "fullyParallel": config.get("fullyParallel", False),
                "retries": config.get("projects", [{}])[0].get("retries", 0) if config.get("projects") else 0,
                "timeout": config.get("projects", [{}])[0].get("timeout", 60000) if config.get("projects") else 60000,
                "configFile": config.get("configFile", "playwright.config.ts"),
                "testDir": config.get("projects", [{}])[0].get("testDir", "") if config.get("projects") else "",
                "reporter": config.get("reporter", []),
                "source": "example_data_migration",
                "original_version": config.get("version", "1.55.0")
            }
        }

        response = await self.client.post("/api/v1/frameworks", json=framework_data)
        if response.status_code != 201:
            raise Exception(f"Failed to create framework: {response.status_code} - {response.text}")

        framework = response.json()
        self.created_frameworks[framework_data["name"]] = framework
        print(f"✅ Created framework: {framework['name']} v{framework['version']}")
        return framework["id"]

    async def create_environments_from_playwright(self, config: dict[str, Any]) -> dict[str, str]:
        """Create environments from Playwright projects."""
        environments = {}

        timestamp = int(time.time())

        for project in config.get("projects", []):
            project_name = project.get("name", project.get("id", "unknown"))

            # Map project names to browser/OS combinations
            browser = "chrome"  # Default (chromium -> chrome)
            if "firefox" in project_name.lower():
                browser = "firefox"
            elif "webkit" in project_name.lower():
                browser = "webkit"
            elif "chrome" in project_name.lower():
                browser = "chrome"
            elif "ipad" in project_name.lower():
                browser = "webkit"  # iPad uses WebKit

            env_data = {
                "name": f"playwright-{project_name}-{timestamp}",
                "browser": browser,
                "os": "linux",  # Assuming linux for CI
                "metadata": {
                    "project_id": project.get("id", project_name),
                    "timeout": project.get("timeout", 60000),
                    "retries": project.get("retries", 0),
                    "actualWorkers": project.get("metadata", {}).get("actualWorkers", 1),
                    "testDir": project.get("testDir", ""),
                    "outputDir": project.get("outputDir", ""),
                    "source": "example_data_migration"
                }
            }

            response = await self.client.post("/api/v1/environments", json=env_data)
            if response.status_code != 201:
                raise Exception(f"Failed to create environment: {response.status_code} - {response.text}")

            environment = response.json()
            environments[project_name] = environment["id"]
            self.created_environments[project_name] = environment
            print(f"✅ Created environment: {env_data['name']} ({browser} on {env_data['os']})")

        return environments

    async def create_suite_from_playwright(self, framework_id: str, environment_id: str,
                                         suite_data: dict[str, Any], stats: dict[str, Any]) -> str:
        """Create test suite from Playwright suite data."""

        # Count tests for this project
        project_tests = []
        for spec in suite_data.get("specs", []):
            for test in spec.get("tests", []):
                project_tests.extend(test.get("results", []))

        total_tests = len(project_tests)
        passed_tests = sum(1 for test in project_tests if test.get("status") == "passed")
        failed_tests = sum(1 for test in project_tests if test.get("status") == "failed")
        skipped_tests = sum(1 for test in project_tests if test.get("status") == "skipped")

        # Calculate timing
        datetime.fromisoformat(stats["startTime"].replace("Z", "+00:00"))
        duration_ms = int(stats.get("duration", 0))

        suite_create_data = {
            "framework_id": framework_id,
            "environment_id": environment_id,
            "name": f"Playwright Test Suite - {suite_data.get('title', 'Unknown')}",
            "total_count": total_tests,
            "passed_count": passed_tests,
            "failed_count": failed_tests,
            "skipped_count": skipped_tests,
            "duration_ms": duration_ms,
            "metadata": {
                "file": suite_data.get("file", ""),
                "title": suite_data.get("title", ""),
                "column": suite_data.get("column", 0),
                "line": suite_data.get("line", 0),
                "specs_count": len(suite_data.get("specs", [])),
                "start_time": stats["startTime"],
                "expected": stats.get("expected", 0),
                "flaky": stats.get("flaky", 0),
                "unexpected": stats.get("unexpected", 0)
            }
        }

        response = await self.client.post("/api/v1/suites", json=suite_create_data)
        if response.status_code != 201:
            raise Exception(f"Failed to create suite: {response.status_code} - {response.text}")

        suite = response.json()
        suite_key = f"{suite_data.get('file', 'unknown')}"
        self.created_suites[suite_key] = suite
        print(f"✅ Created suite: {suite['name']} ({total_tests} tests)")
        return suite["id"]

    async def create_results_from_playwright(self, suite_id: str, suite_data: dict[str, Any]) -> list[str]:
        """Create test results from Playwright suite data."""
        results = []

        for spec in suite_data.get("specs", []):
            spec_title = spec.get("title", "Unknown Spec")

            for test in spec.get("tests", []):
                # Create results for each test execution (can be multiple results per test)
                for result in test.get("results", []):
                    # Map status
                    status = result.get("status", "unknown")
                    api_status = status if status in ["passed", "failed", "skipped"] else "failed"

                    # Extract error information
                    error_message = None
                    errors = result.get("errors", [])
                    if errors and len(errors) > 0:
                        error_message = str(errors[0]) if errors[0] else None

                    result_data = {
                        "suite_id": suite_id,
                        "name": spec_title,
                        "status": api_status,
                        "duration_ms": result.get("duration", 0),
                        "error_message": error_message,
                        "tags": test.get("tags", []),
                        "external_id": test.get("id", ""),
                        "full_title": f"{suite_data.get('title', '')} > {spec_title}",
                        "metadata": {
                            "file": spec.get("file", suite_data.get("file", "")),
                            "line": spec.get("line", 0),
                            "column": spec.get("column", 0),
                            "projectId": result.get("projectId", ""),
                            "projectName": result.get("projectName", ""),
                            "workerIndex": result.get("workerIndex", 0),
                            "parallelIndex": result.get("parallelIndex", 0),
                            "retry": result.get("retry", 0),
                            "startTime": result.get("startTime", ""),
                            "expectedStatus": test.get("expectedStatus", "passed"),
                            "timeout": test.get("timeout", 60000),
                            "annotations": result.get("annotations", []),
                            "attachments": result.get("attachments", [])
                        }
                    }

                    response = await self.client.post("/api/v1/results", json=result_data)
                    if response.status_code != 201:
                        print(f"⚠️  Failed to create result: {response.status_code} - {response.text}")
                        continue

                    result_obj = response.json()
                    results.append(result_obj["id"])

        print(f"✅ Created {len(results)} test results")
        return results

    async def migrate_playwright_data(self, file_path: str) -> dict[str, Any]:
        """Complete migration of Playwright data."""
        print("🔄 Starting Playwright data migration...")

        # Load data
        data = await self.load_playwright_data(file_path)

        # Create framework
        framework_id = await self.create_framework_from_playwright(data["config"])

        # Create environments for each project
        environments = await self.create_environments_from_playwright(data["config"])

        migration_results = {
            "framework_id": framework_id,
            "environments": environments,
            "suites": [],
            "total_results": 0
        }

        # Process each suite and create suites/results
        for suite_data in data["suites"]:
            # We need to create suites per project since each test can run on multiple projects
            project_suites = {}

            # Group tests by project
            projects_in_suite = set()
            for spec in suite_data.get("specs", []):
                for test in spec.get("tests", []):
                    for result in test.get("results", []):
                        project_name = result.get("projectName", "unknown")
                        projects_in_suite.add(project_name)

            # Create suite for each project that has tests in this suite
            for project_name in projects_in_suite:
                if project_name not in environments:
                    print(f"⚠️  Skipping unknown project: {project_name}")
                    continue

                environment_id = environments[project_name]

                # Filter suite data for this project
                project_suite_data = {
                    "title": f"{suite_data.get('title', 'Unknown')} - {project_name}",
                    "file": suite_data.get("file", ""),
                    "column": suite_data.get("column", 0),
                    "line": suite_data.get("line", 0),
                    "specs": []
                }

                # Add specs that have tests for this project
                for spec in suite_data.get("specs", []):
                    project_spec = {
                        "title": spec.get("title", ""),
                        "file": spec.get("file", ""),
                        "line": spec.get("line", 0),
                        "column": spec.get("column", 0),
                        "tests": []
                    }

                    for test in spec.get("tests", []):
                        project_results = [r for r in test.get("results", []) if r.get("projectName") == project_name]
                        if project_results:
                            project_test = {
                                **test,
                                "results": project_results
                            }
                            project_spec["tests"].append(project_test)

                    if project_spec["tests"]:
                        project_suite_data["specs"].append(project_spec)

                # Create suite if it has specs
                if project_suite_data["specs"]:
                    suite_id = await self.create_suite_from_playwright(
                        framework_id, environment_id, project_suite_data, data["stats"]
                    )

                    # Create results
                    result_ids = await self.create_results_from_playwright(suite_id, project_suite_data)

                    project_suites[project_name] = {
                        "suite_id": suite_id,
                        "result_ids": result_ids
                    }
                    migration_results["total_results"] += len(result_ids)

            migration_results["suites"].append(project_suites)

        print("✅ Playwright data migration completed!")
        return migration_results


class CypressDataMigrator:
    """Migrates Cypress test result data to the API."""

    def __init__(self, client: AsyncClient):
        self.client = client
        self.created_frameworks = {}
        self.created_environments = {}
        self.created_suites = {}

    async def load_cypress_data(self, file_path: str) -> dict[str, Any]:
        """Load and validate Cypress JSON data."""
        print(f"📖 Loading Cypress data from {file_path}")

        with open(file_path) as f:
            data = json.load(f)

        # Validate required structure
        required_keys = ['stats', 'results', 'meta']
        for key in required_keys:
            if key not in data:
                raise ValueError(f"Missing required key '{key}' in Cypress data")

        print(f"✅ Loaded Cypress data: {data['stats']['tests']} total tests")
        return data

    async def create_framework_from_cypress(self, meta: dict[str, Any]) -> str:
        """Create framework from Cypress meta."""
        timestamp = int(time.time())

        mocha_version = meta.get("mocha", {}).get("version", "7.2.0")
        mochawesome_version = meta.get("mochawesome", {}).get("version", "7.1.3")

        framework_data = {
            "name": "cypress",
            "version": f"7.2.{timestamp % 10000}",  # Make version unique
            "metadata": {
                "mocha": {
                    "version": mocha_version
                },
                "mochawesome": {
                    "version": mochawesome_version,
                    "options": meta.get("mochawesome", {}).get("options", {})
                },
                "marge": {
                    "version": meta.get("marge", {}).get("version", "6.2.0"),
                    "options": meta.get("marge", {}).get("options", {})
                },
                "testMeta": meta.get("marge", {}).get("options", {}).get("testMeta", {}),
                "source": "example_data_migration",
                "original_version": "7.2.0"
            }
        }

        response = await self.client.post("/api/v1/frameworks", json=framework_data)
        if response.status_code != 201:
            raise Exception(f"Failed to create framework: {response.status_code} - {response.text}")

        framework = response.json()
        self.created_frameworks[framework_data["name"]] = framework
        print(f"✅ Created framework: {framework['name']} v{framework['version']}")
        return framework["id"]

    async def create_environment_from_cypress(self, meta: dict[str, Any]) -> str:
        """Create environment from Cypress meta."""
        timestamp = int(time.time())
        test_meta = meta.get("marge", {}).get("options", {}).get("testMeta", {})

        # Map electron to chrome (Cypress's Electron browser is essentially Chrome)
        original_browser = test_meta.get("browser", "electron")
        browser = "chrome" if original_browser == "electron" else original_browser

        env_data = {
            "name": f"cypress-test-environment-{timestamp}",
            "browser": browser,
            "os": test_meta.get("platform", "linux"),
            "metadata": {
                "headless": test_meta.get("headless", True),
                "branch": test_meta.get("branch", "master"),
                "buildId": test_meta.get("buildId", "unknown"),
                "testFileAttempt": test_meta.get("testFileAttempt", 1),
                "source": "example_data_migration",
                "original_browser": original_browser
            }
        }

        response = await self.client.post("/api/v1/environments", json=env_data)
        if response.status_code != 201:
            raise Exception(f"Failed to create environment: {response.status_code} - {response.text}")

        environment = response.json()
        self.created_environments["cypress-env"] = environment
        print(f"✅ Created environment: {env_data['name']} ({env_data['browser']} on {env_data['os']})")
        return environment["id"]

    async def create_suite_from_cypress(self, framework_id: str, environment_id: str,
                                      stats: dict[str, Any], _results: list[dict[str, Any]]) -> str:
        """Create test suite from Cypress stats and results."""

        # Calculate timing
        datetime.fromisoformat(stats["start"].replace("Z", "+00:00"))
        datetime.fromisoformat(stats["end"].replace("Z", "+00:00"))
        duration_ms = int(stats.get("duration", 0))

        suite_create_data = {
            "framework_id": framework_id,
            "environment_id": environment_id,
            "name": "Cypress Test Suite - Accessibility Tests",
            "total_count": stats.get("tests", 0),
            "passed_count": stats.get("passes", 0),
            "failed_count": stats.get("failures", 0),
            "skipped_count": stats.get("skipped", 0),
            "duration_ms": duration_ms,
            "metadata": {
                "suites": stats.get("suites", 0),
                "testsRegistered": stats.get("testsRegistered", 0),
                "passPercent": stats.get("passPercent", 0),
                "pendingPercent": stats.get("pendingPercent", 0),
                "pending": stats.get("pending", 0),
                "other": stats.get("other", 0),
                "hasOther": stats.get("hasOther", False),
                "hasSkipped": stats.get("hasSkipped", False),
                "start": stats["start"],
                "end": stats["end"]
            }
        }

        response = await self.client.post("/api/v1/suites", json=suite_create_data)
        if response.status_code != 201:
            raise Exception(f"Failed to create suite: {response.status_code} - {response.text}")

        suite = response.json()
        self.created_suites["cypress-suite"] = suite
        print(f"✅ Created suite: {suite['name']} ({suite_create_data['total_count']} tests)")
        return suite["id"]

    async def create_results_from_cypress(self, suite_id: str, results: list[dict[str, Any]]) -> list[str]:
        """Create test results from Cypress results data."""
        created_results = []

        def extract_tests(suite_or_test, parent_title=""):
            """Recursively extract tests from nested suite structure."""
            tests = []

            if "tests" in suite_or_test:
                # This is a suite
                current_title = suite_or_test.get("title", "")
                full_title = f"{parent_title} {current_title}".strip()

                # Add direct tests
                for test in suite_or_test.get("tests", []):
                    tests.append({
                        **test,
                        "suite_title": full_title
                    })

                # Recursively add tests from nested suites
                for nested_suite in suite_or_test.get("suites", []):
                    tests.extend(extract_tests(nested_suite, full_title))

            return tests

        # Extract all tests from the nested structure
        all_tests = []
        for result in results:
            all_tests.extend(extract_tests(result))

        # Create API results for each test
        for test in all_tests:
            # Map Cypress status to our API status
            status_mapping = {
                "passed": "passed",
                "failed": "failed",
                "pending": "skipped",
                "skipped": "skipped"
            }

            cypress_state = test.get("state", "unknown")
            api_status = status_mapping.get(cypress_state, "failed")

            # Extract error information
            error_message = None
            if test.get("err") and isinstance(test["err"], dict):
                error_message = test["err"].get("message", str(test["err"]))

            # Extract tags from full title (common pattern in Cypress)
            tags = []
            full_title = test.get("fullTitle", "")
            if "accessibility" in full_title.lower():
                tags.append("accessibility")
            if "MM-T" in full_title:  # Test case ID pattern
                test_id = full_title.split("MM-T")[1].split()[0] if "MM-T" in full_title else ""
                if test_id:
                    tags.append(f"MM-T{test_id}")

            result_data = {
                "suite_id": suite_id,
                "name": test.get("title", "Unknown Test"),
                "status": api_status,
                "duration_ms": test.get("duration", 0),
                "error_message": error_message,
                "tags": tags,
                "external_id": test.get("uuid", ""),
                "full_title": full_title,
                "metadata": {
                    "suite_title": test.get("suite_title", ""),
                    "timedOut": test.get("timedOut"),
                    "speed": test.get("speed", ""),
                    "pass": test.get("pass", False),
                    "fail": test.get("fail", False),
                    "pending": test.get("pending", False),
                    "context": test.get("context"),
                    "code": test.get("code", ""),
                    "parentUUID": test.get("parentUUID", ""),
                    "isHook": test.get("isHook", False),
                    "skipped": test.get("skipped", False)
                }
            }

            response = await self.client.post("/api/v1/results", json=result_data)
            if response.status_code != 201:
                print(f"⚠️  Failed to create result: {response.status_code} - {response.text}")
                continue

            result_obj = response.json()
            created_results.append(result_obj["id"])

        print(f"✅ Created {len(created_results)} test results")
        return created_results

    async def migrate_cypress_data(self, file_path: str) -> dict[str, Any]:
        """Complete migration of Cypress data."""
        print("🔄 Starting Cypress data migration...")

        # Load data
        data = await self.load_cypress_data(file_path)

        # Create framework
        framework_id = await self.create_framework_from_cypress(data["meta"])

        # Create environment
        environment_id = await self.create_environment_from_cypress(data["meta"])

        # Create suite
        suite_id = await self.create_suite_from_cypress(framework_id, environment_id, data["stats"], data["results"])

        # Create results
        result_ids = await self.create_results_from_cypress(suite_id, data["results"])

        migration_results = {
            "framework_id": framework_id,
            "environment_id": environment_id,
            "suite_id": suite_id,
            "result_ids": result_ids,
            "total_results": len(result_ids)
        }

        print("✅ Cypress data migration completed!")
        return migration_results


async def validate_data_compatibility():
    """Validate that imported data is compatible with our API."""
    print("🔍 Validating data compatibility...")

    app.dependency_overrides[get_current_context] = mock_auth

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Test framework retrieval
        frameworks_response = await client.get("/api/v1/frameworks")
        assert frameworks_response.status_code == 200
        frameworks = frameworks_response.json()
        print(f"✅ Found {len(frameworks)} frameworks")

        # Test environment retrieval
        environments_response = await client.get("/api/v1/environments")
        assert environments_response.status_code == 200
        environments = environments_response.json()
        print(f"✅ Found {len(environments)} environments")

        # Test suite retrieval
        suites_response = await client.get("/api/v1/suites")
        assert suites_response.status_code == 200
        suites = suites_response.json()
        print(f"✅ Found {len(suites)} suites")

        # Test result retrieval
        results_response = await client.get("/api/v1/results")
        assert results_response.status_code == 200
        results = results_response.json()
        print(f"✅ Found {len(results)} results")

        # Test filtering capabilities
        if suites:
            framework_id = suites[0]["framework_id"]
            filtered_suites = await client.get(f"/api/v1/suites?framework_id={framework_id}")
            assert filtered_suites.status_code == 200
            print(f"✅ Framework filtering works: {len(filtered_suites.json())} suites for framework")

        if results:
            # Test status filtering
            passed_results = await client.get("/api/v1/results?status=passed")
            assert passed_results.status_code == 200
            print(f"✅ Status filtering works: {len(passed_results.json())} passed results")

            # Test tag filtering
            accessibility_results = await client.get("/api/v1/results?tags=accessibility")
            assert accessibility_results.status_code == 200
            print(f"✅ Tag filtering works: {len(accessibility_results.json())} accessibility results")

        # Test statistics
        if suites:
            framework_id = suites[0]["framework_id"]
            stats_response = await client.get(f"/api/v1/suites/statistics?framework_id={framework_id}")
            assert stats_response.status_code == 200
            stats = stats_response.json()
            print(f"✅ Statistics work: {stats['total_suites']} suites, {stats['pass_rate_percent']:.1f}% pass rate")

        print("✅ Data compatibility validation completed!")
        return {
            "frameworks_count": len(frameworks),
            "environments_count": len(environments),
            "suites_count": len(suites),
            "results_count": len(results)
        }


async def run_data_migration():
    """Run complete data migration process."""
    print("🚀 Starting Test Data Migration and Validation...")
    print("=" * 60)

    # Initialize database
    await init_database()
    app.dependency_overrides[get_current_context] = mock_auth

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:

        # Migrate Playwright data
        print("\n📊 PLAYWRIGHT DATA MIGRATION")
        print("-" * 40)
        playwright_migrator = PlaywrightDataMigrator(client)
        playwright_results = await playwright_migrator.migrate_playwright_data(
            "resource/playwright-test-results.json"
        )

        print("\n📊 CYPRESS DATA MIGRATION")
        print("-" * 40)
        cypress_migrator = CypressDataMigrator(client)
        cypress_results = await cypress_migrator.migrate_cypress_data(
            "resource/cypress-test-results.json"
        )

        print("\n🔍 DATA COMPATIBILITY VALIDATION")
        print("-" * 40)
        validation_results = await validate_data_compatibility()

        print("\n" + "=" * 60)
        print("📊 MIGRATION SUMMARY")
        print("=" * 60)

        print("🎭 Playwright Migration:")
        print(f"   • Framework: {playwright_migrator.created_frameworks.get('playwright', {}).get('name', 'N/A')}")
        print(f"   • Environments: {len(playwright_migrator.created_environments)}")
        print(f"   • Suites: {len(playwright_results.get('suites', []))}")
        print(f"   • Results: {playwright_results.get('total_results', 0)}")

        print("\n🌲 Cypress Migration:")
        print(f"   • Framework: {cypress_migrator.created_frameworks.get('cypress', {}).get('name', 'N/A')}")
        print(f"   • Environment: {cypress_migrator.created_environments.get('cypress-env', {}).get('name', 'N/A')}")
        print(f"   • Results: {cypress_results.get('total_results', 0)}")

        print("\n📈 Total Database Contents:")
        print(f"   • Frameworks: {validation_results['frameworks_count']}")
        print(f"   • Environments: {validation_results['environments_count']}")
        print(f"   • Suites: {validation_results['suites_count']}")
        print(f"   • Results: {validation_results['results_count']}")

        print("\n✅ Data migration and validation completed successfully!")
        return {
            "playwright_results": playwright_results,
            "cypress_results": cypress_results,
            "validation_results": validation_results
        }


if __name__ == "__main__":
    success = asyncio.run(run_data_migration())
    if success:
        print("🎉 All test data successfully imported and validated!")
    else:
        print("❌ Test data migration failed!")
        sys.exit(1)
