"""
Unit tests for authentication library.
Tests JWT token generation, validation, refresh mechanisms, and token scopes.
"""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from src.lib.auth import (
    JWTAuthenticator,
    TokenClaims,
    TokenManager,
    TokenScope,
    TokenType,
    UserRole,
    generate_secure_secret_key,
    get_token_manager,
)


class TestTokenClaims:
    """Test TokenClaims model."""

    def test_token_claims_creation(self):
        """Test basic token claims creation."""
        exp_time = datetime.utcnow() + timedelta(hours=1)
        claims = TokenClaims(
            sub="user123",
            exp=exp_time,
            scope=TokenScope.USER,
            token_type=TokenType.ACCESS,
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
        )

        assert claims.sub == "user123"
        assert claims.scope == TokenScope.USER
        assert claims.token_type == TokenType.ACCESS
        assert claims.username == "testuser"
        assert claims.email == "test@example.com"
        assert claims.role == UserRole.USER
        assert claims.iss == "test-results-api"
        assert claims.aud == "test-results-api"

    def test_token_claims_datetime_validation(self):
        """Test datetime field validation."""
        # Should handle timezone-aware datetime by converting to naive

        tz_aware_time = datetime.now(UTC)

        claims = TokenClaims(
            sub="user123",
            exp=tz_aware_time,
            scope=TokenScope.USER,
            token_type=TokenType.ACCESS,
        )

        assert claims.exp.tzinfo is None  # Should be timezone-naive

    def test_automation_token_claims(self):
        """Test automation-specific claims."""
        exp_time = datetime.utcnow() + timedelta(days=30)
        claims = TokenClaims(
            sub="automation:ci-system",
            exp=exp_time,
            scope=TokenScope.AUTOMATION,
            token_type=TokenType.AUTOMATION,
            automation_name="ci-system",
            permissions=["results:write", "artifacts:upload"],
        )

        assert claims.scope == TokenScope.AUTOMATION
        assert claims.automation_name == "ci-system"
        assert claims.permissions == ["results:write", "artifacts:upload"]


