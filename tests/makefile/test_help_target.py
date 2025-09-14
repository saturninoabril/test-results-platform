"""
Contract test for 'make help' target.
Tests the interface specification requirements for help documentation.
"""

import subprocess
from pathlib import Path


class TestHelpTarget:
    """Test the make help target contract."""

    def test_help_target_exists(self):
        """Test that make help target exists and is callable."""
        result = subprocess.run(
            ["make", "-n", "help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        # Should not fail with "No rule to make target"
        assert "No rule to make target" not in result.stderr
        assert result.returncode == 0

    def test_help_is_default_target(self):
        """Test that make (no args) shows help by default."""
        result = subprocess.run(
            ["make"], capture_output=True, text=True, cwd=Path(__file__).parent.parent.parent
        )

        # Should show help information
        output = result.stdout.lower()
        assert "usage" in output or "commands" in output or "help" in output
        assert result.returncode == 0

    def test_help_success_criteria(self):
        """Test that make help meets contract success criteria."""
        result = subprocess.run(
            ["make", "help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        # Contract: Exit code 0
        assert result.returncode == 0

        # Contract: Display categorized list of all targets
        output = result.stdout
        assert "Development Commands" in output
        assert "Quality Assurance Commands" in output
        assert "Build and Container Commands" in output
        assert "Database Commands" in output
        assert "Utility Commands" in output

        # Contract: Brief description for each target
        assert "install" in output.lower()
        assert "upgrade" in output.lower()
        assert "test" in output.lower()
        assert "build" in output.lower()

        # Contract: Usage examples provided
        assert "Usage" in output
        assert "Examples" in output or "make " in output

    def test_help_no_dependencies_required(self):
        """Test that make help has no dependencies on other targets."""
        # Contract specifies: Dependencies: None
        result = subprocess.run(
            ["make", "-n", "help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        # Should be able to run without prerequisites
        assert result.returncode == 0

    def test_help_environment_any(self):
        """Test that make help works in any environment."""
        for env_val in ["dev", "test", "prod"]:
            env = {"ENV": env_val}
            result = subprocess.run(
                ["make", "help"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
                env={**subprocess.os.environ, **env},
            )

            # Contract: Environment: Any
            assert result.returncode == 0

    def test_help_shows_environment_variables(self):
        """Test that help shows available environment variables."""
        result = subprocess.run(
            ["make", "help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        output = result.stdout
        # Should document environment variables
        assert "ENV" in output
        assert "VERBOSE" in output
        assert "Environment Variables" in output or "environment" in output.lower()

    def test_help_comprehensive_coverage(self):
        """Test that help covers all major target categories."""
        result = subprocess.run(
            ["make", "help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        output = result.stdout.lower()

        # Check for key targets from each category
        development_targets = ["install", "upgrade", "dev"]
        quality_targets = ["type-check", "lint", "format", "test"]
        build_targets = ["build", "docker"]
        db_targets = ["db-upgrade", "db-reset"]
        utility_targets = ["clean", "help"]

        for target in (
            development_targets + quality_targets + build_targets + db_targets + utility_targets
        ):
            assert target in output, f"Target '{target}' not found in help output"
