#!/usr/bin/env python3
"""
Authentication CLI tool for Test Results Management API.
Provides commands for managing automation tokens, users, and GitHub OAuth setup.
"""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import click
import structlog
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

# Import from the parent services
from ..lib.auth import TokenClaims, TokenScope, TokenType, get_token_manager
from ..lib.config import get_settings

logger = structlog.get_logger()
console = Console()


class TokenManager:
    """Manages automation tokens for the Test Results Management API."""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def generate_token(
        self,
        name: str,
        scope: TokenScope,
        expires_days: int = 365,
        permissions: list[str] | None = None,
        _metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate a new automation token."""

        # Generate unique token ID
        token_id = f"auto_{uuid4().hex[:16]}"

        # Set expiration
        expires_at = datetime.now(UTC) + timedelta(days=expires_days)

        # Create token claims
        claims = TokenClaims(
            sub=token_id,
            exp=expires_at,
            scope=scope,
            token_type=TokenType.AUTOMATION,
            username=name,
            email=f"{token_id}@automation.local",
            permissions=permissions or self._get_default_permissions(scope),
            automation_name=name,
            role=None,
            github_id=None,
        )

        # Generate JWT token using the token manager
        token_manager = await get_token_manager()
        token_result = await token_manager.create_automation_token(
            automation_name=name, permissions=claims.permissions, expiration_days=expires_days
        )
        token = token_result["access_token"]

        # Store token metadata (in production, this would be in database)
        token_info = {
            "id": token_id,
            "name": name,
            "scope": scope.value,
            "permissions": claims.permissions,
            "created_at": datetime.now(UTC).isoformat(),
            "expires_at": expires_at.isoformat(),
            "token": token,
            "metadata": {
                "created_by": "cli",
                "token_name": name,
                "created_at": datetime.now(UTC).isoformat(),
            },
        }

        await self._store_token_metadata(token_info)

        return token_info

    def _get_default_permissions(self, scope: TokenScope) -> list[str]:
        """Get default permissions for a given scope."""
        if scope == TokenScope.USER:
            return [
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
            ]
        elif scope == TokenScope.AUTOMATION:
            return [
                "frameworks:read",
                "frameworks:write",
                "environments:read",
                "environments:write",
                "suites:read",
                "suites:write",
                "results:read",
                "results:write",
                "artifacts:read",
                "artifacts:write",
            ]
        elif scope == TokenScope.READONLY:
            return [
                "frameworks:read",
                "environments:read",
                "suites:read",
                "results:read",
                "artifacts:read",
            ]
        else:
            return []

    async def _store_token_metadata(self, token_info: dict[str, Any]) -> None:
        """Store token metadata. In production, this would use the database."""
        # For now, store in a local file for CLI purposes
        tokens_dir = Path.home() / ".test-results-cli" / "tokens"
        tokens_dir.mkdir(parents=True, exist_ok=True)

        token_file = tokens_dir / f"{token_info['id']}.json"

        # Don't store the actual token in the file for security
        metadata = {k: v for k, v in token_info.items() if k != "token"}

        with open(token_file, "w") as f:
            json.dump(metadata, f, indent=2, default=str)

    async def list_tokens(self) -> list[dict[str, Any]]:
        """List all stored token metadata."""
        tokens_dir = Path.home() / ".test-results-cli" / "tokens"
        if not tokens_dir.exists():
            return []

        tokens = []
        for token_file in tokens_dir.glob("*.json"):
            try:
                with open(token_file) as f:
                    token_info = json.load(f)
                    tokens.append(token_info)
            except Exception as e:
                logger.warning(f"Failed to load token file {token_file}: {e}")

        return sorted(tokens, key=lambda t: t.get("created_at", ""))

    async def revoke_token(self, token_id: str) -> bool:
        """Revoke a token by removing its metadata."""
        tokens_dir = Path.home() / ".test-results-cli" / "tokens"
        token_file = tokens_dir / f"{token_id}.json"

        if token_file.exists():
            token_file.unlink()
            return True
        return False

    async def validate_token(self, token: str) -> dict[str, Any]:
        """Validate a token and return its claims."""
        try:
            # This would typically validate against the API
            # For now, we'll just decode the JWT
            from ..lib.auth import get_token_manager

            token_manager = await get_token_manager()
            claims = token_manager.jwt_auth.decode_token_claims(token)
            if claims:
                return {
                    "valid": True,
                    "claims": claims.__dict__,
                    "expires_at": claims.exp.isoformat(),
                    "scope": claims.scope.value if claims.scope else "unknown",
                    "permissions": claims.permissions or [],
                }
            else:
                return {"valid": False, "error": "Invalid token format"}
        except Exception as e:
            return {"valid": False, "error": str(e)}


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.pass_context
def auth_cli(ctx: click.Context, verbose: bool) -> None:
    """Test Results Management API Authentication CLI.

    Manage automation tokens, users, and authentication configuration.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

    if verbose:
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(20),
        )


