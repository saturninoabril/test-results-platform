"""
GitHub OAuth integration for SSO authentication.
Handles OAuth flow, user profile extraction, and role mapping with permission system.
"""

import secrets
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlencode

import httpx
import structlog
from pydantic import BaseModel, Field

from .auth import TokenManager, UserRole
from .config import get_settings

logger = structlog.get_logger()


class GitHubUserProfile(BaseModel):
    """GitHub user profile information."""
    id: int = Field(..., description="GitHub user ID")
    login: str = Field(..., description="GitHub username")
    email: Optional[str] = Field(None, description="Primary email address")
    name: Optional[str] = Field(None, description="Full name")
    avatar_url: str = Field(..., description="Avatar URL")
    company: Optional[str] = Field(None, description="Company")
    blog: Optional[str] = Field(None, description="Blog/website URL")
    location: Optional[str] = Field(None, description="Location")
    bio: Optional[str] = Field(None, description="Biography")
    public_repos: int = Field(..., description="Number of public repositories")
    followers: int = Field(..., description="Number of followers")
    following: int = Field(..., description="Number of following")
    created_at: str = Field(..., description="Account creation date")
    updated_at: str = Field(..., description="Last profile update")


class GitHubOrganization(BaseModel):
    """GitHub organization information."""
    id: int = Field(..., description="Organization ID")
    login: str = Field(..., description="Organization name")
    description: Optional[str] = Field(None, description="Organization description")
    avatar_url: str = Field(..., description="Organization avatar URL")


class GitHubOAuthResult(BaseModel):
    """Result of GitHub OAuth authentication."""
    success: bool
    user_profile: Optional[GitHubUserProfile] = None
    user_role: Optional[UserRole] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    error: Optional[str] = None
    organizations: List[GitHubOrganization] = Field(default_factory=list)


class RoleMapper:
    """Maps GitHub users to application roles based on configurable rules."""

    def __init__(self) -> None:
        """Initialize role mapper with default rules."""
        # In a real application, these would be configurable via database/config
        self._admin_users: Set[str] = set()  # GitHub usernames
        self._admin_organizations: Set[str] = set()  # GitHub org names
        self._readonly_users: Set[str] = set()
        self._user_email_domains: Set[str] = set()  # Email domains for user role

        # Load default configuration
        self._load_default_config()

    def _load_default_config(self) -> None:
        """Load default role mapping configuration."""
        # Note: Role mapping configuration should be loaded from environment variables
        # or configuration file in production. Using development defaults for now.
        # Environment variables: GITHUB_ADMIN_USERS, GITHUB_ADMIN_ORGS, USER_EMAIL_DOMAINS

        # Example admin users (GitHub usernames)
        self._admin_users = {"admin", "ops-team"}

        # Example admin organizations
        self._admin_organizations = {"my-company-ops", "platform-team"}

        # Example email domains that get user role
        self._user_email_domains = {"example.com", "company.com"}

        logger.info(
            "Role mapper initialized",
            admin_users=list(self._admin_users),
            admin_orgs=list(self._admin_organizations),
        )

    def determine_role(
        self,
        profile: GitHubUserProfile,
        organizations: List[GitHubOrganization],
    ) -> UserRole:
        """Determine user role based on profile and organization membership."""

        # Check for admin role based on username
        if profile.login in self._admin_users:
            logger.info("User granted admin role by username", username=profile.login)
            return UserRole.ADMIN

        # Check for admin role based on organization membership
        for org in organizations:
            if org.login in self._admin_organizations:
                logger.info(
                    "User granted admin role by organization",
                    username=profile.login,
                    organization=org.login,
                )
                return UserRole.ADMIN

        # Check for readonly users
        if profile.login in self._readonly_users:
            logger.info("User granted readonly role", username=profile.login)
            return UserRole.READONLY

        # Check email domain for user role
        if profile.email:
            email_domain = profile.email.split('@')[-1]
            if email_domain in self._user_email_domains:
                logger.info("User granted user role by email domain", email=profile.email)
                return UserRole.USER

        # Default role for authenticated users
        logger.info("User granted default user role", username=profile.login)
        return UserRole.USER

    def add_admin_user(self, username: str) -> None:
        """Add user to admin list."""
        self._admin_users.add(username)
        logger.info("Added admin user", username=username)

    def remove_admin_user(self, username: str) -> None:
        """Remove user from admin list."""
        self._admin_users.discard(username)
        logger.info("Removed admin user", username=username)

    def add_admin_organization(self, org_name: str) -> None:
        """Add organization to admin list."""
        self._admin_organizations.add(org_name)
        logger.info("Added admin organization", organization=org_name)

    def get_role_permissions(self, role: UserRole) -> List[str]:
        """Get permissions for a given role."""
        role_permissions = {
            UserRole.ADMIN: [
                "results:read", "results:write", "results:delete",
                "suites:read", "suites:write", "suites:delete",
                "artifacts:read", "artifacts:write", "artifacts:delete",
                "frameworks:read", "frameworks:write", "frameworks:delete",
                "environments:read", "environments:write", "environments:delete",
                "users:read", "users:write", "users:delete",
                "automation:read", "automation:write", "automation:delete",
            ],
            UserRole.USER: [
                "results:read", "results:write",
                "suites:read", "suites:write",
                "artifacts:read", "artifacts:write",
                "frameworks:read", "frameworks:write",
                "environments:read", "environments:write",
            ],
            UserRole.READONLY: [
                "results:read",
                "suites:read",
                "artifacts:read",
                "frameworks:read",
                "environments:read",
            ],
        }

        return role_permissions.get(role, [])


