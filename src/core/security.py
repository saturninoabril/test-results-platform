"""
Security middleware and configuration for production deployment.
"""

import time
import logging
from typing import Dict, List, Optional, Callable
from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import hashlib
import hmac
from urllib.parse import urlparse

from .config import Settings

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""

    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""

        response = await call_next(request)

        if self.settings.security.enable_security_headers:
            # Strict Transport Security (HSTS)
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self.settings.security.hsts_max_age}; "
                "includeSubDomains; preload"
            )

            # Content Security Policy
            if self.settings.security.content_security_policy:
                response.headers["Content-Security-Policy"] = (
                    self.settings.security.content_security_policy
                )
            else:
                # Default CSP
                response.headers["Content-Security-Policy"] = (
                    "default-src 'self'; "
                    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                    "style-src 'self' 'unsafe-inline'; "
                    "img-src 'self' data: https:; "
                    "font-src 'self' data:; "
                    "connect-src 'self' https:; "
                    "frame-ancestors 'none'"
                )

            # X-Frame-Options
            response.headers["X-Frame-Options"] = "DENY"

            # X-Content-Type-Options
            response.headers["X-Content-Type-Options"] = "nosniff"

            # X-XSS-Protection
            response.headers["X-XSS-Protection"] = "1; mode=block"

            # Referrer Policy
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

            # Permissions Policy
            response.headers["Permissions-Policy"] = (
                "geolocation=(), microphone=(), camera=(), "
                "payment=(), usb=(), magnetometer=(), gyroscope=()"
            )

            # Remove server information
            response.headers.pop("Server", None)

        return response


class RequestSizeMiddleware(BaseHTTPMiddleware):
    """Middleware to limit request size."""

    def __init__(self, app, max_size_mb: int = 100):
        super().__init__(app)
        self.max_size_bytes = max_size_mb * 1024 * 1024

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check request size before processing."""

        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Request size exceeds maximum allowed size of {self.max_size_bytes / 1024 / 1024}MB"
            )

        return await call_next(request)


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """Middleware to whitelist IP addresses (optional)."""

    def __init__(self, app, allowed_ips: List[str] = None):
        super().__init__(app)
        self.allowed_ips = allowed_ips or []

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check if IP is in whitelist."""

        if not self.allowed_ips:
            return await call_next(request)

        client_ip = get_remote_address(request)
        if client_ip not in self.allowed_ips:
            logger.warning(f"Blocked request from unauthorized IP: {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied from this IP address"
            )

        return await call_next(request)


class WebhookSignatureMiddleware(BaseHTTPMiddleware):
    """Middleware to validate webhook signatures."""

    def __init__(self, app, webhook_secret: Optional[str] = None):
        super().__init__(app)
        self.webhook_secret = webhook_secret

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Validate webhook signature for webhook endpoints."""

        # Only apply to webhook endpoints
        if not request.url.path.startswith("/webhooks/"):
            return await call_next(request)

        if not self.webhook_secret:
            logger.warning("Webhook endpoint accessed but no secret configured")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Webhook authentication required"
            )

        # Get signature from headers
        signature = request.headers.get("X-Webhook-Signature")
        if not signature:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing webhook signature"
            )

        # Read request body for signature validation
        body = await request.body()

        # Validate signature
        expected_signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, f"sha256={expected_signature}"):
            logger.warning("Invalid webhook signature received")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )

        return await call_next(request)


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Middleware to add request timing headers."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add timing information to response headers."""

        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time

        response.headers["X-Process-Time"] = str(process_time)
        return response


def configure_cors(app: FastAPI, settings: Settings) -> None:
    """Configure CORS middleware."""

    origins = settings.get_cors_origins()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=settings.security.cors_allow_credentials,
        allow_methods=settings.security.cors_allow_methods,
        allow_headers=settings.security.cors_allow_headers,
        expose_headers=["X-Process-Time", "X-Request-ID"]
    )

    logger.info(f"CORS configured with origins: {origins}")


def configure_rate_limiting(app: FastAPI, settings: Settings) -> Limiter:
    """Configure rate limiting."""

    if not settings.security.rate_limit_enabled:
        logger.info("Rate limiting disabled")
        return None

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[f"{settings.security.rate_limit_requests_per_minute}/minute"]
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    logger.info(f"Rate limiting configured: {settings.security.rate_limit_requests_per_minute}/minute")
    return limiter


def configure_trusted_hosts(app: FastAPI, allowed_hosts: List[str] = None) -> None:
    """Configure trusted host middleware."""

    if not allowed_hosts:
        return

    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=allowed_hosts
    )

    logger.info(f"Trusted hosts configured: {allowed_hosts}")


