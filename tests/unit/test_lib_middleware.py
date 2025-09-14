"""
Unit tests for authentication middleware and dependencies.
Tests bearer token validation, user context, and permission-based access control.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from src.lib.middleware import (
    AuthenticatedUser,
    AuthenticatedAutomation,
    AuthenticationError,
    PermissionError,
    get_bearer_token,
    validate_token,
    get_current_user,
    get_current_automation,
    get_current_context,
    require_permissions,
    require_role,
    add_auth_context_to_request,
)
from src.lib.auth import TokenClaims, TokenScope, TokenType, TokenValidationResult, UserRole


class TestAuthenticationModels:
    """Test authentication model classes."""

    def test_authenticated_user_creation(self):
        """Test AuthenticatedUser model creation."""
        claims = TokenClaims(
            sub="github:123",
            exp=datetime.utcnow() + timedelta(hours=1),
            scope=TokenScope.USER,
            token_type=TokenType.ACCESS,
            username="testuser",
            email="test@example.com",
            role=UserRole.USER
        )

        user = AuthenticatedUser(
            user_id="github:123",
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
            github_id=123,
            permissions=["results:read", "results:write"],
            token_claims=claims
        )

        assert user.user_id == "github:123"
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.role == UserRole.USER
        assert user.github_id == 123
        assert "results:read" in user.permissions
        assert user.token_claims == claims

    def test_authenticated_automation_creation(self):
        """Test AuthenticatedAutomation model creation."""
        claims = TokenClaims(
            sub="automation:ci:abcd1234",
            exp=datetime.utcnow() + timedelta(days=30),
            scope=TokenScope.AUTOMATION,
            token_type=TokenType.AUTOMATION,
            automation_name="ci-system",
            permissions=["results:write", "artifacts:write"]
        )

        automation = AuthenticatedAutomation(
            automation_id="automation:ci:abcd1234",
            automation_name="ci-system",
            permissions=["results:write", "artifacts:write"],
            token_claims=claims
        )

        assert automation.automation_id == "automation:ci:abcd1234"
        assert automation.automation_name == "ci-system"
        assert "results:write" in automation.permissions
        assert automation.token_claims == claims


class TestBearerTokenExtraction:
    """Test bearer token extraction from Authorization header."""

    @pytest.mark.asyncio
    async def test_get_bearer_token_success(self):
        """Test successful bearer token extraction."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="test-token-123"
        )

        token = await get_bearer_token(credentials)
        assert token == "test-token-123"

    @pytest.mark.asyncio
    async def test_get_bearer_token_missing_credentials(self):
        """Test missing authorization credentials."""
        with pytest.raises(AuthenticationError) as exc_info:
            await get_bearer_token(None)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Missing authorization header" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_bearer_token_invalid_scheme(self):
        """Test invalid authorization scheme."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Basic",
            credentials="test-token-123"
        )

        with pytest.raises(AuthenticationError) as exc_info:
            await get_bearer_token(credentials)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid authorization scheme" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_bearer_token_empty_credentials(self):
        """Test empty token credentials."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=""
        )

        with pytest.raises(AuthenticationError) as exc_info:
            await get_bearer_token(credentials)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Missing token in authorization header" in str(exc_info.value.detail)


class TestTokenValidation:
    """Test JWT token validation."""

    @pytest.mark.asyncio
    @patch('src.lib.middleware.get_token_manager')
    async def test_validate_token_success(self, mock_get_token_manager):
        """Test successful token validation."""
        # Mock token manager
        mock_token_manager = AsyncMock()
        mock_jwt_auth = MagicMock()
        mock_token_manager.jwt_auth = mock_jwt_auth
        mock_get_token_manager.return_value = mock_token_manager

        # Mock validation result
        claims = TokenClaims(
            sub="github:123",
            exp=datetime.utcnow() + timedelta(hours=1),
            scope=TokenScope.USER,
            token_type=TokenType.ACCESS,
            username="testuser",
            email="test@example.com",
            role=UserRole.USER
        )
        mock_jwt_auth.validate_token.return_value = TokenValidationResult(
            valid=True,
            claims=claims,
            scope=TokenScope.USER
        )

        result = await validate_token("valid-token")
        assert result == claims

    @pytest.mark.asyncio
    @patch('src.lib.middleware.get_token_manager')
    async def test_validate_token_expired(self, mock_get_token_manager):
        """Test expired token validation."""
        mock_token_manager = AsyncMock()
        mock_jwt_auth = MagicMock()
        mock_token_manager.jwt_auth = mock_jwt_auth
        mock_get_token_manager.return_value = mock_token_manager

        mock_jwt_auth.validate_token.return_value = TokenValidationResult(
            valid=False,
            expired=True,
            error="Token has expired"
        )

        with pytest.raises(AuthenticationError) as exc_info:
            await validate_token("expired-token")

        assert "Token has expired" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    @patch('src.lib.middleware.get_token_manager')
    async def test_validate_token_invalid(self, mock_get_token_manager):
        """Test invalid token validation."""
        mock_token_manager = AsyncMock()
        mock_jwt_auth = MagicMock()
        mock_token_manager.jwt_auth = mock_jwt_auth
        mock_get_token_manager.return_value = mock_token_manager

        mock_jwt_auth.validate_token.return_value = TokenValidationResult(
            valid=False,
            error="Invalid signature"
        )

        with pytest.raises(AuthenticationError) as exc_info:
            await validate_token("invalid-token")

        assert "Invalid token" in str(exc_info.value.detail)