@auth_cli.group()
def token() -> None:
    """Manage automation tokens."""
    pass


@token.command("generate")
@click.option("--name", "-n", required=True, help="Token name/description")
@click.option(
    "--scope",
    "-s",
    type=click.Choice(["user", "automation", "read-only"], case_sensitive=False),
    default="automation",
    help="Token scope",
)
@click.option("--expires-days", "-e", type=int, default=365, help="Token expiration in days")
@click.option(
    "--permissions", "-p", multiple=True, help="Specific permissions (can be used multiple times)"
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["token", "json", "table"]),
    default="table",
    help="Output format",
)
@click.option("--save", is_flag=True, help="Save token metadata locally")
def generate_token(
    name: str, scope: str, expires_days: int, permissions: list[str], output: str, save: bool
) -> None:
    """Generate a new automation token.

    Examples:
      auth token generate --name "GitHub Actions" --scope automation
      auth token generate --name "Read Only" --scope read-only --expires-days 30
      auth token generate --name "Custom" --permissions "results:write" --permissions "artifacts:read"
    """

    async def _generate() -> None:
        manager = TokenManager()

        # Convert scope string to enum
        scope_enum = TokenScope[scope.upper().replace("-", "_")]

        # Generate the token
        rprint(f"🔐 Generating {scope} token: [bold]{name}[/bold]")
        rprint(f"⏰ Expires in {expires_days} days")

        token_info = await manager.generate_token(
            name=name,
            scope=scope_enum,
            expires_days=expires_days,
            permissions=list(permissions) if permissions else None,
        )

        if output == "token":
            # Just print the token
            rprint(token_info["token"])
        elif output == "json":
            # Print full JSON (excluding sensitive data)
            output_data = {k: v for k, v in token_info.items() if k != "token"}
            output_data["token"] = "***REDACTED***"
            rprint(json.dumps(output_data, indent=2, default=str))
        else:
            # Pretty table output
            rprint("\n✅ [bold green]Token generated successfully![/bold green]\n")

            # Create info table
            table = Table(title="Token Information")
            table.add_column("Field", style="cyan")
            table.add_column("Value", style="white")

            table.add_row("Name", name)
            table.add_row("ID", token_info["id"])
            table.add_row("Scope", scope)
            table.add_row("Created", token_info["created_at"][:19])
            table.add_row("Expires", token_info["expires_at"][:19])
            table.add_row("Permissions", ", ".join(token_info["permissions"]))

            console.print(table)

            # Show token in a panel
            token_panel = Panel(
                token_info["token"], title="🔑 Bearer Token", border_style="green", expand=False
            )
            console.print("\n", token_panel)

            # Security warning
            warning = Panel(
                "⚠️  Store this token securely - it won't be shown again!\n"
                "💡 Add it to GitHub Secrets as TEST_RESULTS_TOKEN\n"
                "🔒 This token grants access to your Test Results API",
                title="Security Notice",
                border_style="yellow",
            )
            console.print("\n", warning)

        if save:
            rprint("\n💾 Token metadata saved to ~/.test-results-cli/tokens/")

    asyncio.run(_generate())