class TestJWTAuthenticator:
    """Test JWT authentication functionality."""

    @pytest.fixture
    def authenticator(self):
        """Create JWT authenticator instance."""
        return JWTAuthenticator()

    def test_generate_access_token(self, authenticator):
        """Test access token generation."""
        token = authenticator.generate_access_token(
            user_id="user123",
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
            github_id=12345,
        )

        assert isinstance(token, str)
        assert len(token) > 100  # JWT tokens are quite long

        # Decode without verification to check claims
        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["sub"] == "user123"
        assert payload["username"] == "testuser"
        assert payload["email"] == "test@example.com"
        assert payload["role"] == "user"
        assert payload["github_id"] == 12345
        assert payload["scope"] == "user"
        assert payload["token_type"] == "access"

    def test_generate_refresh_token(self, authenticator):
        """Test refresh token generation."""
        token = authenticator.generate_refresh_token(
            user_id="user123",
            username="testuser",
        )

        assert isinstance(token, str)

        # Decode to check claims
        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["sub"] == "user123"
        assert payload["username"] == "testuser"
        assert payload["scope"] == "user"
        assert payload["token_type"] == "refresh"

    def test_generate_automation_token(self, authenticator):
        """Test automation token generation."""
        permissions = ["results:write", "artifacts:upload", "suites:delete"]
        token = authenticator.generate_automation_token(
            automation_name="github-actions",
            permissions=permissions,
        )

        assert isinstance(token, str)

        # Decode to check claims
        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["automation_name"] == "github-actions"
        assert payload["permissions"] == permissions
        assert payload["scope"] == "automation"
        assert payload["token_type"] == "automation"
        assert payload["sub"].startswith("automation:github-actions:")

    def test_generate_automation_token_custom_expiration(self, authenticator):
        """Test automation token with custom expiration."""
        custom_expiration = timedelta(days=7)
        token = authenticator.generate_automation_token(
            automation_name="ci-system",
            permissions=["results:read"],
            custom_expiration=custom_expiration,
        )

        payload = jwt.decode(token, options={"verify_signature": False})
        exp_time = datetime.fromtimestamp(payload["exp"])
        iat_time = datetime.fromtimestamp(payload["iat"])

        # Should be approximately 7 days difference
        time_diff = exp_time - iat_time
        assert abs(time_diff.total_seconds() - custom_expiration.total_seconds()) < 60

    def test_validate_token_success(self, authenticator):
        """Test successful token validation."""
        # Generate a valid token
        token = authenticator.generate_access_token(
            user_id="user123",
            username="testuser",
            email="test@example.com",
            role=UserRole.ADMIN,
        )

        # Validate the token
        result = authenticator.validate_token(token)

        assert result.valid is True
        assert result.claims is not None
        assert result.claims.sub == "user123"
        assert result.claims.username == "testuser"
        assert result.claims.role == UserRole.ADMIN
        assert result.scope == TokenScope.USER
        assert result.error is None

    def test_validate_token_expired(self, authenticator):
        """Test validation of expired token."""
        # Generate token with past expiration
        past_expiration = timedelta(hours=-1)
        token = authenticator.generate_access_token(
            user_id="user123",
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
            custom_expiration=past_expiration,
        )

        # Validate the expired token
        result = authenticator.validate_token(token)

        assert result.valid is False
        assert result.expired is True
        assert "expired" in result.error.lower()
        assert result.claims is None

    def test_validate_token_invalid_signature(self, authenticator):
        """Test validation of token with invalid signature."""
        # Generate token with different secret
        fake_token = jwt.encode(
            {"sub": "user123", "exp": datetime.utcnow() + timedelta(hours=1)},
            "wrong-secret",
            algorithm="HS256",
        )

        result = authenticator.validate_token(fake_token)

        assert result.valid is False
        assert result.expired is False
        assert "Invalid token" in result.error
        assert result.claims is None

    def test_validate_token_malformed(self, authenticator):
        """Test validation of malformed token."""
        malformed_token = "not.a.valid.jwt.token"

        result = authenticator.validate_token(malformed_token)

        assert result.valid is False
        assert "Invalid token" in result.error

    def test_refresh_access_token_success(self, authenticator):
        """Test successful access token refresh."""
        # Generate refresh token
        refresh_token = authenticator.generate_refresh_token(
            user_id="user123",
            username="testuser",
        )

        # Refresh the access token
        new_access_token = authenticator.refresh_access_token(refresh_token)

        assert new_access_token is not None
        assert isinstance(new_access_token, str)

        # Validate the new access token
        result = authenticator.validate_token(new_access_token)
        assert result.valid is True
        assert result.claims.sub == "user123"
        assert result.claims.username == "testuser"
        assert result.claims.token_type == TokenType.ACCESS

    def test_refresh_access_token_invalid_token(self, authenticator):
        """Test refresh with invalid token."""
        invalid_token = "invalid.token.here"

        new_access_token = authenticator.refresh_access_token(invalid_token)
        assert new_access_token is None

    def test_refresh_access_token_wrong_type(self, authenticator):
        """Test refresh with non-refresh token."""
        # Use access token instead of refresh token
        access_token = authenticator.generate_access_token(
            user_id="user123",
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
        )

        new_access_token = authenticator.refresh_access_token(access_token)
        assert new_access_token is None

    def test_decode_token_claims(self, authenticator):
        """Test token claims decoding without validation."""
        token = authenticator.generate_access_token(
            user_id="user123",
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
        )

        claims = authenticator.decode_token_claims(token)
        assert claims is not None
        assert claims.sub == "user123"
        assert claims.username == "testuser"

    def test_decode_token_claims_invalid(self, authenticator):
        """Test decoding invalid token claims."""
        invalid_token = "not.a.token"

        claims = authenticator.decode_token_claims(invalid_token)
        assert claims is None

    def test_is_token_expired(self, authenticator):
        """Test token expiration check."""
        # Valid token
        valid_token = authenticator.generate_access_token(
            user_id="user123",
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
        )
        assert not authenticator.is_token_expired(valid_token)

        # Expired token
        expired_token = authenticator.generate_access_token(
            user_id="user123",
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
            custom_expiration=timedelta(hours=-1),
        )
        assert authenticator.is_token_expired(expired_token)

    def test_get_token_expiry(self, authenticator):
        """Test getting token expiration time."""
        token = authenticator.generate_access_token(
            user_id="user123",
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
        )

        expiry = authenticator.get_token_expiry(token)
        assert expiry is not None
        assert isinstance(expiry, datetime)
        assert expiry > datetime.utcnow()

    def test_revoke_token(self, authenticator):
        """Test token revocation (placeholder implementation)."""
        token = authenticator.generate_access_token(
            user_id="user123",
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
        )

        # Should return True (placeholder implementation)
        result = authenticator.revoke_token(token)
        assert result is True

        # Invalid token should return False
        result = authenticator.revoke_token("invalid.token")
        assert result is False


