"""
CLI Configuration utilities for Test Results Management API.
Handles CLI-specific configuration, profiles, and settings management.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

import click
from rich import print as rprint


class CLIConfig:
    """Manages CLI configuration and profiles."""

    def __init__(self):
        self.config_dir = Path.home() / ".test-results-cli"
        self.config_file = self.config_dir / "config.json"
        self.profiles_file = self.config_dir / "profiles.json"
        self.config_dir.mkdir(exist_ok=True)

    def load_config(self) -> Dict[str, Any]:
        """Load CLI configuration."""
        if self.config_file.exists():
            with open(self.config_file) as f:
                return json.load(f)
        return self._default_config()

    def save_config(self, config: Dict[str, Any]) -> None:
        """Save CLI configuration."""
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)

    def _default_config(self) -> Dict[str, Any]:
        """Default CLI configuration."""
        return {
            "default_profile": "default",
            "output_format": "table",
            "verbose": False,
            "auto_update_check": True,
            "token_expiry_warning_days": 30
        }

    def load_profiles(self) -> Dict[str, Any]:
        """Load CLI profiles."""
        if self.profiles_file.exists():
            with open(self.profiles_file) as f:
                return json.load(f)
        return {"default": self._default_profile()}

    def save_profiles(self, profiles: Dict[str, Any]) -> None:
        """Save CLI profiles."""
        with open(self.profiles_file, 'w') as f:
            json.dump(profiles, f, indent=2)

    def _default_profile(self) -> Dict[str, Any]:
        """Default profile configuration."""
        return {
            "name": "default",
            "api_endpoint": os.getenv("TEST_RESULTS_API_ENDPOINT", ""),
            "default_scope": "automation",
            "default_expires_days": 365,
            "github_integration": {
                "enabled": False,
                "default_workflow_path": ".github/workflows/"
            }
        }

    def get_active_profile(self) -> Dict[str, Any]:
        """Get the currently active profile."""
        config = self.load_config()
        profiles = self.load_profiles()
        profile_name = config.get("default_profile", "default")
        return profiles.get(profile_name, self._default_profile())

    def set_active_profile(self, profile_name: str) -> bool:
        """Set the active profile."""
        profiles = self.load_profiles()
        if profile_name not in profiles:
            return False

        config = self.load_config()
        config["default_profile"] = profile_name
        self.save_config(config)
        return True


@click.group()
def config_cli():
    """Manage CLI configuration and profiles."""
    pass


@config_cli.command('show')
@click.option('--profile', help='Show specific profile')
def show_config(profile):
    """Show current configuration."""
    cli_config = CLIConfig()

    if profile:
        profiles = cli_config.load_profiles()
        if profile in profiles:
            rprint(f"[bold]Profile: {profile}[/bold]")
            rprint(json.dumps(profiles[profile], indent=2))
        else:
            rprint(f"❌ Profile '{profile}' not found")
    else:
        config = cli_config.load_config()
        active_profile = cli_config.get_active_profile()

        rprint("[bold]CLI Configuration:[/bold]")
        rprint(json.dumps(config, indent=2))
        rprint(f"\n[bold]Active Profile: {config['default_profile']}[/bold]")
        rprint(json.dumps(active_profile, indent=2))


@config_cli.command('set')
@click.argument('key')
@click.argument('value')
@click.option('--profile', help='Set value in specific profile')
def set_config(key, value, profile):
    """Set a configuration value.

    Examples:
      config set output_format json
      config set api_endpoint https://api.example.com --profile production
    """
    cli_config = CLIConfig()

    if profile:
        profiles = cli_config.load_profiles()
        if profile not in profiles:
            profiles[profile] = cli_config._default_profile()
            profiles[profile]["name"] = profile

        # Handle nested keys
        keys = key.split('.')
        current = profiles[profile]
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        # Convert value type
        if value.lower() in ('true', 'false'):
            value = value.lower() == 'true'
        elif value.isdigit():
            value = int(value)

        current[keys[-1]] = value
        cli_config.save_profiles(profiles)
        rprint(f"✅ Set {key} = {value} in profile '{profile}'")
    else:
        config = cli_config.load_config()

        # Handle nested keys
        keys = key.split('.')
        current = config
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        # Convert value type
        if value.lower() in ('true', 'false'):
            value = value.lower() == 'true'
        elif value.isdigit():
            value = int(value)

        current[keys[-1]] = value
        cli_config.save_config(config)
        rprint(f"✅ Set {key} = {value}")


@config_cli.group()
def profile():
    """Manage CLI profiles."""
    pass


@profile.command('list')
def list_profiles():
    """List all profiles."""
    cli_config = CLIConfig()
    config = cli_config.load_config()
    profiles = cli_config.load_profiles()
    active = config.get("default_profile", "default")

    rprint("[bold]Available Profiles:[/bold]\n")

    for name, profile_config in profiles.items():
        status = "[green]●[/green] ACTIVE" if name == active else "[dim]○[/dim]        "
        endpoint = profile_config.get("api_endpoint", "Not set")
        rprint(f"{status} [cyan]{name}[/cyan] - {endpoint}")


@profile.command('create')
@click.argument('name')
@click.option('--api-endpoint', help='API endpoint URL')
@click.option('--copy-from', help='Copy settings from existing profile')
@click.option('--activate', is_flag=True, help='Make this the active profile')
def create_profile(name, api_endpoint, copy_from, activate):
    """Create a new profile.

    Examples:
      config profile create production --api-endpoint https://api.prod.com --activate
      config profile create staging --copy-from production
    """
    cli_config = CLIConfig()
    profiles = cli_config.load_profiles()

    if name in profiles:
        rprint(f"❌ Profile '{name}' already exists")
        return

    if copy_from:
        if copy_from not in profiles:
            rprint(f"❌ Profile '{copy_from}' not found")
            return
        new_profile = profiles[copy_from].copy()
        new_profile["name"] = name
    else:
        new_profile = cli_config._default_profile()
        new_profile["name"] = name

    if api_endpoint:
        new_profile["api_endpoint"] = api_endpoint

    profiles[name] = new_profile
    cli_config.save_profiles(profiles)

    if activate:
        cli_config.set_active_profile(name)

    rprint(f"✅ Created profile '{name}'")
    if activate:
        rprint(f"✅ Activated profile '{name}'")


@profile.command('activate')
@click.argument('name')
def activate_profile(name):
    """Activate a profile."""
    cli_config = CLIConfig()

    if cli_config.set_active_profile(name):
        rprint(f"✅ Activated profile '{name}'")
    else:
        rprint(f"❌ Profile '{name}' not found")


@profile.command('delete')
@click.argument('name')
@click.option('--yes', is_flag=True, help='Skip confirmation')
def delete_profile(name, yes):
    """Delete a profile."""
    if name == 'default':
        rprint("❌ Cannot delete the default profile")
        return

    if not yes:
        if not click.confirm(f"Delete profile '{name}'?"):
            rprint("❌ Cancelled")
            return

    cli_config = CLIConfig()
    profiles = cli_config.load_profiles()

    if name not in profiles:
        rprint(f"❌ Profile '{name}' not found")
        return

    del profiles[name]
    cli_config.save_profiles(profiles)

    # If this was the active profile, switch to default
    config = cli_config.load_config()
    if config.get("default_profile") == name:
        config["default_profile"] = "default"
        cli_config.save_config(config)
        rprint("⚠️  Switched to default profile")

    rprint(f"✅ Deleted profile '{name}'")


if __name__ == '__main__':
    config_cli()