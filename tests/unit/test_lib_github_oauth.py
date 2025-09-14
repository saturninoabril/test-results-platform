"""
Unit tests for GitHub OAuth integration.
Tests OAuth flow, user profile extraction, role mapping, and permission system.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.lib.auth import UserRole
from src.lib.github_oauth import (
    GitHubOAuthClient,
    GitHubOAuthResult,
    GitHubOrganization,
    GitHubUserProfile,
    RoleMapper,
    get_github_oauth_client,
)


class TestGitHubUserProfile:
    """Test GitHubUserProfile model."""

    def test_github_user_profile_creation(self):
        """Test GitHub user profile creation."""
        profile = GitHubUserProfile(
            id=12345,
            login="testuser",
            email="test@example.com",
            name="Test User",
            avatar_url="https://avatars.githubusercontent.com/u/12345",
            company="Test Company",
            blog="https://test.com",
            location="Test City",
            bio="Test bio",
            public_repos=10,
            followers=5,
            following=15,
            created_at="2020-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )

        assert profile.id == 12345
        assert profile.login == "testuser"
        assert profile.email == "test@example.com"
        assert profile.name == "Test User"
        assert profile.public_repos == 10

    def test_github_user_profile_optional_fields(self):
        """Test profile with optional fields as None."""
        profile = GitHubUserProfile(
            id=12345,
            login="testuser",
            avatar_url="https://avatars.githubusercontent.com/u/12345",
            public_repos=10,
            followers=5,
            following=15,
            created_at="2020-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )

        assert profile.email is None
        assert profile.name is None
        assert profile.company is None


class TestGitHubOrganization:
    """Test GitHubOrganization model."""

    def test_github_organization_creation(self):
        """Test GitHub organization creation."""
        org = GitHubOrganization(
            id=67890,
            login="test-org",
            description="Test Organization",
            avatar_url="https://avatars.githubusercontent.com/u/67890",
        )

        assert org.id == 67890
        assert org.login == "test-org"
        assert org.description == "Test Organization"


class TestRoleMapper:
    """Test role mapping functionality."""

    @pytest.fixture
    def role_mapper(self):
        """Create role mapper instance."""
        return RoleMapper()

    def test_role_mapper_initialization(self, role_mapper):
        """Test role mapper initialization."""
        assert isinstance(role_mapper, RoleMapper)
        # Should have some default configuration
        assert len(role_mapper._admin_users) >= 0

    def test_determine_role_admin_by_username(self, role_mapper):
        """Test admin role assignment by username."""
        # Add test user as admin
        role_mapper.add_admin_user("admin-user")

        profile = GitHubUserProfile(
            id=12345,
            login="admin-user",
            avatar_url="https://avatars.githubusercontent.com/u/12345",
            public_repos=10,
            followers=5,
            following=15,
            created_at="2020-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )

        role = role_mapper.determine_role(profile, [])
        assert role == UserRole.ADMIN

    def test_determine_role_admin_by_organization(self, role_mapper):
        """Test admin role assignment by organization."""
        # Add test org as admin org
        role_mapper.add_admin_organization("admin-org")

        profile = GitHubUserProfile(
            id=12345,
            login="regular-user",
            avatar_url="https://avatars.githubusercontent.com/u/12345",
            public_repos=10,
            followers=5,
            following=15,
            created_at="2020-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )

        org = GitHubOrganization(
            id=67890,
            login="admin-org",
            avatar_url="https://avatars.githubusercontent.com/u/67890",
        )

        role = role_mapper.determine_role(profile, [org])
        assert role == UserRole.ADMIN

    def test_determine_role_user_by_email_domain(self, role_mapper):
        """Test user role assignment by email domain."""
        # Add email domain for user role
        role_mapper._user_email_domains.add("company.com")

        profile = GitHubUserProfile(
            id=12345,
            login="employee",
            email="employee@company.com",
            avatar_url="https://avatars.githubusercontent.com/u/12345",
            public_repos=10,
            followers=5,
            following=15,
            created_at="2020-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )

        role = role_mapper.determine_role(profile, [])
        assert role == UserRole.USER

    def test_determine_role_default(self, role_mapper):
        """Test default role assignment."""
        profile = GitHubUserProfile(
            id=12345,
            login="random-user",
            email="random@random.com",
            avatar_url="https://avatars.githubusercontent.com/u/12345",
            public_repos=10,
            followers=5,
            following=15,
            created_at="2020-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )

        role = role_mapper.determine_role(profile, [])
        assert role == UserRole.USER  # Default role

    def test_add_remove_admin_user(self, role_mapper):
        """Test adding and removing admin users."""
        username = "test-admin"

        # Add admin user
        role_mapper.add_admin_user(username)
        assert username in role_mapper._admin_users

        # Remove admin user
        role_mapper.remove_admin_user(username)
        assert username not in role_mapper._admin_users

    def test_get_role_permissions(self, role_mapper):
        """Test getting permissions for different roles."""
        admin_perms = role_mapper.get_role_permissions(UserRole.ADMIN)
        user_perms = role_mapper.get_role_permissions(UserRole.USER)
        readonly_perms = role_mapper.get_role_permissions(UserRole.READONLY)

        # Admin should have all permissions
        assert len(admin_perms) > len(user_perms)
        assert len(user_perms) > len(readonly_perms)

        # Check some specific permissions
        assert "users:delete" in admin_perms
        assert "users:delete" not in user_perms
        assert "results:read" in readonly_perms
        assert "results:write" not in readonly_perms


class TestGitHubOAuthClient:
    """Test GitHub OAuth client functionality."""

    @pytest.fixture
    def oauth_client(self):
        """Create OAuth client instance."""
        return GitHubOAuthClient()

    def test_oauth_client_initialization(self, oauth_client):
        """Test OAuth client initialization."""
        assert isinstance(oauth_client, GitHubOAuthClient)
        assert oauth_client.auth_url == "https://github.com/login/oauth/authorize"
        assert oauth_client.token_url == "https://github.com/login/oauth/access_token"
        assert "user:email" in oauth_client.scopes
        assert "read:org" in oauth_client.scopes

    @patch("src.lib.github_oauth.get_settings")
    def test_get_authorization_url(self, mock_get_settings, oauth_client):
        """Test authorization URL generation."""
        # Mock settings
        mock_settings = MagicMock()
        mock_settings.auth.github_client_id = "test_client_id"
        mock_settings.auth.github_redirect_uri = "http://localhost:8000/auth/callback"
        mock_get_settings.return_value = mock_settings
        oauth_client.settings = mock_settings

        result = oauth_client.get_authorization_url()

        assert "authorization_url" in result
        assert "state" in result
        assert "github.com/login/oauth/authorize" in result["authorization_url"]
        assert "test_client_id" in result["authorization_url"]
        assert len(result["state"]) > 20  # Should be a secure random string

    @patch("src.lib.github_oauth.get_settings")
    def test_get_authorization_url_custom_state(self, mock_get_settings, oauth_client):
        """Test authorization URL with custom state."""
        mock_settings = MagicMock()
        mock_settings.auth.github_client_id = "test_client_id"
        mock_settings.auth.github_redirect_uri = "http://localhost:8000/auth/callback"
        mock_get_settings.return_value = mock_settings
        oauth_client.settings = mock_settings

        custom_state = "custom_state_value"
        result = oauth_client.get_authorization_url(state=custom_state)

        assert result["state"] == custom_state

    @patch("src.lib.github_oauth.get_settings")
    def test_get_authorization_url_no_client_id(self, mock_get_settings, oauth_client):
        """Test authorization URL generation without client ID."""
        mock_settings = MagicMock()
        mock_settings.auth.github_client_id = None
        mock_get_settings.return_value = mock_settings
        oauth_client.settings = mock_settings

        with pytest.raises(ValueError, match="GitHub OAuth client ID not configured"):
            oauth_client.get_authorization_url()

    @pytest.mark.asyncio
    @patch("src.lib.github_oauth.get_settings")
    @patch("httpx.AsyncClient")
    async def test_exchange_code_for_token_success(
        self, mock_httpx_client, mock_get_settings, oauth_client
    ):
        """Test successful code to token exchange."""
        # Mock settings
        mock_settings = MagicMock()
        mock_settings.auth.github_client_id = "test_client_id"
        mock_settings.auth.github_client_secret = "test_client_secret"
        mock_settings.auth.github_redirect_uri = "http://localhost:8000/auth/callback"
        mock_get_settings.return_value = mock_settings
        oauth_client.settings = mock_settings

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "github_access_token"}
        mock_response.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client

        token = await oauth_client.exchange_code_for_token("auth_code", "state_value")

        assert token == "github_access_token"
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.lib.github_oauth.get_settings")
    @patch("httpx.AsyncClient")
    async def test_exchange_code_for_token_error(
        self, mock_httpx_client, mock_get_settings, oauth_client
    ):
        """Test code to token exchange with error response."""
        mock_settings = MagicMock()
        mock_settings.auth.github_client_id = "test_client_id"
        mock_settings.auth.github_client_secret = "test_client_secret"
        mock_settings.auth.github_redirect_uri = "http://localhost:8000/auth/callback"
        mock_get_settings.return_value = mock_settings
        oauth_client.settings = mock_settings

        # Mock error response
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": "invalid_grant"}
        mock_response.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client

        token = await oauth_client.exchange_code_for_token("bad_code", "state_value")

        assert token is None

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_get_user_profile_success(self, mock_httpx_client, oauth_client):
        """Test successful user profile retrieval."""
        # Mock user profile response
        mock_user_response = MagicMock()
        mock_user_response.json.return_value = {
            "id": 12345,
            "login": "testuser",
            "email": "test@example.com",
            "name": "Test User",
            "avatar_url": "https://avatars.githubusercontent.com/u/12345",
            "company": "Test Co",
            "public_repos": 10,
            "followers": 5,
            "following": 15,
            "created_at": "2020-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        }
        mock_user_response.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_user_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client

        profile = await oauth_client.get_user_profile("access_token")

        assert profile is not None
        assert profile.login == "testuser"
        assert profile.id == 12345
        assert profile.email == "test@example.com"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_get_user_profile_fetch_email(self, mock_httpx_client, oauth_client):
        """Test user profile retrieval with separate email fetch."""
        # Mock user profile response without email
        mock_user_response = MagicMock()
        mock_user_response.json.return_value = {
            "id": 12345,
            "login": "testuser",
            "email": None,  # No public email
            "name": "Test User",
            "avatar_url": "https://avatars.githubusercontent.com/u/12345",
            "public_repos": 10,
            "followers": 5,
            "following": 15,
            "created_at": "2020-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        }
        mock_user_response.raise_for_status.return_value = None

        # Mock email response
        mock_email_response = MagicMock()
        mock_email_response.json.return_value = [
            {"email": "test@example.com", "primary": True, "verified": True}
        ]
        mock_email_response.is_success = True

        mock_client = AsyncMock()
        mock_client.get.side_effect = [mock_user_response, mock_email_response]
        mock_httpx_client.return_value.__aenter__.return_value = mock_client

        profile = await oauth_client.get_user_profile("access_token")

        assert profile is not None
        assert profile.email == "test@example.com"
        assert mock_client.get.call_count == 2  # User profile + emails

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_get_user_organizations(self, mock_httpx_client, oauth_client):
        """Test user organizations retrieval."""
        # Mock organizations response
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": 67890,
                "login": "test-org",
                "description": "Test Organization",
                "avatar_url": "https://avatars.githubusercontent.com/u/67890",
            }
        ]
        mock_response.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client

        orgs = await oauth_client.get_user_organizations("access_token")

        assert len(orgs) == 1
        assert orgs[0].login == "test-org"
        assert orgs[0].id == 67890

    @pytest.mark.asyncio
    @patch("src.lib.github_oauth.get_settings")
    async def test_authenticate_user_success(self, mock_get_settings, oauth_client):
        """Test complete authentication flow success."""
        # Mock settings
        mock_settings = MagicMock()
        mock_settings.auth.github_client_id = "test_client_id"
        mock_settings.auth.github_client_secret = "test_client_secret"
        mock_settings.auth.github_redirect_uri = "http://localhost:8000/auth/callback"
        mock_get_settings.return_value = mock_settings
        oauth_client.settings = mock_settings

        # Mock all the methods
        oauth_client.exchange_code_for_token = AsyncMock(return_value="github_token")
        oauth_client.get_user_profile = AsyncMock(
            return_value=GitHubUserProfile(
                id=12345,
                login="testuser",
                email="test@example.com",
                avatar_url="https://avatars.githubusercontent.com/u/12345",
                public_repos=10,
                followers=5,
                following=15,
                created_at="2020-01-01T00:00:00Z",
                updated_at="2025-01-01T00:00:00Z",
            )
        )
        oauth_client.get_user_organizations = AsyncMock(return_value=[])

        # Mock token manager
        oauth_client.token_manager.create_user_tokens = AsyncMock(
            return_value={
                "access_token": "app_access_token",
                "refresh_token": "app_refresh_token",
            }
        )

        result = await oauth_client.authenticate_user("auth_code", "state_value")

        assert result.success is True
        assert result.user_profile is not None
        assert result.user_profile.login == "testuser"
        assert result.access_token == "app_access_token"
        assert result.refresh_token == "app_refresh_token"
        assert result.user_role is not None

    @pytest.mark.asyncio
    async def test_authenticate_user_token_exchange_failure(self, oauth_client):
        """Test authentication failure during token exchange."""
        oauth_client.exchange_code_for_token = AsyncMock(return_value=None)

        result = await oauth_client.authenticate_user("bad_code", "state_value")

        assert result.success is False
        assert "Failed to exchange authorization code" in result.error

    @pytest.mark.asyncio
    async def test_authenticate_user_profile_failure(self, oauth_client):
        """Test authentication failure during profile retrieval."""
        oauth_client.exchange_code_for_token = AsyncMock(return_value="github_token")
        oauth_client.get_user_profile = AsyncMock(return_value=None)

        result = await oauth_client.authenticate_user("auth_code", "state_value")

        assert result.success is False
        assert "Failed to retrieve user profile" in result.error

    def test_get_user_permissions(self, oauth_client):
        """Test getting user permissions."""
        admin_perms = oauth_client.get_user_permissions(UserRole.ADMIN)
        user_perms = oauth_client.get_user_permissions(UserRole.USER)

        assert len(admin_perms) > len(user_perms)
        assert "users:delete" in admin_perms
        assert "users:delete" not in user_perms


class TestUtilityFunctions:
    """Test utility functions."""

    @pytest.mark.asyncio
    async def test_get_github_oauth_client_singleton(self):
        """Test GitHub OAuth client singleton pattern."""
        client1 = await get_github_oauth_client()
        client2 = await get_github_oauth_client()

        assert client1 is client2  # Should be the same instance
        assert isinstance(client1, GitHubOAuthClient)


class TestGitHubOAuthResult:
    """Test GitHubOAuthResult model."""

    def test_oauth_result_success(self):
        """Test successful OAuth result."""
        profile = GitHubUserProfile(
            id=12345,
            login="testuser",
            avatar_url="https://avatars.githubusercontent.com/u/12345",
            public_repos=10,
            followers=5,
            following=15,
            created_at="2020-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )

        result = GitHubOAuthResult(
            success=True,
            user_profile=profile,
            user_role=UserRole.USER,
            access_token="access_token",
            refresh_token="refresh_token",
        )

        assert result.success is True
        assert result.user_profile == profile
        assert result.user_role == UserRole.USER
        assert result.access_token == "access_token"

    def test_oauth_result_failure(self):
        """Test failed OAuth result."""
        result = GitHubOAuthResult(
            success=False,
            error="Authentication failed",
        )

        assert result.success is False
        assert result.error == "Authentication failed"
        assert result.user_profile is None
        assert result.access_token is None
