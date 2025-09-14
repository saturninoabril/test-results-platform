"""
Production-ready configuration management with environment-specific settings.
"""

import os
import secrets
from typing import Any, Dict, List, Optional, Union, Literal
from pydantic import BaseSettings, validator, Field, AnyHttpUrl, PostgresDsn
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""

    url: PostgresDsn = Field(..., env="DATABASE_URL")
    pool_size: int = Field(50, env="DATABASE_POOL_SIZE")
    max_overflow: int = Field(100, env="DATABASE_MAX_OVERFLOW")
    pool_timeout: int = Field(30, env="DATABASE_POOL_TIMEOUT")
    pool_recycle: int = Field(3600, env="DATABASE_POOL_RECYCLE")
    query_timeout: int = Field(30, env="DATABASE_QUERY_TIMEOUT")
    echo: bool = Field(False, env="DATABASE_ECHO")

    class Config:
        env_prefix = "DATABASE_"


class StorageSettings(BaseSettings):
    """Storage configuration settings."""

    type: Literal["s3", "minio"] = Field("s3", env="STORAGE_TYPE")
    endpoint: Optional[str] = Field(None, env="STORAGE_ENDPOINT")
    access_key: str = Field(..., env="STORAGE_ACCESS_KEY")
    secret_key: str = Field(..., env="STORAGE_SECRET_KEY")
    bucket: str = Field(..., env="STORAGE_BUCKET")
    region: str = Field("us-east-1", env="STORAGE_REGION")
    secure: bool = Field(True, env="STORAGE_SECURE")

    class Config:
        env_prefix = "STORAGE_"