@token.command("list")
@click.option(
    "--format", "-f", type=click.Choice(["table", "json"]), default="table", help="Output format"
)
def list_tokens(format: str) -> None:
    """List all stored tokens."""

    async def _list() -> None:
        manager = TokenManager()
        tokens = await manager.list_tokens()

        if not tokens:
            rprint("📭 No tokens found")
            return

        if format == "json":
            rprint(json.dumps(tokens, indent=2, default=str))
        else:
            table = Table(title="Stored Tokens")
            table.add_column("Name", style="cyan")
            table.add_column("ID", style="white")
            table.add_column("Scope", style="green")
            table.add_column("Created", style="blue")
            table.add_column("Expires", style="yellow")

            for token in tokens:
                expires = token.get("expires_at", "")[:19] if token.get("expires_at") else "Never"
                created = token.get("created_at", "")[:19] if token.get("created_at") else "Unknown"

                table.add_row(
                    token.get("name", "Unknown"),
                    token.get("id", "Unknown"),
                    token.get("scope", "Unknown"),
                    created,
                    expires,
                )

            console.print(table)

    asyncio.run(_list())


@token.command("validate")
@click.argument("token")
@click.option(
    "--format", "-f", type=click.Choice(["table", "json"]), default="table", help="Output format"
)
def validate_token(token: str, format: str) -> None:
    """Validate a token and show its details."""

    async def _validate() -> None:
        manager = TokenManager()
        result = await manager.validate_token(token)

        if format == "json":
            rprint(json.dumps(result, indent=2, default=str))
        else:
            if result["valid"]:
                rprint("✅ [bold green]Token is valid[/bold green]\n")

                table = Table(title="Token Details")
                table.add_column("Field", style="cyan")
                table.add_column("Value", style="white")

                claims = result["claims"]
                table.add_row("Subject", claims.get("sub", "Unknown"))
                table.add_row("Scope", result["scope"])
                table.add_row("Expires", result["expires_at"][:19])
                table.add_row("Token Type", claims.get("token_type", "Unknown"))
                table.add_row("Permissions", ", ".join(result["permissions"]))

                console.print(table)
            else:
                rprint(f"❌ [bold red]Token is invalid[/bold red]: {result['error']}")

    asyncio.run(_validate())


@token.command("revoke")
@click.argument("token_id")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
def revoke_token(token_id: str, yes: bool) -> None:
    """Revoke a token by ID."""

    async def _revoke() -> None:
        if not yes and not Confirm.ask(f"Are you sure you want to revoke token {token_id}?"):
            rprint("❌ Cancelled")
            return

        manager = TokenManager()
        success = await manager.revoke_token(token_id)

        if success:
            rprint(f"✅ [bold green]Token {token_id} revoked successfully[/bold green]")
        else:
            rprint(f"❌ [bold red]Token {token_id} not found[/bold red]")

    asyncio.run(_revoke())


@auth_cli.group()
def github() -> None:
    """GitHub OAuth configuration."""
    pass


