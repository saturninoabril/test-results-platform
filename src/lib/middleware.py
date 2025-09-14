"""
FastAPI authentication middleware and dependencies for JWT token validation.
Provides bearer token authentication, user context, and permission-based access control.
"""

from typing import Annotated, Any, List, Optional, Union
from uuid import UUID

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from .auth import TokenClaims, TokenScope, TokenValidationResult, UserRole, get_token_manager
from .github_oauth import get_github_oauth_client

logger = structlog.get_logger()

# HTTP Bearer token security scheme
bearer_scheme = HTTPBearer(auto_error=False)


class AuthenticatedUser(BaseModel):
    """Authenticated user context."""
    user_id: str
    username: str
    email: str
    role: UserRole
    github_id: Optional[int] = None
    permissions: List[str]
    token_claims: TokenClaims


class AuthenticatedAutomation(BaseModel):
    """Authenticated automation context."""
    automation_id: str
    automation_name: str
    permissions: List[str]
    token_claims: TokenClaims


AuthenticatedContext = Union[AuthenticatedUser, AuthenticatedAutomation]


class AuthenticationError(HTTPException):
    """Authentication error with proper HTTP status codes."""

    def __init__(self, detail: str, status_code: int = status.HTTP_401_UNAUTHORIZED):
        super().__init__(status_code=status_code, detail=detail)


class PermissionError(HTTPException):
    """Permission error for insufficient access rights."""

    def __init__(self, detail: str, required_permissions: List[str]):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": detail,
                "required_permissions": required_permissions
            }
        )


async def get_bearer_token(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)]
) -> str:
    """Extract and validate bearer token from Authorization header."""
    if not credentials:
        logger.warning("Missing authorization header")
        raise AuthenticationError("Missing authorization header")

    if credentials.scheme.lower() != "bearer":
        logger.warning("Invalid authorization scheme", scheme=credentials.scheme)
        raise AuthenticationError("Invalid authorization scheme. Expected 'Bearer'")

    if not credentials.credentials:
        logger.warning("Missing token in authorization header")
        raise AuthenticationError("Missing token in authorization header")

    return credentials.credentials


async def validate_token(token: Annotated[str, Depends(get_bearer_token)]) -> TokenClaims:
    """Validate JWT token and return claims."""
    token_manager = await get_token_manager()

    validation_result = token_manager.jwt_auth.validate_token(token)

    if not validation_result.valid:
        if validation_result.expired:
            logger.warning("Token validation failed: expired")
            raise AuthenticationError("Token has expired")

        logger.warning("Token validation failed", error=validation_result.error)
        raise AuthenticationError(f"Invalid token: {validation_result.error}")

    if not validation_result.claims:
        logger.warning("Token validation succeeded but no claims returned")
        raise AuthenticationError("Invalid token: missing claims")

    return validation_result.claims


async def get_current_user(
    claims: Annotated[TokenClaims, Depends(validate_token)]
) -> AuthenticatedUser:
    """Get current authenticated user from token claims."""
    if claims.scope != TokenScope.USER:
        logger.warning("Invalid token scope for user authentication", scope=claims.scope.value)
        raise AuthenticationError("Invalid token scope for user authentication")

    if not claims.username or not claims.email or not claims.role:
        logger.warning("Missing required user claims", username=claims.username, email=claims.email, role=claims.role)
        raise AuthenticationError("Invalid token: missing required user information")

    # Get user permissions from GitHub OAuth client
    github_client = await get_github_oauth_client()
    permissions = github_client.get_user_permissions(claims.role)

    user = AuthenticatedUser(
        user_id=claims.sub,
        username=claims.username,
        email=claims.email,
        role=claims.role,
        github_id=claims.github_id,
        permissions=permissions,
        token_claims=claims
    )

    logger.info(
        "User authenticated",
        user_id=user.user_id,
        username=user.username,
        role=user.role.value,
        permissions_count=len(user.permissions)
    )

    return user


async def get_current_automation(
    claims: Annotated[TokenClaims, Depends(validate_token)]
) -> AuthenticatedAutomation:
    """Get current authenticated automation from token claims."""
    if claims.scope != TokenScope.AUTOMATION:
        logger.warning("Invalid token scope for automation authentication", scope=claims.scope.value)
        raise AuthenticationError("Invalid token scope for automation authentication")

    if not claims.automation_name:
        logger.warning("Missing automation name in token claims")
        raise AuthenticationError("Invalid token: missing automation information")

    automation = AuthenticatedAutomation(
        automation_id=claims.sub,
        automation_name=claims.automation_name,
        permissions=claims.permissions,
        token_claims=claims
    )

    logger.info(
        "Automation authenticated",
        automation_id=automation.automation_id,
        automation_name=automation.automation_name,
        permissions_count=len(automation.permissions)
    )

    return automation