class TestUserAuthentication:
    """Test user authentication from token claims."""

    @pytest.mark.asyncio
    @patch('src.lib.middleware.get_github_oauth_client')
    async def test_get_current_user_success(self, mock_get_github_client):
        """Test successful user authentication."""
        # Mock GitHub OAuth client
        mock_github_client = MagicMock()
        mock_github_client.get_user_permissions.return_value = [
            "results:read", "results:write", "suites:read"
        ]
        mock_get_github_client.return_value = mock_github_client

        claims = TokenClaims(
            sub="github:123",
            exp=datetime.utcnow() + timedelta(hours=1),
            scope=TokenScope.USER,
            token_type=TokenType.ACCESS,
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
            github_id=123
        )

        user = await get_current_user(claims)

        assert isinstance(user, AuthenticatedUser)
        assert user.user_id == "github:123"
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.role == UserRole.USER
        assert user.github_id == 123
        assert "results:read" in user.permissions
        assert user.token_claims == claims

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_scope(self):
        """Test user authentication with invalid token scope."""
        claims = TokenClaims(
            sub="automation:ci:abcd1234",
            exp=datetime.utcnow() + timedelta(days=30),
            scope=TokenScope.AUTOMATION,
            token_type=TokenType.AUTOMATION,
            automation_name="ci-system"
        )

        with pytest.raises(AuthenticationError) as exc_info:
            await get_current_user(claims)

        assert "Invalid token scope" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_current_user_missing_claims(self):
        """Test user authentication with missing required claims."""
        claims = TokenClaims(
            sub="github:123",
            exp=datetime.utcnow() + timedelta(hours=1),
            scope=TokenScope.USER,
            token_type=TokenType.ACCESS
            # Missing username, email, role
        )

        with pytest.raises(AuthenticationError) as exc_info:
            await get_current_user(claims)

        assert "missing required user information" in str(exc_info.value.detail)


class TestAutomationAuthentication:
    """Test automation authentication from token claims."""

    @pytest.mark.asyncio
    async def test_get_current_automation_success(self):
        """Test successful automation authentication."""
        claims = TokenClaims(
            sub="automation:ci:abcd1234",
            exp=datetime.utcnow() + timedelta(days=30),
            scope=TokenScope.AUTOMATION,
            token_type=TokenType.AUTOMATION,
            automation_name="ci-system",
            permissions=["results:write", "artifacts:write"]
        )

        automation = await get_current_automation(claims)

        assert isinstance(automation, AuthenticatedAutomation)
        assert automation.automation_id == "automation:ci:abcd1234"
        assert automation.automation_name == "ci-system"
        assert "results:write" in automation.permissions
        assert automation.token_claims == claims

    @pytest.mark.asyncio
    async def test_get_current_automation_invalid_scope(self):
        """Test automation authentication with invalid token scope."""
        claims = TokenClaims(
            sub="github:123",
            exp=datetime.utcnow() + timedelta(hours=1),
            scope=TokenScope.USER,
            token_type=TokenType.ACCESS,
            username="testuser"
        )

        with pytest.raises(AuthenticationError) as exc_info:
            await get_current_automation(claims)

        assert "Invalid token scope" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_current_automation_missing_claims(self):
        """Test automation authentication with missing automation name."""
        claims = TokenClaims(
            sub="automation:ci:abcd1234",
            exp=datetime.utcnow() + timedelta(days=30),
            scope=TokenScope.AUTOMATION,
            token_type=TokenType.AUTOMATION
            # Missing automation_name
        )

        with pytest.raises(AuthenticationError) as exc_info:
            await get_current_automation(claims)

        assert "missing automation information" in str(exc_info.value.detail)


