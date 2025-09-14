"""
Contract tests for Test Framework endpoints.
These tests validate API contracts defined in OpenAPI specification.
Tests must FAIL initially (RED phase) - no implementation exists yet.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from uuid import UUID, uuid4

# Apply pytest.mark.asyncio to all test methods in this module
pytestmark = pytest.mark.asyncio


async def setup_test_client():
    """Set up test client with authentication and database."""
    from src.main import app
    from src.lib.middleware import get_current_context, AuthenticatedUser, UserRole
    from src.lib.auth import TokenClaims, TokenScope, TokenType
    from src.lib.database import init_database
    from datetime import datetime, timedelta, timezone

    # Initialize database
    await init_database()

    # Mock authentication for contract tests
    def mock_auth():
        claims = TokenClaims(
            sub="test:user:123",
            exp=datetime.now(timezone.utc) + timedelta(hours=1),
            scope=TokenScope.USER,
            token_type=TokenType.ACCESS,
            username="testuser",
            email="test@example.com",
            role=UserRole.ADMIN
        )
        return AuthenticatedUser(
            user_id="test:user:123",
            username="testuser",
            email="test@example.com",
            role=UserRole.ADMIN,
            permissions=["frameworks:read", "frameworks:write", "frameworks:delete"],
            token_claims=claims
        )

    # Override authentication dependencies
    app.dependency_overrides[get_current_context] = mock_auth

    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    )


class TestFrameworksContract:
    """Contract tests for /api/v1/frameworks endpoints."""

    async def test_create_framework_success(self):
        """Test POST /api/v1/frameworks with valid data."""
        client = await setup_test_client()

        import random
        framework_data = {
            "name": "playwright",
            "version": f"1.55.{random.randint(1000, 9999)}",  # Make version unique but valid semver
            "metadata": {
                "actualWorkers": 1,
                "projects": ["setup", "ipad", "chrome", "firefox"]
            }
        }

        async with client:
            response = await client.post("/api/v1/frameworks", json=framework_data)

            assert response.status_code == 201
            data = response.json()
            assert "id" in data
            assert UUID(data["id"])  # Valid UUID
            assert data["name"] == "playwright"
            assert data["version"] == framework_data["version"]
            assert data["metadata"] == framework_data["metadata"]
            assert "created_at" in data
            assert "updated_at" in data

    async def test_create_framework_invalid_name(self, client: AsyncClient):
        """Test POST /api/v1/frameworks with invalid name."""
        framework_data = {
            "name": "PlayWright!",  # Invalid: uppercase and special chars
            "version": "1.55.0"
        }

        response = await client.post("/api/v1/frameworks", json=framework_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("name" in str(error) for error in data["detail"])

    async def test_create_framework_invalid_version(self, client: AsyncClient):
        """Test POST /api/v1/frameworks with invalid version."""
        framework_data = {
            "name": "playwright",
            "version": "not-a-version"  # Invalid semantic version
        }

        response = await client.post("/api/v1/frameworks", json=framework_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("version" in str(error) for error in data["detail"])

    async def test_create_framework_missing_required_fields(self, client: AsyncClient):
        """Test POST /api/v1/frameworks with missing required fields."""
        framework_data = {
            "metadata": {"some": "data"}
            # Missing name and version
        }

        response = await client.post("/api/v1/frameworks", json=framework_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        errors = data["detail"]
        assert any("name" in str(error) for error in errors)
        assert any("version" in str(error) for error in errors)

    async def test_get_frameworks_empty(self, client: AsyncClient):
        """Test GET /api/v1/frameworks with no frameworks."""
        response = await client.get("/api/v1/frameworks")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    async def test_get_frameworks_with_data(self, client: AsyncClient):
        """Test GET /api/v1/frameworks with existing frameworks."""
        # First create a framework
        framework_data = {
            "name": "cypress",
            "version": "7.2.0",
            "metadata": {"mocha": {"version": "7.2.0"}}
        }
        create_response = await client.post("/api/v1/frameworks", json=framework_data)
        assert create_response.status_code == 201

        # Then get all frameworks
        response = await client.get("/api/v1/frameworks")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        framework = data[0]
        assert "id" in framework
        assert framework["name"] == "cypress"
        assert framework["version"] == "7.2.0"

    async def test_get_framework_by_id_success(self, client: AsyncClient):
        """Test GET /api/v1/frameworks/{id} with valid ID."""
        # First create a framework
        framework_data = {
            "name": "playwright",
            "version": "1.55.0"
        }
        create_response = await client.post("/api/v1/frameworks", json=framework_data)
        assert create_response.status_code == 201
        created_framework = create_response.json()
        framework_id = created_framework["id"]

        # Then get it by ID
        response = await client.get(f"/api/v1/frameworks/{framework_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == framework_id
        assert data["name"] == "playwright"
        assert data["version"] == "1.55.0"

    async def test_get_framework_by_id_not_found(self, client: AsyncClient):
        """Test GET /api/v1/frameworks/{id} with non-existent ID."""
        non_existent_id = str(uuid4())

        response = await client.get(f"/api/v1/frameworks/{non_existent_id}")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    async def test_get_framework_by_id_invalid_uuid(self, client: AsyncClient):
        """Test GET /api/v1/frameworks/{id} with invalid UUID."""
        invalid_id = "not-a-uuid"

        response = await client.get(f"/api/v1/frameworks/{invalid_id}")

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    async def test_update_framework_success(self, client: AsyncClient):
        """Test PUT /api/v1/frameworks/{id} with valid data."""
        # First create a framework
        framework_data = {
            "name": "playwright",
            "version": "1.55.0"
        }
        create_response = await client.post("/api/v1/frameworks", json=framework_data)
        assert create_response.status_code == 201
        created_framework = create_response.json()
        framework_id = created_framework["id"]

        # Then update it
        updated_data = {
            "name": "playwright",
            "version": "1.56.0",  # Version update
            "metadata": {"updated": True}
        }

        response = await client.put(f"/api/v1/frameworks/{framework_id}", json=updated_data)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == framework_id
        assert data["version"] == "1.56.0"
        assert data["metadata"] == {"updated": True}

    async def test_update_framework_not_found(self, client: AsyncClient):
        """Test PUT /api/v1/frameworks/{id} with non-existent ID."""
        non_existent_id = str(uuid4())
        updated_data = {
            "name": "playwright",
            "version": "1.56.0"
        }

        response = await client.put(f"/api/v1/frameworks/{non_existent_id}", json=updated_data)

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    async def test_delete_framework_success(self, client: AsyncClient):
        """Test DELETE /api/v1/frameworks/{id} with valid ID."""
        # First create a framework
        framework_data = {
            "name": "playwright",
            "version": "1.55.0"
        }
        create_response = await client.post("/api/v1/frameworks", json=framework_data)
        assert create_response.status_code == 201
        created_framework = create_response.json()
        framework_id = created_framework["id"]

        # Then delete it
        response = await client.delete(f"/api/v1/frameworks/{framework_id}")

        assert response.status_code == 204
        assert response.content == b""

        # Verify it's gone
        get_response = await client.get(f"/api/v1/frameworks/{framework_id}")
        assert get_response.status_code == 404

    async def test_delete_framework_not_found(self, client: AsyncClient):
        """Test DELETE /api/v1/frameworks/{id} with non-existent ID."""
        non_existent_id = str(uuid4())

        response = await client.delete(f"/api/v1/frameworks/{non_existent_id}")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    async def test_create_duplicate_framework(self, client: AsyncClient):
        """Test POST /api/v1/frameworks with duplicate name/version."""
        framework_data = {
            "name": "playwright",
            "version": "1.55.0"
        }

        # Create first framework
        response1 = await client.post("/api/v1/frameworks", json=framework_data)
        assert response1.status_code == 201

        # Try to create duplicate
        response2 = await client.post("/api/v1/frameworks", json=framework_data)
        assert response2.status_code == 409  # Conflict
        data = response2.json()
        assert "detail" in data
        assert "already exists" in data["detail"].lower()

    async def test_framework_metadata_validation(self, client: AsyncClient):
        """Test framework creation with invalid JSON metadata."""
        framework_data = {
            "name": "playwright",
            "version": "1.55.0",
            "metadata": "invalid-json"  # Should be dict, not string
        }

        response = await client.post("/api/v1/frameworks", json=framework_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("metadata" in str(error) for error in data["detail"])