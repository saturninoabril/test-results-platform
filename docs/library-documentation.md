# Library Documentation

## Overview

The Test Results Management API is built with a library-first architecture, where each major feature is implemented as a standalone library that can be used independently or together. This document provides comprehensive documentation of all libraries and their APIs.

## Library Structure

```
src/
├── models/          # SQLAlchemy database models
│   ├── base.py         # Base model with common fields
│   ├── test_framework.py  # TestFramework model
│   ├── test_environment.py # TestEnvironment model
│   ├── test_suite.py   # TestSuite model
│   ├── test_result.py  # TestResult model
│   └── test_artifact.py # TestArtifact model
└── services/        # Business logic libraries
    ├── auth.py         # Authentication and authorization
    ├── database.py     # Database connection management
    ├── storage.py      # File storage operations
    ├── test_results.py # Test result CRUD operations
    └── webhooks.py     # Webhook management
```

## Database Models

### Base Model (`src/models/base.py`)

All models inherit from a common base that provides standard fields and functionality.

```python
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, DateTime, func
from typing import Dict, Any
import uuid

Base = declarative_base()

class BaseModel(Base):
    __abstract__ = True

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary."""
        return {
            column.key: getattr(self, column.key)
            for column in self.__table__.columns
        }

    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update model instance from dictionary."""
        for key, value in data.items():
            if hasattr(self, key) and key not in ['id', 'created_at']:
                setattr(self, key, value)

# Usage examples:
from src.models.test_framework import TestFramework

# Create instance
framework = TestFramework(
    id="playwright-1.55.0",
    name="Playwright",
    version="1.55.0"
)

# Convert to dict
data = framework.to_dict()
# Returns: {"id": "playwright-1.55.0", "name": "Playwright", ...}

# Update from dict
framework.update_from_dict({"version": "1.56.0"})
```

### TestFramework Model (`src/models/test_framework.py`)

Represents testing frameworks like Playwright, Cypress, etc.

```python
from sqlalchemy import Column, String, JSON
from .base import BaseModel

class TestFramework(BaseModel):
    __tablename__ = 'test_frameworks'

    id = Column(String(255), primary_key=True)  # e.g., "playwright-1.55.0"
    name = Column(String(100), nullable=False)   # e.g., "Playwright"
    version = Column(String(50), nullable=False) # e.g., "1.55.0"
    metadata = Column(JSON, default=dict)        # Framework-specific config

# Usage examples:
framework = TestFramework(
    id="cypress-13.0.0",
    name="Cypress",
    version="13.0.0",
    metadata={
        "supports_parallel": False,
        "artifact_types": ["screenshot", "video"],
        "config_file": "cypress.json"
    }
)

# Query examples:
async def get_frameworks_by_name(db: AsyncSession, name: str):
    result = await db.execute(
        select(TestFramework).where(TestFramework.name == name)
    )
    return result.scalars().all()

async def get_latest_framework_version(db: AsyncSession, name: str):
    result = await db.execute(
        select(TestFramework)
        .where(TestFramework.name == name)
        .order_by(TestFramework.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
```

### TestEnvironment Model (`src/models/test_environment.py`)

Defines execution environments for tests.

```python
from sqlalchemy import Column, String, JSON
from .base import BaseModel

class TestEnvironment(BaseModel):
    __tablename__ = 'test_environments'

    id = Column(String(255), primary_key=True)   # e.g., "chrome-ubuntu-ci"
    name = Column(String(200), nullable=False)   # e.g., "Chrome on Ubuntu (CI)"
    browser = Column(String(50))                 # e.g., "chromium", "firefox"
    os = Column(String(50))                      # e.g., "ubuntu-latest", "windows"
    metadata = Column(JSON, default=dict)        # Environment-specific config

# Usage examples:
env = TestEnvironment(
    id="firefox-macos-local",
    name="Firefox on macOS (Local Development)",
    browser="firefox",
    os="macOS",
    metadata={
        "headless": False,
        "viewport": "1920x1080",
        "device_scale_factor": 2,
        "locale": "en-US",
        "timezone": "America/New_York"
    }
)

# Query examples:
async def get_environments_by_browser(db: AsyncSession, browser: str):
    result = await db.execute(
        select(TestEnvironment).where(TestEnvironment.browser == browser)
    )
    return result.scalars().all()

async def get_ci_environments(db: AsyncSession):
    result = await db.execute(
        select(TestEnvironment)
        .where(TestEnvironment.metadata['ci_environment'].astext.isnot(None))
    )
    return result.scalars().all()
```

