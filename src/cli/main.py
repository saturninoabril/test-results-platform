#!/usr/bin/env python3
"""
Main CLI entry point for Test Results Management API tools.
Provides a unified interface for all CLI functionality.
"""

import sys
from pathlib import Path

import click
from rich import print as rprint
from rich.console import Console

# Add the parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# from cli.auth import auth_cli

console = Console()


@click.group()
@click.version_option(version="0.4.0", prog_name="test-results-cli")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Test Results Management API CLI Tools.

    A comprehensive command-line interface for managing test results,
    authentication, storage, and CI/CD integration.

    Common workflows:
      • Generate automation tokens: test-results-cli auth token generate
      • Validate API connectivity: test-results-cli auth status
      • Import test data: test-results-cli data import <file>
      • Manage storage: test-results-cli storage cleanup

    For detailed help on any command, use: test-results-cli <command> --help
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


# Register subcommands
# cli.add_command(auth_cli, name="auth")


@cli.command()
def version() -> None:
    """Show version information."""
    rprint("🧪 [bold]Test Results Management API CLI[/bold]")
    rprint("   Version: 0.4.0")
    rprint("   Python: " + sys.version.split()[0])
    rprint("   Platform: " + sys.platform)


@cli.command()
def quickstart() -> None:
    """Show quickstart guide for CLI usage."""
    rprint("""
🚀 [bold blue]Test Results CLI Quickstart Guide[/bold blue]

[bold yellow]1. Generate an automation token:[/bold yellow]
   test-results-cli auth token generate --name "My CI Token" --scope automation

[bold yellow]2. Set up GitHub Actions integration:[/bold yellow]
   • Copy the token from step 1
   • Add it to GitHub Secrets as TEST_RESULTS_TOKEN
   • Use the reusable workflows in .github/workflows/

[bold yellow]3. Validate your setup:[/bold yellow]
   test-results-cli auth status
   test-results-cli auth token validate <your-token>

[bold yellow]4. Available commands:[/bold yellow]
   • auth token generate    - Create automation tokens
   • auth token list        - List stored tokens
   • auth token validate    - Validate token
   • auth github setup     - Configure GitHub OAuth
   • auth status           - Show system status

[bold green]Need help?[/bold green] Use --help with any command for detailed options.
""")


if __name__ == "__main__":
    try:
        cli()
    except KeyboardInterrupt:
        rprint("\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        rprint(f"\n❌ [bold red]Error:[/bold red] {e}")
        if "--verbose" in sys.argv or "-v" in sys.argv:
            raise
        sys.exit(1)
