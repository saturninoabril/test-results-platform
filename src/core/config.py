"""
Production-ready configuration management with environment-specific settings.
"""

import logging
import os
import secrets
from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, ValidationInfo, field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""

    url: PostgresDsn = Field(description="Database URL")
    pool_size: int = Field(default=50, description="Database connection pool size")
    max_overflow: int = Field(default=100, description="Maximum pool overflow")
    pool_timeout: int = Field(default=30, description="Pool timeout in seconds")
    pool_recycle: int = Field(default=3600, description="Pool recycle time")
    query_timeout: int = Field(default=30, description="Query timeout in seconds")
    echo: bool = Field(default=False, description="Enable SQL query logging")

    model_config = {"env_prefix": "DATABASE_"}


class StorageSettings(BaseSettings):
    """Storage configuration settings."""

    type: Literal["s3", "minio"] = Field(default="s3", description="Storage type")
    endpoint: str | None = Field(default=None, description="Storage endpoint URL")
    access_key: str = Field(description="Storage access key")
    secret_key: str = Field(description="Storage secret key")
    bucket: str = Field(description="Storage bucket name")
    region: str = Field(default="us-east-1", description="Storage region")
    secure: bool = Field(default=True, description="Use secure connection")

    model_config = {"env_prefix": "STORAGE_"}


class AuthSettings(BaseSettings):
    """Authentication configuration settings."""

    jwt_secret_key: str = Field(description="JWT secret key")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expiration_hours: int = Field(default=24, description="JWT expiration in hours")
    automation_token_max_age_days: int = Field(
        default=365, description="Automation token max age in days"
    )

    # GitHub OAuth
    github_client_id: str | None = Field(default=None, description="GitHub OAuth client ID")
    github_client_secret: str | None = Field(default=None, description="GitHub OAuth client secret")
    github_redirect_uri: str | None = Field(default=None, description="GitHub OAuth redirect URI")

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT secret key must be at least 32 characters long")
        return v

    model_config = {"env_prefix": "AUTH_"}


class LoggingSettings(BaseSettings):
    """Logging configuration settings."""

    level: str = Field(default="INFO", description="Log level")
    format: Literal["json", "standard"] = Field(default="json", description="Log format")
    file: str | None = Field(default=None, description="Log file path")
    max_file_size_mb: int = Field(default=100, description="Max log file size in MB")
    backup_count: int = Field(default=5, description="Log backup count")
    structured_logging: bool = Field(default=True, description="Enable structured logging")

    model_config = {"env_prefix": "LOG_"}


class MetricsSettings(BaseSettings):
    """Metrics and monitoring configuration."""

    enabled: bool = Field(default=True, description="Enable metrics collection")
    endpoint: str = Field(default="/metrics", description="Metrics endpoint path")
    include_request_id: bool = Field(default=True, description="Include request ID in metrics")
    slow_query_threshold_ms: float = Field(default=1000.0, description="Slow query threshold in ms")

    model_config = {"env_prefix": "METRICS_"}


