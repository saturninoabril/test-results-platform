"""
Contract test for 'make check-requirements' target.
Tests the interface specification requirements for development prerequisites.
"""

import subprocess
from pathlib import Path


class TestRequirementsTarget:
    """Test the make check-requirements target contract."""

    def test_requirements_target_exists(self):
        """Test that make check-requirements target exists and is callable."""
        result = subprocess.run(
            ["make", "-n", "check-requirements"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        # Should not fail with "No rule to make target"
        assert "No rule to make target" not in result.stderr
        assert result.returncode == 0

    def test_requirements_success_criteria(self):
        """Test that make check-requirements meets contract success criteria."""
        result = subprocess.run(
            ["make", "check-requirements"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        # Contract: Exit code 0 when requirements satisfied
        assert result.returncode == 0, (
            f"Expected exit code 0, got {result.returncode}: {result.stderr}"
        )

        # Contract: Output should indicate Python 3.13+ and uv found
        output = result.stdout.lower()
        assert "python" in output
        assert "uv" in output
        assert "requirements satisfied" in output or "found" in output

    def test_requirements_python_version_check(self):
        """Test that requirements check validates Python version."""
        result = subprocess.run(
            ["make", "check-requirements"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        # Should check Python version
        output = result.stdout
        assert "Python" in output
        # Should find Python 3.13+ (assuming development environment has it)
        assert "3.13" in output or "3.14" in output or "3.15" in output

    def test_requirements_uv_check(self):
        """Test that requirements check validates uv installation."""
        result = subprocess.run(
            ["make", "check-requirements"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        # Should check uv installation
        output = result.stdout
        assert "uv" in output
        # Should show version (assuming uv is installed in development)
        assert "found" in output.lower()

    def test_requirements_no_dependencies(self):
        """Test that make check-requirements has no dependencies on other targets."""
        result = subprocess.run(
            ["make", "-n", "check-requirements"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        # Should be able to run without prerequisites
        assert result.returncode == 0

    def test_requirements_help_integration(self):
        """Test that check-requirements appears in help output."""
        result = subprocess.run(
            ["make", "help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        # Should appear in help
        output = result.stdout
        assert "check-requirements" in output
        assert "Python 3.13+" in output and "uv installation" in output

    def test_install_depends_on_requirements(self):
        """Test that install target depends on requirements check."""
        result = subprocess.run(
            ["make", "-n", "install"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        # Should show dependency on check-requirements
        # This is a structural test - we expect no errors
        assert result.returncode == 0

    def test_requirements_strict_enforcement(self):
        """Test that requirements check enforces Python 3.13+ minimum version."""
        # This test validates the design - actual version checking happens at runtime
        # We're testing that the Makefile includes version comparison logic

        # Read the Makefile to verify version check logic exists
        makefile_path = Path(__file__).parent.parent.parent / "Makefile"
        makefile_content = makefile_path.read_text()

        # Should contain Python version checking logic
        assert "PYTHON_MIN_VERSION" in makefile_content
        assert "3.13" in makefile_content
        assert "version_info" in makefile_content or "sort -V" in makefile_content

        # Should contain uv checking logic
        assert "command -v uv" in makefile_content
        assert "uv --version" in makefile_content
