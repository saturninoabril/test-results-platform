"""
Authentication API endpoints for user and automation token management.
Provides REST API for GitHub OAuth, token generation, and user profile management.
"""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from ..lib.auth import get_token_manager
from ..lib.github_oauth import get_github_oauth_client
from ..lib.middleware import (
    AuthenticatedUser,
    get_current_user,
)
from .models import (
    AutomationTokenRequest,
    TokenRequest,
    TokenResponse,
    UserProfileResponse,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


@router.post(
    "/authorization-url",
    summary="Get GitHub OAuth authorization URL",
    description="Generate a GitHub OAuth authorization URL for SSO authentication",
)
async def get_authorization_url() -> dict[str, Any]:
    """Get GitHub OAuth authorization URL."""
    try:
        github_client = await get_github_oauth_client()
        result = github_client.get_authorization_url()

        logger.info("GitHub OAuth URL generated")
        return result

    except Exception as e:
        logger.error("Failed to generate GitHub OAuth URL", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate GitHub OAuth authorization URL",
        ) from e


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Exchange OAuth code for tokens",
    description="Exchange GitHub OAuth authorization code for access and refresh tokens",
)
async def exchange_token(request: TokenRequest) -> TokenResponse:
    """Exchange OAuth authorization code for tokens."""
    try:
        if request.grant_type != "github_oauth":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid grant_type. Only 'github_oauth' is supported",
            )

        github_client = await get_github_oauth_client()
        result = await github_client.authenticate_user(request.code, request.state)

        if not result.success:
            logger.warning("GitHub OAuth authentication failed", error=result.error)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=result.error or "GitHub OAuth authentication failed",
            )

        logger.info(
            "User authenticated via GitHub OAuth",
            username=result.user_profile.login if result.user_profile else None,
            role=result.user_role.value if result.user_role else None,
        )

        # Get permissions for the user's role
        permissions = (
            github_client.get_user_permissions(result.user_role) if result.user_role else []
        )

        if not result.access_token:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to obtain access token from GitHub",
            )

        return TokenResponse(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            token_type="Bearer",
            expires_in=3600,  # 1 hour in seconds
            permissions=permissions,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Token exchange failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred during token exchange",
        ) from e


@router.post(
    "/automation-token",
    response_model=TokenResponse,
    summary="Generate automation token",
    description="Generate an automation token for CI/CD systems (requires admin privileges)",
    dependencies=[Depends(get_current_user)],
)
async def create_automation_token(
    request: AutomationTokenRequest, current_user: AuthenticatedUser = Depends(get_current_user)
) -> TokenResponse:
    """Generate automation token for CI/CD systems."""
    try:
        # Check if user has admin privileges
        if "automation:write" not in current_user.permissions:
            logger.warning(
                "Insufficient permissions for automation token creation",
                user_id=current_user.user_id,
                permissions=current_user.permissions,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required to create automation tokens",
            )

        token_manager = await get_token_manager()
        result = await token_manager.create_automation_token(
            automation_name=request.automation_name,
            permissions=request.permissions,
            expiration_days=request.expiration_days,
        )

        logger.info(
            "Automation token created",
            automation_name=request.automation_name,
            permissions=request.permissions,
            created_by=current_user.username,
        )

        return TokenResponse(
            access_token=result["automation_token"],
            refresh_token=None,
            token_type="Bearer",
            expires_in=int(result["expires_in_days"]) * 24 * 3600,  # Convert days to seconds
            permissions=result["permissions"].split(",")
            if isinstance(result["permissions"], str) and result["permissions"]
            else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Automation token creation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while creating automation token",
        ) from e


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current user profile",
    description="Get the current authenticated user's profile and permissions",
)
async def get_current_user_profile(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> UserProfileResponse:
    """Get current user's profile."""
    try:
        logger.debug("User profile retrieved", user_id=current_user.user_id)

        return UserProfileResponse(
            user_id=current_user.user_id,
            username=current_user.username,
            email=current_user.email,
            role=current_user.role.value,
            permissions=current_user.permissions,
            github_id=current_user.github_id,
        )

    except Exception as e:
        logger.error("Failed to get user profile", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving user profile",
        ) from e


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Refresh an expired access token using a refresh token",
)
async def refresh_token(refresh_token: str) -> TokenResponse:
    """Refresh access token."""
    try:
        token_manager = await get_token_manager()
        result = await token_manager.refresh_user_token(refresh_token)

        if not result:
            logger.warning("Token refresh failed")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token"
            )

        logger.info("Token refreshed successfully")

        return TokenResponse(
            access_token=result["access_token"],
            refresh_token=result.get("refresh_token"),
            token_type=result["token_type"],
            expires_in=int(result["expires_in"]),
            permissions=(
                perms.split(",")
                if (perms := result.get("permissions")) and isinstance(perms, str)
                else None
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Token refresh failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred during token refresh",
        ) from e