### TestSuite Model (`src/models/test_suite.py`)

Groups related test results from a single execution.

```python
from sqlalchemy import Column, String, Integer, DateTime, JSON, Enum
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
from .base import BaseModel

class TestSuiteStatus(PyEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TestSuite(BaseModel):
    __tablename__ = 'test_suites'

    id = Column(String(255), primary_key=True)
    external_id = Column(String(255))             # CI run ID, etc.
    name = Column(String(500), nullable=False)
    framework_id = Column(String(255), nullable=False)
    environment_id = Column(String(255), nullable=False)
    status = Column(Enum(TestSuiteStatus), default=TestSuiteStatus.PENDING)

    # Test counts
    total_tests = Column(Integer, default=0)
    passed = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    skipped = Column(Integer, default=0)

    # Timing
    duration_ms = Column(Integer)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    metadata = Column(JSON, default=dict)

    # Relationships
    results = relationship("TestResult", back_populates="suite")

# Usage examples:
from datetime import datetime, timezone

suite = TestSuite(
    id="suite-20240115-001",
    external_id="github-run-456789",
    name="E2E Login Tests",
    framework_id="playwright-1.55.0",
    environment_id="chrome-ubuntu-ci",
    status=TestSuiteStatus.RUNNING,
    started_at=datetime.now(timezone.utc),
    metadata={
        "commit_sha": "abc123def456",
        "branch": "feature/login-improvements",
        "pr_number": 123,
        "repository": "myorg/myapp"
    }
)

# Update suite when completed
suite.status = TestSuiteStatus.COMPLETED
suite.completed_at = datetime.now(timezone.utc)
suite.total_tests = 25
suite.passed = 23
suite.failed = 2
suite.duration_ms = 120000

# Query examples:
async def get_recent_suites(db: AsyncSession, limit: int = 50):
    result = await db.execute(
        select(TestSuite)
        .order_by(TestSuite.started_at.desc())
        .limit(limit)
    )
    return result.scalars().all()

async def get_suite_statistics(db: AsyncSession, framework_id: str):
    result = await db.execute(
        select(
            func.count(TestSuite.id).label('total_suites'),
            func.avg(TestSuite.duration_ms).label('avg_duration'),
            func.sum(TestSuite.total_tests).label('total_tests')
        )
        .where(TestSuite.framework_id == framework_id)
    )
    return result.first()
```

### TestResult Model (`src/models/test_result.py`)

Individual test execution results.