def setup_security_middleware(app: FastAPI, settings: Settings) -> Dict[str, any]:
    """Set up all security middleware and return configuration."""

    security_config = {}

    # Add compression middleware (early in stack)
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Add request size limiting
    app.add_middleware(
        RequestSizeMiddleware,
        max_size_mb=settings.security.max_upload_size_mb
    )

    # Add security headers
    app.add_middleware(SecurityHeadersMiddleware, settings=settings)

    # Add request timing
    app.add_middleware(RequestTimingMiddleware)

    # Configure CORS
    configure_cors(app, settings)
    security_config["cors_origins"] = settings.get_cors_origins()

    # Configure rate limiting
    limiter = configure_rate_limiting(app, settings)
    security_config["rate_limiting"] = settings.security.rate_limit_enabled

    # Configure trusted hosts for production
    if settings.is_production():
        # Extract hosts from CORS origins
        trusted_hosts = []
        for origin in settings.security.cors_origins:
            if origin != "*":
                parsed = urlparse(origin)
                if parsed.netloc:
                    trusted_hosts.append(parsed.netloc)

        if trusted_hosts:
            configure_trusted_hosts(app, trusted_hosts)
            security_config["trusted_hosts"] = trusted_hosts

    # Optional: IP whitelist (if configured)
    allowed_ips = []  # Could be loaded from environment
    if allowed_ips:
        app.add_middleware(IPWhitelistMiddleware, allowed_ips=allowed_ips)
        security_config["ip_whitelist"] = len(allowed_ips)

    # Optional: Webhook signature validation
    webhook_secret = None  # Could be loaded from environment
    if webhook_secret:
        app.add_middleware(WebhookSignatureMiddleware, webhook_secret=webhook_secret)
        security_config["webhook_auth"] = True

    logger.info("Security middleware configured")
    return security_config


class FileTypeValidator:
    """Validate uploaded file types."""

    def __init__(self, allowed_types: List[str]):
        self.allowed_types = allowed_types

    def validate_content_type(self, content_type: str) -> bool:
        """Validate content type against allowed types."""
        return content_type in self.allowed_types

    def validate_file_extension(self, filename: str) -> bool:
        """Validate file extension."""
        if not filename:
            return False

        extension = filename.lower().split('.')[-1]

        # Map extensions to content types
        extension_map = {
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif': 'image/gif',
            'webp': 'image/webp',
            'mp4': 'video/mp4',
            'webm': 'video/webm',
            'avi': 'video/avi',
            'pdf': 'application/pdf',
            'html': 'text/html',
            'txt': 'text/plain',
            'zip': 'application/zip',
            'tar': 'application/x-tar',
            'gz': 'application/gzip'
        }

        content_type = extension_map.get(extension)
        return content_type in self.allowed_types if content_type else False

    def get_allowed_extensions(self) -> List[str]:
        """Get list of allowed file extensions."""
        extension_map = {
            'image/png': 'png',
            'image/jpeg': 'jpg',
            'image/gif': 'gif',
            'image/webp': 'webp',
            'video/mp4': 'mp4',
            'video/webm': 'webm',
            'video/avi': 'avi',
            'application/pdf': 'pdf',
            'text/html': 'html',
            'text/plain': 'txt',
            'application/zip': 'zip',
            'application/x-tar': 'tar',
            'application/gzip': 'gz'
        }

        return [extension_map[ct] for ct in self.allowed_types if ct in extension_map]


def create_file_validator(settings: Settings) -> FileTypeValidator:
    """Create file type validator from settings."""
    return FileTypeValidator(settings.security.allowed_file_types)


def validate_api_key(api_key: str) -> bool:
    """Validate API key format (basic validation)."""
    if not api_key:
        return False

    # Basic validation - should be reasonable length
    if len(api_key) < 20:
        return False

    # Should contain alphanumeric characters
    if not any(c.isalnum() for c in api_key):
        return False

    return True


def generate_request_id() -> str:
    """Generate unique request ID."""
    import uuid
    return str(uuid.uuid4())


def mask_sensitive_data(data: dict, sensitive_keys: List[str] = None) -> dict:
    """Mask sensitive data in logs/responses."""

    if sensitive_keys is None:
        sensitive_keys = [
            'password', 'secret', 'token', 'key', 'auth',
            'authorization', 'credentials', 'private'
        ]

    masked_data = data.copy()

    for key, value in data.items():
        if any(sensitive_key in key.lower() for sensitive_key in sensitive_keys):
            if isinstance(value, str) and len(value) > 4:
                masked_data[key] = value[:4] + "*" * (len(value) - 4)
            else:
                masked_data[key] = "***"
        elif isinstance(value, dict):
            masked_data[key] = mask_sensitive_data(value, sensitive_keys)

    return masked_data