class AuthSettings(BaseSettings):
    """Authentication configuration settings."""

    jwt_secret_key: str = Field(..., env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field("HS256", env="JWT_ALGORITHM")
    jwt_expiration_hours: int = Field(24, env="JWT_EXPIRATION_HOURS")
    automation_token_max_age_days: int = Field(365, env="AUTOMATION_TOKEN_MAX_AGE_DAYS")

    # GitHub OAuth
    github_client_id: Optional[str] = Field(None, env="GITHUB_CLIENT_ID")
    github_client_secret: Optional[str] = Field(None, env="GITHUB_CLIENT_SECRET")
    github_redirect_uri: Optional[str] = Field(None, env="GITHUB_REDIRECT_URI")

    @validator("jwt_secret_key")
    def validate_jwt_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT secret key must be at least 32 characters long")
        return v

    class Config:
        env_prefix = "AUTH_"


class LoggingSettings(BaseSettings):
    """Logging configuration settings."""

    level: str = Field("INFO", env="LOG_LEVEL")
    format: Literal["json", "standard"] = Field("json", env="LOG_FORMAT")
    file: Optional[str] = Field(None, env="LOG_FILE")
    max_file_size_mb: int = Field(100, env="LOG_MAX_FILE_SIZE_MB")
    backup_count: int = Field(5, env="LOG_BACKUP_COUNT")
    structured_logging: bool = Field(True, env="STRUCTURED_LOGGING")

    class Config:
        env_prefix = "LOG_"


class MetricsSettings(BaseSettings):
    """Metrics and monitoring configuration."""

    enabled: bool = Field(True, env="METRICS_ENABLED")
    endpoint: str = Field("/metrics", env="METRICS_ENDPOINT")
    include_request_id: bool = Field(True, env="METRICS_INCLUDE_REQUEST_ID")
    slow_query_threshold_ms: float = Field(1000.0, env="METRICS_SLOW_QUERY_THRESHOLD_MS")

    class Config:
        env_prefix = "METRICS_"


class SecuritySettings(BaseSettings):
    """Security configuration settings."""

    # CORS
    cors_origins: List[str] = Field(["*"], env="CORS_ORIGINS")
    cors_allow_credentials: bool = Field(True, env="CORS_ALLOW_CREDENTIALS")
    cors_allow_methods: List[str] = Field(["*"], env="CORS_ALLOW_METHODS")
    cors_allow_headers: List[str] = Field(["*"], env="CORS_ALLOW_HEADERS")

    # Security headers
    enable_security_headers: bool = Field(True, env="ENABLE_SECURITY_HEADERS")
    hsts_max_age: int = Field(31536000, env="HSTS_MAX_AGE")  # 1 year
    content_security_policy: Optional[str] = Field(None, env="CONTENT_SECURITY_POLICY")

    # Rate limiting
    rate_limit_enabled: bool = Field(True, env="RATE_LIMIT_ENABLED")
    rate_limit_requests_per_minute: int = Field(60, env="RATE_LIMIT_REQUESTS_PER_MINUTE")
    rate_limit_burst: int = Field(20, env="RATE_LIMIT_BURST")

    # File upload limits
    max_upload_size_mb: int = Field(100, env="MAX_UPLOAD_SIZE_MB")
    allowed_file_types: List[str] = Field([
        "image/png", "image/jpeg", "image/gif", "image/webp",
        "video/mp4", "video/webm", "video/avi",
        "application/pdf", "text/html", "text/plain",
        "application/zip", "application/x-tar", "application/gzip"
    ], env="ALLOWED_FILE_TYPES")

    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @validator("cors_allow_methods", pre=True)
    def parse_cors_methods(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [method.strip() for method in v.split(",")]
        return v

    @validator("cors_allow_headers", pre=True)
    def parse_cors_headers(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [header.strip() for header in v.split(",")]
        return v

    @validator("allowed_file_types", pre=True)
    def parse_allowed_file_types(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [file_type.strip() for file_type in v.split(",")]
        return v

    class Config:
        env_prefix = "SECURITY_"


class PerformanceSettings(BaseSettings):
    """Performance optimization settings."""

    # Worker configuration
    workers: int = Field(4, env="WORKERS")
    max_requests: int = Field(1000, env="MAX_REQUESTS")
    max_requests_jitter: int = Field(50, env="MAX_REQUESTS_JITTER")
    timeout_keep_alive: int = Field(5, env="TIMEOUT_KEEP_ALIVE")

    # Caching
    cache_enabled: bool = Field(True, env="CACHE_ENABLED")
    cache_redis_url: Optional[str] = Field(None, env="CACHE_REDIS_URL")
    cache_ttl_seconds: int = Field(300, env="CACHE_TTL_SECONDS")

    # Response limits
    max_response_size_mb: int = Field(50, env="MAX_RESPONSE_SIZE_MB")
    api_timeout_seconds: int = Field(30, env="API_TIMEOUT_SECONDS")

    class Config:
        env_prefix = "PERFORMANCE_"


class Settings(BaseSettings):
    """Main application settings."""

    # Application metadata
    app_name: str = Field("Test Results Management API", env="APP_NAME")
    app_version: str = Field("0.4.0", env="APP_VERSION")
    app_description: str = Field(
        "REST API for managing test execution results from end-to-end testing frameworks",
        env="APP_DESCRIPTION"
    )

    # Environment
    environment: Literal["development", "staging", "production"] = Field(
        "development", env="APP_ENVIRONMENT"
    )
    debug: bool = Field(False, env="DEBUG")

    # API configuration
    api_v1_prefix: str = Field("/v1", env="API_V1_PREFIX")
    docs_url: Optional[str] = Field("/docs", env="DOCS_URL")
    redoc_url: Optional[str] = Field("/redoc", env="REDOC_URL")
    openapi_url: Optional[str] = Field("/openapi.json", env="OPENAPI_URL")

    # Server configuration
    host: str = Field("0.0.0.0", env="HOST")
    port: int = Field(8000, env="PORT")
    reload: bool = Field(False, env="RELOAD")

    # Sub-configurations
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    metrics: MetricsSettings = Field(default_factory=MetricsSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    performance: PerformanceSettings = Field(default_factory=PerformanceSettings)

    @validator("environment")
    def validate_environment(cls, v: str) -> str:
        if v not in ["development", "staging", "production"]:
            raise ValueError("Environment must be development, staging, or production")
        return v

    @validator("docs_url", "redoc_url", "openapi_url", pre=True)
    def disable_docs_in_production(cls, v: Optional[str], values: Dict[str, Any]) -> Optional[str]:
        if values.get("environment") == "production":
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

    def get_cors_origins(self) -> List[str]:
        """Get CORS origins list."""
        if self.is_development():
            return ["*"]
        return self.security.cors_origins

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        validate_assignment = True


class DevelopmentSettings(Settings):
    """Development-specific settings."""

    environment: Literal["development"] = "development"
    debug: bool = True
    reload: bool = True

    # Override sub-settings for development
    logging: LoggingSettings = Field(default_factory=lambda: LoggingSettings(
        level="DEBUG",
        format="standard",
        structured_logging=False
    ))

    security: SecuritySettings = Field(default_factory=lambda: SecuritySettings(
        cors_origins=["*"],
        rate_limit_enabled=False,
        enable_security_headers=False
    ))

    performance: PerformanceSettings = Field(default_factory=lambda: PerformanceSettings(
        workers=1,
        cache_enabled=False
    ))


class ProductionSettings(Settings):
    """Production-specific settings."""

    environment: Literal["production"] = "production"
    debug: bool = False
    reload: bool = False
    docs_url: Optional[str] = None
    redoc_url: Optional[str] = None

    # Override sub-settings for production
    logging: LoggingSettings = Field(default_factory=lambda: LoggingSettings(
        level="INFO",
        format="json",
        structured_logging=True
    ))

    security: SecuritySettings = Field(default_factory=lambda: SecuritySettings(
        enable_security_headers=True,
        rate_limit_enabled=True
    ))


class StagingSettings(Settings):
    """Staging-specific settings."""

    environment: Literal["staging"] = "staging"
    debug: bool = False

    logging: LoggingSettings = Field(default_factory=lambda: LoggingSettings(
        level="INFO",
        format="json"
    ))


@lru_cache()
def get_settings() -> Settings:
    """Get application settings (cached)."""

    environment = os.getenv("APP_ENVIRONMENT", "development").lower()

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


def validate_configuration(settings: Settings) -> List[str]:
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