"""Shared fixtures for contract tests."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from src.lib.auth import TokenClaims, TokenScope, TokenType
from src.lib.database import close_database, init_database
from src.lib.middleware import AuthenticatedUser, UserRole, get_current_context
from src.lib.storage import close_storage, init_storage
from src.main import app

UTC = ZoneInfo("UTC")


@pytest.fixture(scope="function")
async def setup_services():
    """Initialize all services for each test function."""
    await init_database()
    await init_storage()

    # Clean database tables for fresh test data
    from src.lib.database import get_session

    async with get_session() as session:
        # Delete data in dependency order (children first, then parents)
        await session.execute(text("DELETE FROM test_artifacts"))
        await session.execute(text("DELETE FROM test_results"))
        await session.execute(text("DELETE FROM test_suites"))
        await session.execute(text("DELETE FROM test_environments"))
        await session.execute(text("DELETE FROM test_frameworks"))
        await session.commit()

    yield
    await close_storage()
    await close_database()


@pytest.fixture
async def client(setup_services):
    """Create test client with authentication."""

    # Mock authentication for contract tests
    def mock_auth():
        claims = TokenClaims(
            sub="test:user:contract",
            exp=datetime.now(UTC) + timedelta(hours=1),
            scope=TokenScope.USER,
            token_type=TokenType.ACCESS,
            username="contract_user",
            email="contract@example.com",
            role=UserRole.ADMIN,
        )
        return AuthenticatedUser(
            user_id="test:user:contract",
            username="contract_user",
            email="contract@example.com",
            role=UserRole.ADMIN,
            permissions=[
                "frameworks:read",
                "frameworks:write",
                "frameworks:delete",
                "environments:read",
                "environments:write",
                "environments:delete",
                "suites:read",
                "suites:write",
                "suites:delete",
                "results:read",
                "results:write",
                "results:delete",
                "artifacts:read",
                "artifacts:write",
                "artifacts:delete",
            ],
            token_claims=claims,
        )

    # Override authentication dependency
    app.dependency_overrides[get_current_context] = mock_auth

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    # Clean up dependency override
    app.dependency_overrides.clear()