class TestTokenManager:
    """Test TokenManager high-level functionality."""

    @pytest.fixture
    def token_manager(self):
        """Create token manager instance."""
        return TokenManager()

    @pytest.mark.asyncio
    async def test_create_user_tokens(self, token_manager):
        """Test creating user token pair."""
        tokens = await token_manager.create_user_tokens(
            user_id="user123",
            username="testuser",
            email="test@example.com",
            role=UserRole.ADMIN,
            github_id=12345,
        )

        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "Bearer"
        assert isinstance(tokens["expires_in"], int)
        assert tokens["expires_in"] > 0

        # Validate both tokens
        access_result = token_manager.jwt_auth.validate_token(tokens["access_token"])
        refresh_result = token_manager.jwt_auth.validate_token(tokens["refresh_token"])

        assert access_result.valid
        assert refresh_result.valid
        assert access_result.claims.token_type == TokenType.ACCESS
        assert refresh_result.claims.token_type == TokenType.REFRESH

    @pytest.mark.asyncio
    async def test_create_automation_token(self, token_manager):
        """Test creating automation token."""
        permissions = ["results:write", "artifacts:upload"]
        token_info = await token_manager.create_automation_token(
            automation_name="ci-system",
            permissions=permissions,
            expiration_days=14,
        )

        assert "automation_token" in token_info
        assert token_info["token_type"] == "Bearer"
        assert token_info["expires_in_days"] == 14
        assert token_info["permissions"] == permissions

        # Validate token
        result = token_manager.jwt_auth.validate_token(token_info["automation_token"])
        assert result.valid
        assert result.claims.automation_name == "ci-system"
        assert result.claims.permissions == permissions

    @pytest.mark.asyncio
    async def test_validate_and_refresh_token_valid(self, token_manager):
        """Test validation of valid token."""
        tokens = await token_manager.create_user_tokens(
            user_id="user123",
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
        )

        result = await token_manager.validate_and_refresh_token(tokens["access_token"])

        assert result["valid"] is True
        assert result["needs_refresh"] is False
        assert "claims" in result

    @pytest.mark.asyncio
    async def test_validate_and_refresh_token_expired_access(self, token_manager):
        """Test validation of expired access token."""
        # Generate expired access token
        expired_token = token_manager.jwt_auth.generate_access_token(
            user_id="user123",
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
            custom_expiration=timedelta(hours=-1),
        )

        result = await token_manager.validate_and_refresh_token(expired_token)

        assert result["valid"] is False
        assert result["needs_refresh"] is True
        assert "expired" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_validate_and_refresh_token_expired_refresh(self, token_manager):
        """Test validation of expired refresh token."""
        # Generate expired refresh token
        expired_refresh = token_manager.jwt_auth.generate_refresh_token(
            user_id="user123",
            username="testuser",
        )

        # Manually set expiration in the past by re-encoding
        import jwt

        payload = jwt.decode(expired_refresh, options={"verify_signature": False})
        payload["exp"] = (datetime.utcnow() - timedelta(hours=1)).timestamp()
        expired_refresh = jwt.encode(payload, token_manager.jwt_auth._secret_key, algorithm="HS256")

        result = await token_manager.validate_and_refresh_token(expired_refresh)

        assert result["valid"] is False
        assert result["needs_refresh"] is False  # Refresh tokens can't be refreshed

    @pytest.mark.asyncio
    async def test_refresh_user_token_success(self, token_manager):
        """Test successful user token refresh."""
        # Create initial tokens
        tokens = await token_manager.create_user_tokens(
            user_id="user123",
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
        )

        # Refresh access token
        refreshed = await token_manager.refresh_user_token(tokens["refresh_token"])

        assert refreshed is not None
        assert "access_token" in refreshed
        assert refreshed["token_type"] == "Bearer"

        # New token should be different from original
        assert refreshed["access_token"] != tokens["access_token"]

        # New token should be valid
        result = token_manager.jwt_auth.validate_token(refreshed["access_token"])
        assert result.valid

    @pytest.mark.asyncio
    async def test_refresh_user_token_invalid(self, token_manager):
        """Test refresh with invalid token."""
        refreshed = await token_manager.refresh_user_token("invalid.token")
        assert refreshed is None

    @pytest.mark.asyncio
    async def test_get_token_manager_singleton(self):
        """Test token manager singleton pattern."""
        manager1 = await get_token_manager()
        manager2 = await get_token_manager()

        assert manager1 is manager2  # Should be the same instance


class TestUtilityFunctions:
    """Test utility functions."""

    def test_generate_secure_secret_key(self):
        """Test secure secret key generation."""
        key1 = generate_secure_secret_key()
        key2 = generate_secure_secret_key()

        assert isinstance(key1, str)
        assert isinstance(key2, str)
        assert len(key1) >= 32  # Should be reasonably long
        assert key1 != key2  # Should be different each time


class TestTokenScopes:
    """Test token scope functionality."""

    @pytest.fixture
    def authenticator(self):
        """Create JWT authenticator instance."""
        return JWTAuthenticator()

    def test_user_token_scope(self, authenticator):
        """Test user token has correct scope."""
        token = authenticator.generate_access_token(
            user_id="user123",
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
        )

        result = authenticator.validate_token(token)
        assert result.scope == TokenScope.USER

    def test_automation_token_scope(self, authenticator):
        """Test automation token has correct scope."""
        token = authenticator.generate_automation_token(
            automation_name="ci",
            permissions=["results:write"],
        )

        result = authenticator.validate_token(token)
        assert result.scope == TokenScope.AUTOMATION

    def test_different_user_roles(self, authenticator):
        """Test tokens with different user roles."""
        roles = [UserRole.ADMIN, UserRole.USER, UserRole.READONLY]

        for role in roles:
            token = authenticator.generate_access_token(
                user_id=f"user-{role.value}",
                username=f"test-{role.value}",
                email=f"test-{role.value}@example.com",
                role=role,
            )

            result = authenticator.validate_token(token)
            assert result.valid
            assert result.claims.role == role