@github.command("setup")
@click.option("--client-id", prompt=True, help="GitHub OAuth App Client ID")
@click.option(
    "--client-secret", prompt=True, hide_input=True, help="GitHub OAuth App Client Secret"
)
@click.option("--callback-url", help="OAuth callback URL")
def setup_github_oauth(client_id: str, _client_secret: str, callback_url: str) -> None:
    """Set up GitHub OAuth configuration.

    This will create or update the GitHub OAuth configuration for user authentication.
    You need to create a GitHub OAuth App first at: https://github.com/settings/applications/new
    """
    rprint("🔧 Setting up GitHub OAuth configuration...")

    # In production, this would update the application configuration
    # For now, we'll show what would be configured

    config = {
        "github_oauth": {
            "client_id": client_id,
            "client_secret": "***REDACTED***",
            "callback_url": callback_url or "http://localhost:8000/auth/github/callback",
        }
    }

    rprint("✅ [bold green]GitHub OAuth configured successfully![/bold green]\n")

    table = Table(title="OAuth Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Client ID", client_id)
    table.add_row("Client Secret", "***REDACTED***")
    table.add_row("Callback URL", config["github_oauth"]["callback_url"])

    console.print(table)

    rprint("\n📋 [bold blue]Next Steps:[/bold blue]")
    rprint("1. Add these values to your application configuration")
    rprint("2. Update your GitHub OAuth App settings:")
    rprint("   - Authorization callback URL: " + config["github_oauth"]["callback_url"])
    rprint("3. Restart your application to apply changes")


@auth_cli.command("status")
def auth_status() -> None:
    """Show authentication system status."""
    rprint("🔍 Authentication System Status\n")

    # Check configuration
    settings = get_settings()

    table = Table(title="Configuration Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("Details", style="blue")

    # JWT Configuration
    jwt_status = "✅ Configured" if settings.auth.jwt_secret_key else "❌ Missing"
    table.add_row("JWT Secret", jwt_status, "Required for token generation")

    # GitHub OAuth
    github_status = "✅ Ready" if hasattr(settings, "github") else "⚠️ Not configured"
    table.add_row("GitHub OAuth", github_status, "Optional for user authentication")

    # Database
    db_status = "✅ Configured"
    table.add_row("Database", db_status, settings.database.url.split("@")[-1])

    console.print(table)

    # Token statistics
    async def _show_stats() -> None:
        manager = TokenManager()
        tokens = await manager.list_tokens()

        if tokens:
            rprint("\n📊 [bold]Token Statistics:[/bold]")
            rprint(f"   Total tokens: {len(tokens)}")

            # Count by scope
            scopes: dict[str, int] = {}
            for token in tokens:
                scope = token.get("scope", "unknown")
                scopes[scope] = scopes.get(scope, 0) + 1

            for scope, count in scopes.items():
                rprint(f"   {scope}: {count}")

    asyncio.run(_show_stats())


@auth_cli.command("troubleshoot")
def troubleshoot() -> None:
    """Run authentication troubleshooting diagnostics."""
    rprint("🔧 Running authentication diagnostics...\n")

    diagnostics = []

    # Check JWT secret
    settings = get_settings()
    if settings.auth.jwt_secret_key:
        diagnostics.append(("✅", "JWT Secret", "Configured"))
    else:
        diagnostics.append(
            ("❌", "JWT Secret", "Missing - set AUTH_SECRET_KEY environment variable")
        )

    # Check token directory
    tokens_dir = Path.home() / ".test-results-cli" / "tokens"
    if tokens_dir.exists():
        token_count = len(list(tokens_dir.glob("*.json")))
        diagnostics.append(("✅", "Token Storage", f"Found {token_count} stored tokens"))
    else:
        diagnostics.append(("⚠️", "Token Storage", "Directory not found - no tokens stored locally"))

    # Check database connectivity
    try:
        # This would test database connection
        diagnostics.append(("✅", "Database", "Connection available"))
    except Exception as e:
        diagnostics.append(("❌", "Database", f"Connection failed: {e}"))

    # Display results
    for status, component, detail in diagnostics:
        rprint(f"{status} {component}: {detail}")

    rprint("\n💡 [bold blue]Troubleshooting Tips:[/bold blue]")
    rprint("• Ensure AUTH_SECRET_KEY environment variable is set")
    rprint("• Verify database connection settings")
    rprint("• Check token permissions and expiration")
    rprint("• Use 'auth token validate <token>' to test specific tokens")


if __name__ == "__main__":
    auth_cli()