class TestContextAuthentication:
    """Test generic context authentication."""

    @pytest.mark.asyncio
    @patch('src.lib.middleware.get_github_oauth_client')
    async def test_get_current_context_user(self, mock_get_github_client):
        """Test context authentication for user tokens."""
        # Mock GitHub OAuth client
        mock_github_client = MagicMock()
        mock_github_client.get_user_permissions.return_value = ["results:read"]
        mock_get_github_client.return_value = mock_github_client

        claims = TokenClaims(
            sub="github:123",
            exp=datetime.utcnow() + timedelta(hours=1),
            scope=TokenScope.USER,
            token_type=TokenType.ACCESS,
            username="testuser",
            email="test@example.com",
            role=UserRole.USER
        )

        context = await get_current_context(claims)
        assert isinstance(context, AuthenticatedUser)
        assert context.user_id == "github:123"

    @pytest.mark.asyncio
    async def test_get_current_context_automation(self):
        """Test context authentication for automation tokens."""
        claims = TokenClaims(
            sub="automation:ci:abcd1234",
            exp=datetime.utcnow() + timedelta(days=30),
            scope=TokenScope.AUTOMATION,
            token_type=TokenType.AUTOMATION,
            automation_name="ci-system",
            permissions=["results:write"]
        )

        context = await get_current_context(claims)
        assert isinstance(context, AuthenticatedAutomation)
        assert context.automation_id == "automation:ci:abcd1234"

    @pytest.mark.asyncio
    async def test_get_current_context_invalid_scope(self):
        """Test context authentication with invalid scope."""
        claims = TokenClaims(
            sub="invalid:123",
            exp=datetime.utcnow() + timedelta(hours=1),
            scope=TokenScope.ADMIN,  # Invalid scope
            token_type=TokenType.ACCESS
        )

        with pytest.raises(AuthenticationError) as exc_info:
            await get_current_context(claims)

        assert "Invalid token scope" in str(exc_info.value.detail)


class TestPermissionRequirements:
    """Test permission-based access control."""

    @pytest.mark.asyncio
    async def test_require_permissions_success(self):
        """Test successful permission check."""
        claims = TokenClaims(
            sub="github:123",
            exp=datetime.utcnow() + timedelta(hours=1),
            scope=TokenScope.USER,
            token_type=TokenType.ACCESS
        )
        context = AuthenticatedUser(
            user_id="github:123",
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
            permissions=["results:read", "results:write", "suites:read"],
            token_claims=claims
        )

        # Test the dependency function directly
        dependency_func = require_permissions("results:read", "suites:read")
        result = await dependency_func(context)
        assert result == context

    @pytest.mark.asyncio
    async def test_require_permissions_failure(self):
        """Test failed permission check."""
        claims = TokenClaims(
            sub="github:123",
            exp=datetime.utcnow() + timedelta(hours=1),
            scope=TokenScope.USER,
            token_type=TokenType.ACCESS
        )
        context = AuthenticatedUser(
            user_id="github:123",
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
            permissions=["results:read"],
            token_claims=claims
        )

        dependency_func = require_permissions("results:read", "results:delete")

        with pytest.raises(PermissionError) as exc_info:
            await dependency_func(context)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "results:delete" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_require_permissions_automation_context(self):
        """Test permission check with automation context."""
        claims = TokenClaims(
            sub="automation:ci:abcd1234",
            exp=datetime.utcnow() + timedelta(days=30),
            scope=TokenScope.AUTOMATION,
            token_type=TokenType.AUTOMATION
        )
        context = AuthenticatedAutomation(
            automation_id="automation:ci:abcd1234",
            automation_name="ci-system",
            permissions=["results:write", "artifacts:write"],
            token_claims=claims
        )

        dependency_func = require_permissions("results:write")
        result = await dependency_func(context)
        assert result == context