```python
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Enum, ARRAY
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
from .base import BaseModel

class TestResultStatus(PyEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    FLAKY = "flaky"

class TestResult(BaseModel):
    __tablename__ = 'test_results'

    id = Column(String(255), primary_key=True)
    suite_id = Column(String(255), nullable=False)
    external_id = Column(String(255))             # Test ID from framework
    full_title = Column(Text, nullable=False)     # Complete test title/path
    status = Column(Enum(TestResultStatus), nullable=False)

    # Timing and execution details
    duration_ms = Column(Integer)
    retry_count = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    # Error information
    error_message = Column(Text)
    stack_trace = Column(Text)

    # Categorization
    tags = Column(ARRAY(String), default=list)   # e.g., ["auth", "smoke", "critical"]

    metadata = Column(JSON, default=dict)

    # Relationships
    suite = relationship("TestSuite", back_populates="results")
    artifacts = relationship("TestArtifact", back_populates="result")

# Usage examples:
result = TestResult(
    id="result-login-001",
    suite_id="suite-20240115-001",
    external_id="test-login-valid-credentials",
    full_title="Login Flow › Valid Credentials › should login successfully with correct username and password",
    status=TestResultStatus.PASSED,
    duration_ms=1500,
    retry_count=0,
    tags=["auth", "smoke", "critical"],
    started_at=datetime.now(timezone.utc),
    completed_at=datetime.now(timezone.utc),
    metadata={
        "test_file": "tests/auth/login.spec.ts",
        "test_location": "login.spec.ts:25:5",
        "browser_version": "118.0.5993.70"
    }
)

# Failed test example
failed_result = TestResult(
    id="result-checkout-002",
    suite_id="suite-20240115-001",
    external_id="test-checkout-payment-failure",
    full_title="Checkout Flow › Payment › should handle payment failure gracefully",
    status=TestResultStatus.FAILED,
    duration_ms=3200,
    retry_count=2,
    error_message="Payment gateway returned error: Insufficient funds",
    stack_trace="Error: Payment gateway returned error\n    at checkout.spec.ts:45:12",
    tags=["checkout", "payment", "regression"],
    metadata={
        "payment_method": "credit_card",
        "amount": "$99.99",
        "error_code": "INSUFFICIENT_FUNDS"
    }
)

# Query examples:
async def get_failed_tests(db: AsyncSession, suite_id: str):
    result = await db.execute(
        select(TestResult)
        .where(TestResult.suite_id == suite_id)
        .where(TestResult.status == TestResultStatus.FAILED)
    )
    return result.scalars().all()

async def get_flaky_tests(db: AsyncSession, days: int = 7):
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(TestResult.external_id, func.count().label('failure_count'))
        .where(TestResult.status == TestResultStatus.FAILED)
        .where(TestResult.started_at >= cutoff_date)
        .group_by(TestResult.external_id)
        .having(func.count() >= 3)
    )
    return result.all()
```

### TestArtifact Model (`src/models/test_artifact.py`)

Files generated during test execution.

```python
from sqlalchemy import Column, String, Integer, Text, JSON
from sqlalchemy.orm import relationship
from .base import BaseModel

class TestArtifact(BaseModel):
    __tablename__ = 'test_artifacts'

    id = Column(String(255), primary_key=True)
    result_id = Column(String(255), nullable=False)
    name = Column(String(500), nullable=False)    # Original filename
    type = Column(String(50), nullable=False)     # screenshot, video, trace, etc.
    content_type = Column(String(100))            # MIME type
    size = Column(Integer)                        # File size in bytes
    storage_path = Column(Text, nullable=False)   # Path in storage system
    metadata = Column(JSON, default=dict)

    # Relationships
    result = relationship("TestResult", back_populates="artifacts")

# Usage examples:
artifact = TestArtifact(
    id="artifact-screenshot-001",
    result_id="result-login-001",
    name="login-page-screenshot.png",
    type="screenshot",
    content_type="image/png",
    size=156789,
    storage_path="artifacts/2024/01/15/login-page-screenshot.png",
    metadata={
        "width": 1280,
        "height": 720,
        "capture_time": "2024-01-15T10:01:01Z",
        "page_title": "Login - My App"
    }
)

# Video artifact example
video_artifact = TestArtifact(
    id="artifact-video-002",
    result_id="result-checkout-002",
    name="checkout-flow-recording.webm",
    type="video",
    content_type="video/webm",
    size=5467890,
    storage_path="artifacts/2024/01/15/checkout-flow-recording.webm",
    metadata={
        "duration_ms": 15000,
        "fps": 30,
        "resolution": "1920x1080",
        "codec": "vp9"
    }
)

# Query examples:
async def get_artifacts_by_type(db: AsyncSession, result_id: str, artifact_type: str):
    result = await db.execute(
        select(TestArtifact)
        .where(TestArtifact.result_id == result_id)
        .where(TestArtifact.type == artifact_type)
    )
    return result.scalars().all()

async def get_storage_usage_stats(db: AsyncSession):
    result = await db.execute(
        select(
            TestArtifact.type,
            func.count().label('count'),
            func.sum(TestArtifact.size).label('total_size')
        )
        .group_by(TestArtifact.type)
    )
    return result.all()
```

