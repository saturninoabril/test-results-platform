"""
JWT authentication library with token generation, validation, and refresh mechanisms.
Supports different token scopes (user, automation) with proper claims and expiration handling.
"""

import secrets
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4

import jwt
import structlog
from pydantic import BaseModel, Field, field_validator

from .config import get_settings

logger = structlog.get_logger()


class TokenScope(str, Enum):
    """Token scope enumeration."""

    USER = "user"
    AUTOMATION = "automation"
    ADMIN = "admin"
    READONLY = "readonly"


class UserRole(str, Enum):
    """User role enumeration."""

    ADMIN = "admin"
    USER = "user"
    READONLY = "readonly"


class TokenType(str, Enum):
    """Token type enumeration."""

    ACCESS = "access"
    REFRESH = "refresh"
    AUTOMATION = "automation"


class TokenClaims(BaseModel):
    """JWT token claims structure."""

    sub: str = Field(..., description="Subject (user ID)")
    iss: str = Field(default="test-results-api", description="Issuer")
    aud: str = Field(default="test-results-api", description="Audience")
    exp: datetime = Field(..., description="Expiration time")
    iat: datetime = Field(default_factory=datetime.utcnow, description="Issued at")
    jti: str = Field(default_factory=lambda: str(uuid4()), description="JWT ID")
    scope: TokenScope = Field(..., description="Token scope")
    token_type: TokenType = Field(..., description="Token type")

    # User-specific claims
    username: str | None = Field(None, description="Username")
    email: str | None = Field(None, description="User email")
    role: UserRole | None = Field(None, description="User role")
    github_id: int | None = Field(None, description="GitHub user ID")

    # Automation-specific claims
    automation_name: str | None = Field(None, description="Automation system name")
    permissions: list[str] = Field(default_factory=list, description="Token permissions")

    @field_validator("exp", "iat")
    @classmethod
    def validate_datetime_as_timestamp(cls, v: datetime) -> datetime:
        """Ensure datetime values are timezone-naive UTC."""
        if v.tzinfo is not None:
            v = v.replace(tzinfo=None)
        return v

    def model_dump_for_jwt(self) -> dict[str, Any]:
        """Dump model for JWT encoding with timestamps as integers."""
        data = self.model_dump(mode="json", exclude_none=True)

        # Convert datetime fields to timestamps
        for field in ["exp", "iat"]:
            if field in data and isinstance(data[field], str):
                # If it's already serialized as ISO string, parse it back
                dt = datetime.fromisoformat(data[field])
                data[field] = int(dt.timestamp())
            elif field in data and isinstance(data[field], datetime):
                data[field] = int(data[field].timestamp())

        return data


class TokenValidationResult(BaseModel):
    """Result of token validation."""

    valid: bool
    claims: TokenClaims | None = None
    error: str | None = None
    expired: bool = False
    scope: TokenScope | None = None