class TestRoleRequirements:
    """Test role-based access control."""

    @pytest.mark.asyncio
    async def test_require_role_success(self):
        """Test successful role check."""
        claims = TokenClaims(
            sub="github:123",
            exp=datetime.utcnow() + timedelta(hours=1),
            scope=TokenScope.USER,
            token_type=TokenType.ACCESS
        )
        user = AuthenticatedUser(
            user_id="github:123",
            username="testuser",
            email="test@example.com",
            role=UserRole.ADMIN,
            permissions=[],
            token_claims=claims
        )

        dependency_func = require_role(UserRole.ADMIN, UserRole.USER)
        result = await dependency_func(user)
        assert result == user

    @pytest.mark.asyncio
    async def test_require_role_failure(self):
        """Test failed role check."""
        claims = TokenClaims(
            sub="github:123",
            exp=datetime.utcnow() + timedelta(hours=1),
            scope=TokenScope.USER,
            token_type=TokenType.ACCESS
        )
        user = AuthenticatedUser(
            user_id="github:123",
            username="testuser",
            email="test@example.com",
            role=UserRole.READONLY,
            permissions=[],
            token_claims=claims
        )

        dependency_func = require_role(UserRole.ADMIN)

        with pytest.raises(PermissionError) as exc_info:
            await dependency_func(user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Insufficient role" in str(exc_info.value.detail)


class TestRequestMiddleware:
    """Test request middleware for authentication context."""

    @pytest.mark.asyncio
    @patch('src.lib.middleware.get_token_manager')
    @patch('src.lib.middleware.get_github_oauth_client')
    async def test_add_auth_context_user_token(self, mock_get_github_client, mock_get_token_manager):
        """Test adding user auth context to request."""
        # Create a real request state object
        class MockState:
            pass

        # Mock request
        mock_request = MagicMock()
        mock_request.headers = {"authorization": "Bearer user-token"}
        mock_request.state = MockState()

        # Mock token manager
        mock_token_manager = AsyncMock()
        mock_jwt_auth = MagicMock()
        mock_token_manager.jwt_auth = mock_jwt_auth
        mock_get_token_manager.return_value = mock_token_manager

        # Mock GitHub client
        mock_github_client = MagicMock()
        mock_github_client.get_user_permissions.return_value = ["results:read"]
        mock_get_github_client.return_value = mock_github_client

        # Mock validation result
        claims = TokenClaims(
            sub="github:123",
            exp=datetime.utcnow() + timedelta(hours=1),
            scope=TokenScope.USER,
            token_type=TokenType.ACCESS,
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
            github_id=123
        )
        mock_jwt_auth.validate_token.return_value = TokenValidationResult(
            valid=True,
            claims=claims
        )

        await add_auth_context_to_request(mock_request)

        # Verify user context was added
        assert hasattr(mock_request.state, 'user')
        user = mock_request.state.user
        assert user.user_id == "github:123"
        assert user.username == "testuser"

    @pytest.mark.asyncio
    @patch('src.lib.middleware.get_token_manager')
    async def test_add_auth_context_automation_token(self, mock_get_token_manager):
        """Test adding automation auth context to request."""
        # Mock request
        mock_request = MagicMock()
        mock_request.headers = {"authorization": "Bearer automation-token"}
        mock_request.state = MagicMock()

        # Mock token manager
        mock_token_manager = AsyncMock()
        mock_jwt_auth = MagicMock()
        mock_token_manager.jwt_auth = mock_jwt_auth
        mock_get_token_manager.return_value = mock_token_manager

        # Mock validation result
        claims = TokenClaims(
            sub="automation:ci:abcd1234",
            exp=datetime.utcnow() + timedelta(days=30),
            scope=TokenScope.AUTOMATION,
            token_type=TokenType.AUTOMATION,
            automation_name="ci-system",
            permissions=["results:write"]
        )
        mock_jwt_auth.validate_token.return_value = TokenValidationResult(
            valid=True,
            claims=claims
        )

        await add_auth_context_to_request(mock_request)

        # Verify automation context was added
        assert hasattr(mock_request.state, 'automation')
        automation = mock_request.state.automation
        assert automation.automation_id == "automation:ci:abcd1234"
        assert automation.automation_name == "ci-system"

    @pytest.mark.asyncio
    async def test_add_auth_context_no_header(self):
        """Test middleware with no authorization header."""
        class MockState:
            pass

        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.state = MockState()

        # Should not raise exception
        await add_auth_context_to_request(mock_request)

        # Should not add any auth context
        assert not hasattr(mock_request.state, 'user')
        assert not hasattr(mock_request.state, 'automation')

    @pytest.mark.asyncio
    @patch('src.lib.middleware.get_token_manager')
    async def test_add_auth_context_invalid_token(self, mock_get_token_manager):
        """Test middleware with invalid token."""
        class MockState:
            pass

        mock_request = MagicMock()
        mock_request.headers = {"authorization": "Bearer invalid-token"}
        mock_request.state = MockState()

        # Mock token manager to return invalid result
        mock_token_manager = AsyncMock()
        mock_jwt_auth = MagicMock()
        mock_token_manager.jwt_auth = mock_jwt_auth
        mock_get_token_manager.return_value = mock_token_manager

        mock_jwt_auth.validate_token.return_value = TokenValidationResult(
            valid=False,
            error="Invalid signature"
        )

        # Should not raise exception
        await add_auth_context_to_request(mock_request)

        # Should not add any auth context
        assert not hasattr(mock_request.state, 'user')
        assert not hasattr(mock_request.state, 'automation')