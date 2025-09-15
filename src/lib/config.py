"""
Project configuration management using Pydantic BaseSettings.
Handles environment-specific settings for database, storage, authentication, and application.
"""

from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""

    model_config = SettingsConfigDict(env_prefix="DATABASE_", extra="ignore")

    url: str = Field(
        default="postgresql+asyncpg://test_results_user:test_results_password@localhost:5433/test_results",
        description="Database connection URL",
    )
    pool_size: int = Field(default=10, ge=1, le=50, description="Connection pool size")
    max_overflow: int = Field(default=20, ge=0, le=100, description="Max overflow connections")
    pool_timeout: int = Field(default=30, ge=1, le=300, description="Pool timeout in seconds")
    echo: bool = Field(default=False, description="Echo SQL queries")

    @field_validator("url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL format."""
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError("Database URL must start with postgresql:// or postgresql+asyncpg://")
        return v


class StorageSettings(BaseSettings):
    """Storage configuration settings."""

    model_config = SettingsConfigDict(env_prefix="STORAGE_", extra="ignore")

    type: str = Field(default="minio", description="Storage type (minio or s3)")
    endpoint: str | None = Field(
        default="http://localhost:9000", description="Storage endpoint URL"
    )
    access_key: str = Field(default="minioadmin", description="Storage access key")
    secret_key: str = Field(default="minioadmin123", description="Storage secret key")
    region: str = Field(default="us-east-1", description="Storage region")
    bucket_prefix: str = Field(default="dev", description="Bucket prefix for environment")
    use_ssl: bool = Field(default=False, description="Use SSL for storage connections")
    max_file_size: int = Field(default=100 * 1024 * 1024, description="Max file size in bytes")
    signed_url_expiry: int = Field(default=3600, description="Signed URL expiry in seconds")

    @field_validator("type")
    @classmethod
    def validate_storage_type(cls, v: str) -> str:
        """Validate storage type."""
        if v not in ("minio", "s3"):
            raise ValueError("Storage type must be 'minio' or 's3'")
        return v

    @field_validator("max_file_size")
    @classmethod
    def validate_max_file_size(cls, v: int) -> int:
        """Validate max file size is reasonable."""
        if v < 1024 or v > 1024 * 1024 * 1024:  # 1KB to 1GB
            raise ValueError("Max file size must be between 1KB and 1GB")
        return v


class AuthSettings(BaseSettings):
    """Authentication configuration settings."""

    model_config = SettingsConfigDict(env_prefix="AUTH_", extra="ignore")

    jwt_secret_key: str = Field(
        default="dev-secret-key-change-in-production",
        description="JWT secret key",
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expiration_hours: int = Field(
        default=24, ge=1, le=168, description="JWT expiration in hours"
    )

    # GitHub OAuth settings
    github_client_id: str | None = Field(default=None, description="GitHub OAuth client ID")
    github_client_secret: str | None = Field(default=None, description="GitHub OAuth client secret")
    github_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/auth/callback",
        description="GitHub OAuth redirect URI",
    )

    # Automation token settings
    automation_token_expiry_days: int = Field(
        default=90, ge=1, le=365, description="Automation token expiry in days"
    )

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret_key(cls, v: str) -> str:
        """Validate JWT secret key strength."""
        if len(v) < 32:
            raise ValueError("JWT secret key must be at least 32 characters long")
        return v

    @field_validator("jwt_algorithm")
    @classmethod
    def validate_jwt_algorithm(cls, v: str) -> str:
        """Validate JWT algorithm."""
        allowed_algorithms = ["HS256", "HS384", "HS512", "RS256", "RS384", "RS512"]
        if v not in allowed_algorithms:
            raise ValueError(f"JWT algorithm must be one of: {allowed_algorithms}")
        return v


class MattermostSettings(BaseSettings):
    """Mattermost webhook configuration settings."""

    model_config = SettingsConfigDict(env_prefix="MATTERMOST_", extra="ignore")

    webhook_url: str | None = Field(default=None, description="Mattermost webhook URL")
    username: str = Field(default="Test Results Bot", description="Webhook username")
    icon_url: str | None = Field(default=None, description="Bot icon URL")
    channel: str | None = Field(default=None, description="Default channel to post to")
    enabled: bool = Field(default=False, description="Enable Mattermost notifications")

    # Notification settings
    notify_test_failures: bool = Field(default=True, description="Notify on test failures")
    notify_suite_completion: bool = Field(default=True, description="Notify on suite completion")
    notify_high_failure_rate: bool = Field(default=True, description="Notify on high failure rate")
    failure_rate_threshold: float = Field(
        default=0.1, ge=0.0, le=1.0, description="Failure rate threshold (0.0-1.0)"
    )

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str | None) -> str | None:
        """Validate Mattermost webhook URL format."""
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("Webhook URL must start with http:// or https://")
        return v


class AppSettings(BaseSettings):
    """Application configuration settings."""

    model_config = SettingsConfigDict(env_prefix="APP_", extra="ignore")

    name: str = Field(default="Test Results API", description="Application name")
    version: str = Field(default="0.4.0", description="Application version")
    description: str = Field(
        default="REST API for managing test execution results from end-to-end testing frameworks",
        description="Application description",
    )
    env: str = Field(
        default="development", description="Environment (development, staging, production)"
    )
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="info", description="Logging level")

    # API configuration
    api_prefix: str = Field(default="/api/v1", description="API prefix")
    docs_url: str | None = Field(default="/docs", description="Swagger UI URL")
    redoc_url: str | None = Field(default="/redoc", description="ReDoc URL")

    # Performance settings
    max_requests_per_second: int = Field(default=1000, ge=1, description="Max requests per second")
    request_timeout: int = Field(default=30, ge=1, le=300, description="Request timeout in seconds")

    # CORS settings
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="Allowed CORS origins",
    )
    cors_allow_credentials: bool = Field(default=True, description="Allow credentials in CORS")

    @field_validator("env")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment."""
        allowed_envs = ["development", "staging", "production", "test"]
        if v not in allowed_envs:
            raise ValueError(f"Environment must be one of: {allowed_envs}")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        allowed_levels = ["debug", "info", "warning", "error", "critical"]
        if v.lower() not in allowed_levels:
            raise ValueError(f"Log level must be one of: {allowed_levels}")
        return v.lower()


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Sub-settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    app: AppSettings = Field(default_factory=AppSettings)
    mattermost: MattermostSettings = Field(default_factory=MattermostSettings)

    # Redis settings (optional)
    redis_url: str | None = Field(default="redis://localhost:6379/0", description="Redis URL")

    def get_bucket_name(self, artifact_type: str) -> str:
        """Get bucket name for artifact type and environment."""
        return f"{self.storage.bucket_prefix}-{artifact_type}"

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app.env == "production"

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.app.env == "development"

    def get_cors_config(self) -> dict[str, Any]:
        """Get CORS configuration dictionary."""
        return {
            "allow_origins": self.app.cors_origins,
            "allow_credentials": self.app.cors_allow_credentials,
            "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["*"],
        }


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
