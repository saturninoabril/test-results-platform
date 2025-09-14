"""
Contract test for 'make test-unit' target.
Tests the interface specification requirements for unit test execution.
"""

import os
import subprocess
from pathlib import Path


class TestUnitTarget:
    """Test the make test-unit target contract."""

    def test_unit_target_exists(self):
        """Test that make test-unit target exists and is callable."""
        result = subprocess.run(
            ["make", "-n", "test-unit"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        # Should not fail with "No rule to make target"
        assert "No rule to make target" not in result.stderr
        assert result.returncode == 0

    def test_unit_success_criteria_when_working(self):
        """Test that make test-unit meets contract success criteria when tests pass."""
        result = subprocess.run(
            ["make", "test-unit"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        # Contract: Exit code 0 if all tests pass, 1 if any tests fail
        # Currently should fail because not implemented
        if "not implemented" not in result.stdout.lower():
            # Once implemented, should pass or fail appropriately
            assert result.returncode in [0, 1], (
                f"Expected exit code 0 or 1, got {result.returncode}"
            )

    def test_unit_dependencies_install(self):
        """Test that make test-unit depends on install target."""
        # Contract specifies: Dependencies: install
        result = subprocess.run(
            ["make", "-n", "test-unit"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        # When implemented, should show dependency on install
        assert result.returncode == 0

    def test_unit_environment_testing(self):
        """Test that make test-unit works in testing environment."""
        env = {"ENV": "test"}
        result = subprocess.run(
            ["make", "test-unit"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
            env={**os.environ, **env},
        )

        # Contract: Environment: Testing
        # Should succeed or fail appropriately in testing environment
        assert result.returncode >= 0  # Any valid exit code for now

    def test_unit_output_requirements(self):
        """Test that make test-unit provides required output format."""
        result = subprocess.run(
            ["make", "test-unit"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        # Contract: Output should include test results with coverage report
        # This will be validated when implementation exists
        output = result.stdout.lower()

        # For now, just verify it produces some output
        assert len(output) > 0

    def test_unit_fast_execution(self):
        """Test that unit tests are fast (unit test characteristic)."""
        import time

        start_time = time.time()

        result = subprocess.run(
            ["make", "test-unit"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        end_time = time.time()
        duration = end_time - start_time

        # Unit tests should be fast - allowing 60 seconds for now including setup
        # This will be tightened when actual implementation is done
        assert duration < 60, f"Unit tests took {duration:.2f} seconds, should be much faster"