async def get_current_context(
    claims: Annotated[TokenClaims, Depends(validate_token)]
) -> AuthenticatedContext:
    """Get current authenticated context (user or automation)."""
    if claims.scope == TokenScope.USER:
        return await get_current_user(claims)
    elif claims.scope == TokenScope.AUTOMATION:
        return await get_current_automation(claims)
    else:
        logger.warning("Invalid token scope", scope=claims.scope.value)
        raise AuthenticationError(f"Invalid token scope: {claims.scope.value}")


def require_permissions(*required_permissions: str) -> Any:
    """Dependency factory for permission-based access control."""

    async def check_permissions(
        context: Annotated[AuthenticatedContext, Depends(get_current_context)]
    ) -> AuthenticatedContext:
        """Check if authenticated context has required permissions."""
        missing_permissions = []

        for permission in required_permissions:
            if permission not in context.permissions:
                missing_permissions.append(permission)

        if missing_permissions:
            logger.warning(
                "Permission denied",
                user_id=getattr(context, 'user_id', None) or getattr(context, 'automation_id', None),
                required_permissions=list(required_permissions),
                missing_permissions=missing_permissions,
                user_permissions=context.permissions
            )
            raise PermissionError(
                detail=f"Insufficient permissions. Missing: {', '.join(missing_permissions)}",
                required_permissions=list(required_permissions)
            )

        return context

    return check_permissions


def require_role(*required_roles: UserRole) -> Any:
    """Dependency factory for role-based access control (user tokens only)."""

    async def check_role(
        user: Annotated[AuthenticatedUser, Depends(get_current_user)]
    ) -> AuthenticatedUser:
        """Check if authenticated user has required role."""
        if user.role not in required_roles:
            logger.warning(
                "Role access denied",
                user_id=user.user_id,
                username=user.username,
                user_role=user.role.value,
                required_roles=[role.value for role in required_roles]
            )
            raise PermissionError(
                detail=f"Insufficient role. Required: {', '.join(role.value for role in required_roles)}",
                required_permissions=[]
            )

        return user

    return check_role


# Convenience dependencies for common access patterns
RequireAdmin = Depends(require_role(UserRole.ADMIN))
RequireUser = Depends(require_role(UserRole.USER, UserRole.ADMIN))
RequireReadOnly = Depends(require_role(UserRole.READONLY, UserRole.USER, UserRole.ADMIN))

# Permission-based dependencies
RequireResultsRead = Depends(require_permissions("results:read"))
RequireResultsWrite = Depends(require_permissions("results:write"))
RequireResultsDelete = Depends(require_permissions("results:delete"))

RequireSuitesRead = Depends(require_permissions("suites:read"))
RequireSuitesWrite = Depends(require_permissions("suites:write"))
RequireSuitesDelete = Depends(require_permissions("suites:delete"))

RequireArtifactsRead = Depends(require_permissions("artifacts:read"))
RequireArtifactsWrite = Depends(require_permissions("artifacts:write"))
RequireArtifactsDelete = Depends(require_permissions("artifacts:delete"))

RequireFrameworksRead = Depends(require_permissions("frameworks:read"))
RequireFrameworksWrite = Depends(require_permissions("frameworks:write"))
RequireFrameworksDelete = Depends(require_permissions("frameworks:delete"))

RequireEnvironmentsRead = Depends(require_permissions("environments:read"))
RequireEnvironmentsWrite = Depends(require_permissions("environments:write"))
RequireEnvironmentsDelete = Depends(require_permissions("environments:delete"))


async def add_auth_context_to_request(request: Request) -> None:
    """Middleware to add authentication context to request state."""
    # This can be used as FastAPI middleware to automatically add auth context
    # to all requests, making it available in request.state.user or request.state.automation

    # Extract token from request headers
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return

    token = auth_header.split(" ", 1)[1]

    try:
        token_manager = await get_token_manager()
        validation_result = token_manager.jwt_auth.validate_token(token)

        if validation_result.valid and validation_result.claims:
            claims = validation_result.claims

            if claims.scope == TokenScope.USER:
                # Create user context
                github_client = await get_github_oauth_client()
                permissions = github_client.get_user_permissions(claims.role or UserRole.USER)

                request.state.user = AuthenticatedUser(
                    user_id=claims.sub,
                    username=claims.username or "",
                    email=claims.email or "",
                    role=claims.role or UserRole.USER,
                    github_id=claims.github_id,
                    permissions=permissions,
                    token_claims=claims
                )

            elif claims.scope == TokenScope.AUTOMATION:
                # Create automation context
                request.state.automation = AuthenticatedAutomation(
                    automation_id=claims.sub,
                    automation_name=claims.automation_name or "",
                    permissions=claims.permissions,
                    token_claims=claims
                )

    except Exception as e:
        # Don't fail the request if auth context can't be added
        logger.debug("Failed to add auth context to request", error=str(e))