## Service Libraries

### Authentication Library (`src/services/auth.py`)

Handles JWT tokens, GitHub OAuth, and authorization.

```python
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from pydantic import BaseModel
import httpx

class TokenClaims(BaseModel):
    sub: str                    # Subject (user ID or automation name)
    iat: int                    # Issued at
    exp: int                    # Expires at
    type: str                   # "user" or "automation"
    permissions: List[str]      # ["read", "write", "admin"]
    scope: Optional[str] = None # Additional scope information

class TokenManager:
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm

    async def create_user_token(
        self,
        user_id: str,
        permissions: List[str],
        expiration_hours: int = 24
    ) -> str:
        """Create JWT token for authenticated user."""
        now = datetime.now(timezone.utc)
        claims = TokenClaims(
            sub=user_id,
            iat=int(now.timestamp()),
            exp=int((now + timedelta(hours=expiration_hours)).timestamp()),
            type="user",
            permissions=permissions
        )

        return jwt.encode(
            claims.dict(),
            self.secret_key,
            algorithm=self.algorithm
        )

    async def create_automation_token(
        self,
        automation_name: str,
        permissions: List[str],
        expiration_days: int = 365
    ) -> str:
        """Create long-lived token for CI/CD automation."""
        now = datetime.now(timezone.utc)
        claims = TokenClaims(
            sub=automation_name,
            iat=int(now.timestamp()),
            exp=int((now + timedelta(days=expiration_days)).timestamp()),
            type="automation",
            permissions=permissions,
            scope="ci_cd"
        )

        return jwt.encode(
            claims.dict(),
            self.secret_key,
            algorithm=self.algorithm
        )

    async def validate_token(self, token: str) -> Optional[TokenClaims]:
        """Validate JWT token and return claims."""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            return TokenClaims(**payload)
        except JWTError:
            return None

    async def refresh_token(self, token: str) -> Optional[str]:
        """Refresh a valid token with new expiration."""
        claims = await self.validate_token(token)
        if not claims:
            return None

        # Only refresh if token expires within 7 days
        exp_datetime = datetime.fromtimestamp(claims.exp, timezone.utc)
        if exp_datetime - datetime.now(timezone.utc) > timedelta(days=7):
            return None

        if claims.type == "user":
            return await self.create_user_token(
                claims.sub,
                claims.permissions,
                expiration_hours=24
            )
        else:
            return await self.create_automation_token(
                claims.sub,
                claims.permissions,
                expiration_days=365
            )

class GitHubOAuth:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.auth_url = "https://github.com/login/oauth/authorize"
        self.token_url = "https://github.com/login/oauth/access_token"
        self.user_url = "https://api.github.com/user"

    def get_auth_url(self, state: str) -> str:
        """Generate GitHub OAuth authorization URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "user:email",
            "state": state
        }
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.auth_url}?{query_string}"

    async def exchange_code(self, code: str, state: str) -> Optional[Dict[str, Any]]:
        """Exchange authorization code for access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                    "state": state
                },
                headers={"Accept": "application/json"}
            )

            if response.status_code != 200:
                return None

            return response.json()

    async def get_user_info(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Get user information from GitHub API."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.user_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github.v3+json"
                }
            )

            if response.status_code != 200:
                return None

            return response.json()

# Usage examples:
import os

# Initialize token manager
token_manager = TokenManager(
    secret_key=os.getenv("JWT_SECRET_KEY"),
    algorithm="HS256"
)

# Create user token
user_token = await token_manager.create_user_token(
    user_id="github_user_123",
    permissions=["read", "write"],
    expiration_hours=24
)

# Create automation token
automation_token = await token_manager.create_automation_token(
    automation_name="GitHub Actions - My Repo",
    permissions=["write"],
    expiration_days=90
)

# Validate token
claims = await token_manager.validate_token(token)
if claims and "write" in claims.permissions:
    # User has write permission
    pass

# GitHub OAuth flow
github = GitHubOAuth(
    client_id=os.getenv("GITHUB_CLIENT_ID"),
    client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
    redirect_uri="https://api.example.com/auth/github/callback"
)

# Step 1: Redirect user to GitHub
auth_url = github.get_auth_url(state="random_state_string")

# Step 2: Handle callback
token_data = await github.exchange_code(code="auth_code", state="random_state_string")
if token_data:
    user_info = await github.get_user_info(token_data["access_token"])
    # Create user session with user_info
```