class SecuritySettings(BaseSettings):
    """Security configuration settings."""

    # CORS
    cors_origins: list[str] = Field(default=["*"])
    cors_allow_credentials: bool = Field(default=True)
    cors_allow_methods: list[str] = Field(default=["*"])
    cors_allow_headers: list[str] = Field(default=["*"])

    # Security headers
    enable_security_headers: bool = Field(default=True)
    hsts_max_age: int = Field(default=31536000)  # 1 year
    content_security_policy: str | None = Field(default=None)

    # Rate limiting
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_requests_per_minute: int = Field(default=60)
    rate_limit_burst: int = Field(default=20)

    # File upload limits
    max_upload_size_mb: int = Field(default=100)
    allowed_file_types: list[str] = Field(
        default=[
            "image/png",
            "image/jpeg",
            "image/gif",
            "image/webp",
            "video/mp4",
            "video/webm",
            "video/avi",
            "application/pdf",
            "text/html",
            "text/plain",
            "application/zip",
            "application/x-tar",
            "application/gzip",
        ]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("cors_allow_methods", mode="before")
    @classmethod
    def parse_cors_methods(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [method.strip() for method in v.split(",")]
        return v

    @field_validator("cors_allow_headers", mode="before")
    @classmethod
    def parse_cors_headers(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [header.strip() for header in v.split(",")]
        return v

    @field_validator("allowed_file_types", mode="before")
    @classmethod
    def parse_allowed_file_types(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [file_type.strip() for file_type in v.split(",")]
        return v

    model_config = {"env_prefix": "SECURITY_"}


class PerformanceSettings(BaseSettings):
    """Performance optimization settings."""

    # Worker configuration
    workers: int = Field(default=4)
    max_requests: int = Field(default=1000)
    max_requests_jitter: int = Field(default=50)
    timeout_keep_alive: int = Field(default=5)

    # Caching
    cache_enabled: bool = Field(default=True)
    cache_redis_url: str | None = Field(default=None)
    cache_ttl_seconds: int = Field(default=300)

    # Response limits
    max_response_size_mb: int = Field(default=50)
    api_timeout_seconds: int = Field(default=30)

    model_config = {"env_prefix": "PERFORMANCE_"}


class Settings(BaseSettings):
    """Main application settings."""

    # Application metadata
    app_name: str = Field(default="Test Results Management API")
    app_version: str = Field(default="0.4.0")
    app_description: str = Field(
        default="REST API for managing test execution results from end-to-end testing frameworks"
    )

    # Environment
    environment: Literal["development", "staging", "production"] = Field(default="development")
    debug: bool = Field(default=False)

    # API configuration
    api_v1_prefix: str = Field(default="/v1")
    docs_url: str | None = Field(default="/docs")
    redoc_url: str | None = Field(default="/redoc")
    openapi_url: str | None = Field(default="/openapi.json")

    # Server configuration
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    reload: bool = Field(default=False)

    # Sub-configurations
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)  # type: ignore[arg-type]
    storage: StorageSettings = Field(default_factory=StorageSettings)  # type: ignore[arg-type]
    auth: AuthSettings = Field(default_factory=AuthSettings)  # type: ignore[arg-type]
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    metrics: MetricsSettings = Field(default_factory=MetricsSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    performance: PerformanceSettings = Field(default_factory=PerformanceSettings)

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        if v not in ["development", "staging", "production"]:
            raise ValueError("Environment must be development, staging, or production")
        return v

    @field_validator("docs_url", "redoc_url", "openapi_url", mode="before")
    @classmethod
    def disable_docs_in_production(cls, v: str | None, info: ValidationInfo) -> str | None:
        if info.data.get("environment") == "production":
            return None
        return v

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    def get_database_url(self) -> str:
        """Get database URL string."""
        return str(self.database.url)

    def get_cors_origins(self) -> list[str]:
        """Get CORS origins list."""
        if self.is_development():
            return ["*"]
        return self.security.cors_origins

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "validate_assignment": True,
    }


class DevelopmentSettings(Settings):
    """Development-specific settings."""

    environment: Literal["development"] = "development"
    debug: bool = True
    reload: bool = True

    # Override sub-settings for development
    logging: LoggingSettings = Field(
        default_factory=lambda: LoggingSettings(
            level="DEBUG", format="standard", structured_logging=False
        )
    )

    security: SecuritySettings = Field(
        default_factory=lambda: SecuritySettings(
            cors_origins=["*"], rate_limit_enabled=False, enable_security_headers=False
        )
    )

    performance: PerformanceSettings = Field(
        default_factory=lambda: PerformanceSettings(workers=1, cache_enabled=False)
    )


class ProductionSettings(Settings):
    """Production-specific settings."""

    environment: Literal["production"] = "production"
    debug: bool = False
    reload: bool = False
    docs_url: str | None = None
    redoc_url: str | None = None

    # Override sub-settings for production
    logging: LoggingSettings = Field(
        default_factory=lambda: LoggingSettings(
            level="INFO", format="json", structured_logging=True
        )
    )

    security: SecuritySettings = Field(
        default_factory=lambda: SecuritySettings(
            enable_security_headers=True, rate_limit_enabled=True
        )
    )


class StagingSettings(Settings):
    """Staging-specific settings."""

    environment: Literal["staging"] = "staging"
    debug: bool = False

    logging: LoggingSettings = Field(
        default_factory=lambda: LoggingSettings(level="INFO", format="json")
    )


@lru_cache
def get_settings() -> Settings:
    """Get application settings (cached)."""

    environment = os.getenv("APP_ENVIRONMENT", "development").lower()

    settings_class: type[Settings]
    if environment == "production":
        settings_class = ProductionSettings
    elif environment == "staging":
        settings_class = StagingSettings
    else:
        settings_class = DevelopmentSettings

    try:
        settings = settings_class()
        logger.info(f"Loaded {environment} settings")
        return settings
    except Exception as e:
        logger.error(f"Failed to load settings: {e}")
        # Fallback to development settings
        return DevelopmentSettings()


def generate_secret_key() -> str:
    """Generate a secure secret key."""
    return secrets.token_urlsafe(32)


def validate_configuration(settings: Settings) -> list[str]:
    """Validate configuration and return any warnings or errors."""

    warnings = []

    # Check required production settings
    if settings.is_production():
        if settings.auth.jwt_secret_key == "dev-secret-key":
            warnings.append("Using default JWT secret key in production")

        if not settings.auth.github_client_id:
            warnings.append("GitHub OAuth not configured")

        if "*" in settings.security.cors_origins:
            warnings.append("CORS allows all origins in production")

        if not settings.logging.file:
            warnings.append("No log file configured for production")

    # Check database configuration
    if "localhost" in str(settings.database.url) and settings.is_production():
        warnings.append("Using localhost database URL in production")

    # Check storage configuration
    if settings.storage.type == "minio" and settings.is_production():
        warnings.append("Using MinIO storage in production (consider S3)")

    return warnings


# Export the main settings function
settings = get_settings()