class JWTAuthenticator:
    """JWT token generation and validation."""

    def __init__(self) -> None:
        """Initialize JWT authenticator with settings."""
        self.settings = get_settings()
        self._algorithm = self.settings.auth.jwt_algorithm
        self._secret_key = self.settings.auth.jwt_secret_key

        # Token expiration settings
        self._access_token_expire_hours = self.settings.auth.jwt_expiration_hours
        self._refresh_token_expire_days = 7  # Refresh tokens last 7 days
        self._automation_token_expire_days = self.settings.auth.automation_token_expiry_days

    def generate_access_token(
        self,
        user_id: str,
        username: str,
        email: str,
        role: UserRole,
        github_id: int | None = None,
        custom_expiration: timedelta | None = None,
    ) -> str:
        """Generate access token for user authentication."""
        expiration = custom_expiration or timedelta(hours=self._access_token_expire_hours)
        exp_time = datetime.utcnow() + expiration

        claims = TokenClaims(
            sub=user_id,
            exp=exp_time,
            scope=TokenScope.USER,
            token_type=TokenType.ACCESS,
            username=username,
            email=email,
            role=role,
            github_id=github_id,
            automation_name=None,
        )

        token = jwt.encode(claims.model_dump_for_jwt(), self._secret_key, algorithm=self._algorithm)

        logger.info(
            "Access token generated",
            user_id=user_id,
            username=username,
            role=role.value,
            expires_at=exp_time.isoformat(),
        )

        return token

    def generate_refresh_token(self, user_id: str, username: str) -> str:
        """Generate refresh token for token renewal."""
        exp_time = datetime.utcnow() + timedelta(days=self._refresh_token_expire_days)

        claims = TokenClaims(
            sub=user_id,
            exp=exp_time,
            scope=TokenScope.USER,
            token_type=TokenType.REFRESH,
            username=username,
            email=None,
            role=None,
            github_id=None,
            automation_name=None,
        )

        token = jwt.encode(claims.model_dump_for_jwt(), self._secret_key, algorithm=self._algorithm)

        logger.info(
            "Refresh token generated",
            user_id=user_id,
            username=username,
            expires_at=exp_time.isoformat(),
        )

        return token

    def generate_automation_token(
        self,
        automation_name: str,
        permissions: list[str],
        custom_expiration: timedelta | None = None,
    ) -> str:
        """Generate automation token for CI/CD systems."""
        expiration = custom_expiration or timedelta(days=self._automation_token_expire_days)
        exp_time = datetime.utcnow() + expiration
        automation_id = f"automation:{automation_name}:{uuid4().hex[:8]}"

        claims = TokenClaims(
            sub=automation_id,
            exp=exp_time,
            scope=TokenScope.AUTOMATION,
            token_type=TokenType.AUTOMATION,
            automation_name=automation_name,
            permissions=permissions,
            username=None,
            email=None,
            role=None,
            github_id=None,
        )

        token = jwt.encode(claims.model_dump_for_jwt(), self._secret_key, algorithm=self._algorithm)

        logger.info(
            "Automation token generated",
            automation_name=automation_name,
            automation_id=automation_id,
            permissions=permissions,
            expires_at=exp_time.isoformat(),
        )

        return token

    def validate_token(self, token: str) -> TokenValidationResult:
        """Validate JWT token and return claims."""
        try:
            # Decode token
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
                options={"verify_exp": True, "verify_aud": False},
            )

            # Parse claims
            claims = TokenClaims(**payload)

            logger.debug(
                "Token validated successfully",
                subject=claims.sub,
                scope=claims.scope.value,
                token_type=claims.token_type.value,
            )

            return TokenValidationResult(
                valid=True,
                claims=claims,
                scope=claims.scope,
            )

        except jwt.ExpiredSignatureError:
            logger.warning("Token validation failed: expired")
            return TokenValidationResult(
                valid=False,
                error="Token has expired",
                expired=True,
            )

        except jwt.InvalidTokenError as e:
            logger.warning("Token validation failed", error=str(e))
            return TokenValidationResult(
                valid=False,
                error=f"Invalid token: {str(e)}",
            )

        except Exception as e:
            logger.error("Token validation error", error=str(e))
            return TokenValidationResult(
                valid=False,
                error=f"Token validation error: {str(e)}",
            )

    def refresh_access_token(self, refresh_token: str) -> str | None:
        """Generate new access token from refresh token."""
        validation_result = self.validate_token(refresh_token)

        if not validation_result.valid:
            logger.warning("Refresh token validation failed", error=validation_result.error)
            return None

        claims = validation_result.claims
        if not claims or claims.token_type != TokenType.REFRESH:
            logger.warning(
                "Invalid token type for refresh", token_type=claims.token_type if claims else None
            )
            return None

        # Extract user info from refresh token
        user_id = claims.sub
        username = claims.username

        if not username:
            logger.warning("Missing username in refresh token", user_id=user_id)
            return None

        # Note: In a real implementation, you'd fetch the user's current role and email from the database
        # For now, we'll use defaults - this should be enhanced when user management is implemented
        new_access_token = self.generate_access_token(
            user_id=user_id,
            username=username,
            email=f"{username}@example.com",  # Placeholder
            role=UserRole.USER,  # Default role
        )

        logger.info("Access token refreshed", user_id=user_id, username=username)
        return new_access_token

    def decode_token_claims(self, token: str) -> TokenClaims | None:
        """Decode token without validation (for inspection)."""
        try:
            payload = jwt.decode(token, options={"verify_signature": False, "verify_exp": False})
            return TokenClaims(**payload)
        except Exception as e:
            logger.error("Failed to decode token claims", error=str(e))
            return None

    def is_token_expired(self, token: str) -> bool:
        """Check if token is expired without full validation."""
        claims = self.decode_token_claims(token)
        if not claims:
            return True

        return datetime.utcnow() > claims.exp

    def get_token_expiry(self, token: str) -> datetime | None:
        """Get token expiration time."""
        claims = self.decode_token_claims(token)
        return claims.exp if claims else None

    def revoke_token(self, token: str) -> bool:
        """
        Revoke a token (placeholder for token blacklisting).

        In a production implementation, this would add the token to a blacklist
        stored in Redis or database until its expiration.
        """
        claims = self.decode_token_claims(token)
        if not claims:
            return False

        # Token revocation - store blacklisted tokens (requires Redis/database implementation)
        # For now, tokens remain valid until expiration
        # Future: Store jti in Redis/database with expiration time
        logger.info(
            "Token revoked (logged only - implement blacklist storage)",
            jti=claims.jti,
            subject=claims.sub,
            expires_at=claims.exp.isoformat(),
        )
        return True  # Always returns True for now - implement proper blacklist check