### Database Library (`src/services/database.py`)

Database connection and session management.

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import QueuePool
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import os

class DatabaseManager:
    def __init__(self, database_url: str, **kwargs):
        self.engine = create_async_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=kwargs.get('pool_size', 20),
            max_overflow=kwargs.get('max_overflow', 30),
            pool_timeout=kwargs.get('pool_timeout', 30),
            pool_recycle=kwargs.get('pool_recycle', 3600),
            echo=kwargs.get('echo', False)
        )

        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session with automatic cleanup."""
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            async with self.get_session() as session:
                result = await session.execute("SELECT 1")
                return result.scalar() == 1
        except Exception:
            return False

    async def get_connection_stats(self) -> dict:
        """Get connection pool statistics."""
        pool = self.engine.pool
        return {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalidated": pool.invalidated()
        }

    async def close(self):
        """Close database connections."""
        await self.engine.dispose()

# Global database manager instance
db_manager: DatabaseManager = None

async def init_database(database_url: str = None, **kwargs):
    """Initialize database connection."""
    global db_manager
    if not database_url:
        database_url = os.getenv("DATABASE_URL")

    db_manager = DatabaseManager(database_url, **kwargs)

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI to get database session."""
    if not db_manager:
        raise RuntimeError("Database not initialized. Call init_database() first.")

    async with db_manager.get_session() as session:
        yield session

async def get_database_manager() -> DatabaseManager:
    """Get the global database manager."""
    if not db_manager:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return db_manager

# Usage examples:
from fastapi import Depends

# Initialize database (typically in startup event)
await init_database(
    database_url="postgresql+asyncpg://user:pass@localhost/testresults",
    pool_size=20,
    max_overflow=30,
    echo=False
)