class GitHubOAuthClient:
    """GitHub OAuth client for SSO authentication."""

    def __init__(self) -> None:
        """Initialize GitHub OAuth client."""
        self.settings = get_settings()
        self.role_mapper = RoleMapper()
        self.token_manager = TokenManager()

        # GitHub OAuth endpoints
        self.auth_url = "https://github.com/login/oauth/authorize"
        self.token_url = "https://github.com/login/oauth/access_token"
        self.api_base_url = "https://api.github.com"

        # OAuth scopes needed
        self.scopes = ["user:email", "read:org"]

    def get_authorization_url(self, state: Optional[str] = None) -> Dict[str, str]:
        """Generate GitHub OAuth authorization URL."""
        if not self.settings.auth.github_client_id:
            raise ValueError("GitHub OAuth client ID not configured")

        if state is None:
            state = secrets.token_urlsafe(32)

        params = {
            "client_id": self.settings.auth.github_client_id,
            "redirect_uri": self.settings.auth.github_redirect_uri,
            "scope": " ".join(self.scopes),
            "state": state,
            "response_type": "code",
        }

        auth_url = f"{self.auth_url}?{urlencode(params)}"

        logger.info(
            "Generated GitHub OAuth URL",
            redirect_uri=self.settings.auth.github_redirect_uri,
            scopes=self.scopes,
            state=state[:8],  # Log only first 8 chars for security
        )

        return {
            "authorization_url": auth_url,
            "state": state,
        }

    async def exchange_code_for_token(self, code: str, state: str) -> Optional[str]:
        """Exchange authorization code for access token."""
        if not self.settings.auth.github_client_id or not self.settings.auth.github_client_secret:
            raise ValueError("GitHub OAuth credentials not configured")

        data = {
            "client_id": self.settings.auth.github_client_id,
            "client_secret": self.settings.auth.github_client_secret,
            "code": code,
            "redirect_uri": self.settings.auth.github_redirect_uri,
            "state": state,
        }

        headers = {
            "Accept": "application/json",
            "User-Agent": "test-results-api/1.0",
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.token_url,
                    data=data,
                    headers=headers,
                    timeout=30.0,
                )

                response.raise_for_status()
                token_data = response.json()

                if "error" in token_data:
                    logger.error("GitHub OAuth token exchange failed", error=token_data["error"])
                    return None

                access_token = token_data.get("access_token")
                if not access_token:
                    logger.error("No access token in GitHub response")
                    return None

                logger.info("GitHub OAuth token exchange successful")
                return str(access_token)

            except httpx.HTTPError as e:
                logger.error("GitHub OAuth token exchange HTTP error", error=str(e))
                return None
            except Exception as e:
                logger.error("GitHub OAuth token exchange error", error=str(e))
                return None

    async def get_user_profile(self, access_token: str) -> Optional[GitHubUserProfile]:
        """Get user profile from GitHub API."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "test-results-api/1.0",
        }

        async with httpx.AsyncClient() as client:
            try:
                # Get user profile
                response = await client.get(
                    f"{self.api_base_url}/user",
                    headers=headers,
                    timeout=30.0,
                )

                response.raise_for_status()
                user_data = response.json()

                # Get user's primary email if not public
                if not user_data.get("email"):
                    email_response = await client.get(
                        f"{self.api_base_url}/user/emails",
                        headers=headers,
                        timeout=30.0,
                    )

                    if email_response.is_success:
                        emails = email_response.json()
                        primary_email = next(
                            (email["email"] for email in emails if email["primary"]),
                            None
                        )
                        if primary_email:
                            user_data["email"] = primary_email

                profile = GitHubUserProfile(**user_data)
                logger.info("Retrieved GitHub user profile", username=profile.login, user_id=profile.id)
                return profile

            except httpx.HTTPError as e:
                logger.error("GitHub API user profile HTTP error", error=str(e))
                return None
            except Exception as e:
                logger.error("GitHub API user profile error", error=str(e))
                return None

    async def get_user_organizations(self, access_token: str) -> List[GitHubOrganization]:
        """Get user's organization memberships."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "test-results-api/1.0",
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.api_base_url}/user/orgs",
                    headers=headers,
                    timeout=30.0,
                )

                response.raise_for_status()
                orgs_data = response.json()

                organizations = [GitHubOrganization(**org) for org in orgs_data]
                logger.info(
                    "Retrieved user organizations",
                    count=len(organizations),
                    orgs=[org.login for org in organizations],
                )
                return organizations

            except httpx.HTTPError as e:
                logger.error("GitHub API organizations HTTP error", error=str(e))
                return []
            except Exception as e:
                logger.error("GitHub API organizations error", error=str(e))
                return []

    async def authenticate_user(self, code: str, state: str) -> GitHubOAuthResult:
        """Complete GitHub OAuth authentication flow."""
        try:
            # Exchange code for access token
            github_token = await self.exchange_code_for_token(code, state)
            if not github_token:
                return GitHubOAuthResult(
                    success=False,
                    error="Failed to exchange authorization code for access token"
                )

            # Get user profile
            profile = await self.get_user_profile(github_token)
            if not profile:
                return GitHubOAuthResult(
                    success=False,
                    error="Failed to retrieve user profile from GitHub"
                )

            # Get user organizations
            organizations = await self.get_user_organizations(github_token)

            # Determine user role
            user_role = self.role_mapper.determine_role(profile, organizations)

            # Generate application tokens
            user_id = f"github:{profile.id}"
            tokens = await self.token_manager.create_user_tokens(
                user_id=user_id,
                username=profile.login,
                email=profile.email or f"{profile.login}@github.local",
                role=user_role,
                github_id=profile.id,
            )

            logger.info(
                "GitHub OAuth authentication successful",
                username=profile.login,
                user_id=user_id,
                role=user_role.value,
                organizations=[org.login for org in organizations],
            )

            return GitHubOAuthResult(
                success=True,
                user_profile=profile,
                user_role=user_role,
                access_token=tokens["access_token"],
                refresh_token=tokens["refresh_token"],
                organizations=organizations,
            )

        except Exception as e:
            logger.error("GitHub OAuth authentication error", error=str(e))
            return GitHubOAuthResult(
                success=False,
                error=f"Authentication error: {str(e)}"
            )

    def get_user_permissions(self, role: UserRole) -> List[str]:
        """Get user permissions based on role."""
        return self.role_mapper.get_role_permissions(role)

    async def refresh_github_token(self, refresh_token: str) -> Optional[Dict[str, str]]:
        """Refresh GitHub access token (if supported by GitHub in the future)."""
        # GitHub currently doesn't support refresh tokens for OAuth apps
        # This is a placeholder for future implementation
        logger.warning("GitHub OAuth refresh tokens not supported")
        return None


# Global OAuth client instance
_github_oauth_client: Optional[GitHubOAuthClient] = None


async def get_github_oauth_client() -> GitHubOAuthClient:
    """Get or create GitHub OAuth client instance."""
    global _github_oauth_client
    if _github_oauth_client is None:
        _github_oauth_client = GitHubOAuthClient()
    return _github_oauth_client