class TokenManager:
    """High-level token management with caching and utilities."""

    def __init__(self) -> None:
        """Initialize token manager."""
        self.jwt_auth = JWTAuthenticator()
        # Note: Redis caching can be added for blacklisted tokens when implementing token revocation
        # self.redis_client = redis.AsyncRedis() if settings.performance.cache_redis_url else None

    async def create_user_tokens(
        self,
        user_id: str,
        username: str,
        email: str,
        role: UserRole,
        github_id: int | None = None,
    ) -> dict[str, Any]:
        """Create access and refresh token pair for user."""
        access_token = self.jwt_auth.generate_access_token(
            user_id=user_id,
            username=username,
            email=email,
            role=role,
            github_id=github_id,
        )

        refresh_token = self.jwt_auth.generate_refresh_token(
            user_id=user_id,
            username=username,
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": self.jwt_auth._access_token_expire_hours * 3600,  # seconds
        }

    async def create_automation_token(
        self,
        automation_name: str,
        permissions: list[str],
        expiration_days: int | None = None,
    ) -> dict[str, Any]:
        """Create automation token for CI/CD systems."""
        custom_expiration = None
        if expiration_days:
            custom_expiration = timedelta(days=expiration_days)

        token = self.jwt_auth.generate_automation_token(
            automation_name=automation_name,
            permissions=permissions,
            custom_expiration=custom_expiration,
        )

        expires_in_days = expiration_days or self.jwt_auth._automation_token_expire_days

        return {
            "automation_token": token,
            "token_type": "Bearer",
            "expires_in_days": expires_in_days,
            "permissions": permissions,
        }

    async def validate_and_refresh_token(self, token: str) -> dict[str, Any] | None:
        """Validate token and auto-refresh if needed."""
        validation_result = self.jwt_auth.validate_token(token)

        if validation_result.valid:
            return {
                "valid": True,
                "claims": validation_result.claims.model_dump() if validation_result.claims else {},
                "needs_refresh": False,
            }

        # If expired and it's a refresh token, don't try to refresh
        if validation_result.expired:
            claims = self.jwt_auth.decode_token_claims(token)
            if claims and claims.token_type == TokenType.REFRESH:
                return {
                    "valid": False,
                    "error": "Refresh token expired",
                    "needs_refresh": False,
                }

            # For access tokens, indicate refresh is needed
            return {
                "valid": False,
                "error": "Access token expired",
                "needs_refresh": True,
            }

        return {
            "valid": False,
            "error": validation_result.error,
            "needs_refresh": False,
        }

    async def refresh_user_token(self, refresh_token: str) -> dict[str, Any] | None:
        """Refresh user access token."""
        new_access_token = self.jwt_auth.refresh_access_token(refresh_token)

        if not new_access_token:
            return None

        return {
            "access_token": new_access_token,
            "token_type": "Bearer",
            "expires_in": self.jwt_auth._access_token_expire_hours * 3600,
        }


# Global token manager instance
_token_manager: TokenManager | None = None


async def get_token_manager() -> TokenManager:
    """Get or create token manager instance."""
    global _token_manager
    if _token_manager is None:
        _token_manager = TokenManager()
    return _token_manager


def generate_secure_secret_key() -> str:
    """Generate a cryptographically secure secret key for JWT signing."""
    return secrets.token_urlsafe(32)