# Use in FastAPI endpoint
@app.get("/frameworks")
async def get_frameworks(db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(select(TestFramework))
    return result.scalars().all()

# Use in standalone function
async def create_test_suite(suite_data: dict):
    async with db_manager.get_session() as db:
        suite = TestSuite(**suite_data)
        db.add(suite)
        await db.flush()
        return suite

# Health check
async def check_database_health():
    return await db_manager.health_check()

# Connection monitoring
async def get_db_stats():
    return await db_manager.get_connection_stats()
```

### Storage Library (`src/services/storage.py`)

S3-compatible file storage operations.

```python
import asyncio
from typing import Optional, List, Dict, Any, AsyncIterator
from datetime import datetime
import aioboto3
from minio import Minio
from minio.error import S3Error
import aiofiles
import os
from urllib.parse import urlparse

class StorageConfig:
    def __init__(
        self,
        storage_type: str = "s3",  # "s3" or "minio"
        endpoint: str = None,
        access_key: str = None,
        secret_key: str = None,
        bucket: str = None,
        region: str = "us-east-1",
        secure: bool = True
    ):
        self.storage_type = storage_type
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket = bucket
        self.region = region
        self.secure = secure

class FileInfo:
    def __init__(
        self,
        name: str,
        size: int,
        content_type: str,
        last_modified: datetime,
        etag: str,
        metadata: Dict[str, Any] = None
    ):
        self.name = name
        self.size = size
        self.content_type = content_type
        self.last_modified = last_modified
        self.etag = etag
        self.metadata = metadata or {}

class StorageClient:
    def __init__(self, config: StorageConfig):
        self.config = config
        self._s3_client = None
        self._minio_client = None

    async def __aenter__(self):
        if self.config.storage_type == "s3":
            session = aioboto3.Session()
            self._s3_client = await session.client(
                's3',
                endpoint_url=self.config.endpoint,
                aws_access_key_id=self.config.access_key,
                aws_secret_access_key=self.config.secret_key,
                region_name=self.config.region
            ).__aenter__()
        else:
            self._minio_client = Minio(
                endpoint=self.config.endpoint.replace("http://", "").replace("https://", ""),
                access_key=self.config.access_key,
                secret_key=self.config.secret_key,
                secure=self.config.secure
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._s3_client:
            await self._s3_client.__aexit__(exc_type, exc_val, exc_tb)

    async def upload_file(
        self,
        local_path: str,
        storage_path: str,
        content_type: str = None,
        metadata: Dict[str, str] = None
    ) -> bool:
        """Upload file to storage."""
        try:
            if self.config.storage_type == "s3":
                extra_args = {}
                if content_type:
                    extra_args['ContentType'] = content_type
                if metadata:
                    extra_args['Metadata'] = metadata

                await self._s3_client.upload_file(
                    local_path,
                    self.config.bucket,
                    storage_path,
                    ExtraArgs=extra_args
                )
            else:
                self._minio_client.fput_object(
                    self.config.bucket,
                    storage_path,
                    local_path,
                    content_type=content_type,
                    metadata=metadata
                )
            return True
        except Exception as e:
            print(f"Upload failed: {e}")
            return False

    async def upload_bytes(
        self,
        data: bytes,
        storage_path: str,
        content_type: str = None,
        metadata: Dict[str, str] = None
    ) -> bool:
        """Upload bytes to storage."""
        try:
            if self.config.storage_type == "s3":
                extra_args = {}
                if content_type:
                    extra_args['ContentType'] = content_type
                if metadata:
                    extra_args['Metadata'] = metadata

                await self._s3_client.put_object(
                    Bucket=self.config.bucket,
                    Key=storage_path,
                    Body=data,
                    **extra_args
                )
            else:
                from io import BytesIO
                self._minio_client.put_object(
                    self.config.bucket,
                    storage_path,
                    BytesIO(data),
                    length=len(data),
                    content_type=content_type,
                    metadata=metadata
                )
            return True
        except Exception as e:
            print(f"Upload failed: {e}")
            return False

    async def download_file(self, storage_path: str, local_path: str) -> bool:
        """Download file from storage."""
        try:
            if self.config.storage_type == "s3":
                await self._s3_client.download_file(
                    self.config.bucket,
                    storage_path,
                    local_path
                )
            else:
                self._minio_client.fget_object(
                    self.config.bucket,
                    storage_path,
                    local_path
                )
            return True
        except Exception as e:
            print(f"Download failed: {e}")
            return False

    async def get_file_bytes(self, storage_path: str) -> Optional[bytes]:
        """Get file content as bytes."""
        try:
            if self.config.storage_type == "s3":
                response = await self._s3_client.get_object(
                    Bucket=self.config.bucket,
                    Key=storage_path
                )
                return await response['Body'].read()
            else:
                response = self._minio_client.get_object(
                    self.config.bucket,
                    storage_path
                )
                return response.read()
        except Exception as e:
            print(f"Get file failed: {e}")
            return None

    async def list_files(self, prefix: str = "") -> List[FileInfo]:
        """List files in storage."""
        files = []
        try:
            if self.config.storage_type == "s3":
                paginator = self._s3_client.get_paginator('list_objects_v2')
                async for page in paginator.paginate(
                    Bucket=self.config.bucket,
                    Prefix=prefix
                ):
                    if 'Contents' in page:
                        for obj in page['Contents']:
                            files.append(FileInfo(
                                name=obj['Key'],
                                size=obj['Size'],
                                content_type=obj.get('ContentType', 'application/octet-stream'),
                                last_modified=obj['LastModified'],
                                etag=obj['ETag'].strip('"')
                            ))
            else:
                objects = self._minio_client.list_objects(
                    self.config.bucket,
                    prefix=prefix,
                    recursive=True
                )
                for obj in objects:
                    files.append(FileInfo(
                        name=obj.object_name,
                        size=obj.size,
                        content_type=obj.content_type or 'application/octet-stream',
                        last_modified=obj.last_modified,
                        etag=obj.etag
                    ))
        except Exception as e:
            print(f"List files failed: {e}")

        return files

    async def delete_file(self, storage_path: str) -> bool:
        """Delete file from storage."""
        try:
            if self.config.storage_type == "s3":
                await self._s3_client.delete_object(
                    Bucket=self.config.bucket,
                    Key=storage_path
                )
            else:
                self._minio_client.remove_object(
                    self.config.bucket,
                    storage_path
                )
            return True
        except Exception as e:
            print(f"Delete failed: {e}")
            return False

    async def file_exists(self, storage_path: str) -> bool:
        """Check if file exists in storage."""
        try:
            if self.config.storage_type == "s3":
                await self._s3_client.head_object(
                    Bucket=self.config.bucket,
                    Key=storage_path
                )
            else:
                self._minio_client.stat_object(
                    self.config.bucket,
                    storage_path
                )
            return True
        except Exception:
            return False

    async def generate_presigned_url(
        self,
        storage_path: str,
        expiration: int = 3600,
        method: str = "GET"
    ) -> Optional[str]:
        """Generate presigned URL for direct access."""
        try:
            if self.config.storage_type == "s3":
                return await self._s3_client.generate_presigned_url(
                    method.lower() + '_object',
                    Params={
                        'Bucket': self.config.bucket,
                        'Key': storage_path
                    },
                    ExpiresIn=expiration
                )
            else:
                from datetime import timedelta
                return self._minio_client.presigned_get_object(
                    self.config.bucket,
                    storage_path,
                    expires=timedelta(seconds=expiration)
                )
        except Exception as e:
            print(f"Presigned URL generation failed: {e}")
            return None

# Global storage client
storage_client: StorageClient = None

async def init_storage(config: StorageConfig = None):
    """Initialize storage client."""
    global storage_client
    if not config:
        config = StorageConfig(
            storage_type=os.getenv("STORAGE_TYPE", "s3"),
            endpoint=os.getenv("STORAGE_ENDPOINT"),
            access_key=os.getenv("STORAGE_ACCESS_KEY"),
            secret_key=os.getenv("STORAGE_SECRET_KEY"),
            bucket=os.getenv("STORAGE_BUCKET"),
            region=os.getenv("STORAGE_REGION", "us-east-1"),
            secure=os.getenv("STORAGE_SECURE", "true").lower() == "true"
        )

    storage_client = StorageClient(config)

def get_storage_client() -> StorageClient:
    """Get the global storage client."""
    if not storage_client:
        raise RuntimeError("Storage not initialized. Call init_storage() first.")
    return storage_client

# Usage examples:
# Initialize storage
await init_storage()

# Upload artifact
async def upload_test_artifact(result_id: str, file_path: str, artifact_type: str):
    client = get_storage_client()
    async with client:
        storage_path = f"artifacts/{datetime.now().year}/{datetime.now().month:02d}/{datetime.now().day:02d}/{result_id}_{os.path.basename(file_path)}"

        success = await client.upload_file(
            local_path=file_path,
            storage_path=storage_path,
            content_type="image/png" if artifact_type == "screenshot" else None,
            metadata={
                "result_id": result_id,
                "artifact_type": artifact_type,
                "uploaded_at": datetime.now().isoformat()
            }
        )

        return storage_path if success else None

# Download artifact
async def download_test_artifact(storage_path: str, local_path: str):
    client = get_storage_client()
    async with client:
        return await client.download_file(storage_path, local_path)

# Generate download URL
async def get_artifact_download_url(storage_path: str):
    client = get_storage_client()
    async with client:
        return await client.generate_presigned_url(storage_path, expiration=3600)
```

This comprehensive library documentation provides detailed information about all the core libraries in the Test Results Management API, including practical usage examples and real-world integration patterns. Each library is designed to be used independently or as part of the larger system, following the library-first architecture principle.