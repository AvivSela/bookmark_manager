import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


class TestMultiTenancy:
    """Tests for multi-tenant isolation and authentication."""

    @pytest.mark.asyncio
    async def test_tenants_can_have_same_url(
        self, authenticated_client, sample_bookmark_data
    ):
        """Two different tenants can bookmark the same URL."""
        client1 = await authenticated_client("550e8400-e29b-41d4-a716-446655440001")
        client2 = await authenticated_client("550e8400-e29b-41d4-a716-446655440002")

        # Tenant 1 creates bookmark
        response1 = await client1.post("/bookmarks", json=sample_bookmark_data)
        assert response1.status_code == 201
        data1 = response1.json()
        assert data1["tenant_id"] == "550e8400-e29b-41d4-a716-446655440001"

        # Tenant 2 creates same URL - should succeed
        response2 = await client2.post("/bookmarks", json=sample_bookmark_data)
        assert response2.status_code == 201
        data2 = response2.json()
        assert data2["tenant_id"] == "550e8400-e29b-41d4-a716-446655440002"

        # Verify different bookmark IDs but same URL
        assert data1["id"] != data2["id"]
        assert str(data1["url"]) == str(data2["url"])

        await client1.aclose()
        await client2.aclose()

    @pytest.mark.asyncio
    async def test_tenant_cannot_access_other_tenants_bookmarks(
        self, authenticated_client, sample_bookmark_data
    ):
        """Tenants cannot access bookmarks belonging to other tenants."""
        client1 = await authenticated_client("550e8400-e29b-41d4-a716-446655440001")
        client2 = await authenticated_client("550e8400-e29b-41d4-a716-446655440002")

        # Tenant 1 creates bookmark
        response = await client1.post("/bookmarks", json=sample_bookmark_data)
        bookmark_id = response.json()["id"]

        # Tenant 2 tries to access Tenant 1's bookmark
        response = await client2.get(f"/bookmarks/{bookmark_id}")
        assert response.status_code == 404  # Not 403 - prevents ID leakage

        await client1.aclose()
        await client2.aclose()

    @pytest.mark.asyncio
    async def test_tenant_cannot_update_other_tenants_bookmarks(
        self, authenticated_client, sample_bookmark_data
    ):
        """Tenants cannot update bookmarks belonging to other tenants."""
        client1 = await authenticated_client("550e8400-e29b-41d4-a716-446655440001")
        client2 = await authenticated_client("550e8400-e29b-41d4-a716-446655440002")

        # Tenant 1 creates bookmark
        response = await client1.post("/bookmarks", json=sample_bookmark_data)
        bookmark_id = response.json()["id"]

        # Tenant 2 tries to update Tenant 1's bookmark
        update_data = {"title": "Hacked Title"}
        response = await client2.put(f"/bookmarks/{bookmark_id}", json=update_data)
        assert response.status_code == 404

        # Verify bookmark was not modified
        response = await client1.get(f"/bookmarks/{bookmark_id}")
        assert response.status_code == 200
        assert response.json()["title"] == "Example Bookmark"

        await client1.aclose()
        await client2.aclose()

    @pytest.mark.asyncio
    async def test_tenant_cannot_delete_other_tenants_bookmarks(
        self, authenticated_client, sample_bookmark_data
    ):
        """Tenants cannot delete bookmarks belonging to other tenants."""
        client1 = await authenticated_client("550e8400-e29b-41d4-a716-446655440001")
        client2 = await authenticated_client("550e8400-e29b-41d4-a716-446655440002")

        # Tenant 1 creates bookmark
        response = await client1.post("/bookmarks", json=sample_bookmark_data)
        bookmark_id = response.json()["id"]

        # Tenant 2 tries to delete Tenant 1's bookmark
        response = await client2.delete(f"/bookmarks/{bookmark_id}")
        assert response.status_code == 404

        # Verify bookmark still exists for Tenant 1
        response = await client1.get(f"/bookmarks/{bookmark_id}")
        assert response.status_code == 200

        await client1.aclose()
        await client2.aclose()

    @pytest.mark.asyncio
    async def test_list_only_returns_tenants_bookmarks(self, authenticated_client):
        """List endpoint only returns bookmarks for the authenticated tenant."""
        client1 = await authenticated_client("550e8400-e29b-41d4-a716-446655440001")
        client2 = await authenticated_client("550e8400-e29b-41d4-a716-446655440002")

        # Tenant 1 creates 2 bookmarks
        await client1.post(
            "/bookmarks",
            json={"url": "https://example1.com", "title": "Tenant 1 Bookmark 1"},
        )
        await client1.post(
            "/bookmarks",
            json={"url": "https://example2.com", "title": "Tenant 1 Bookmark 2"},
        )

        # Tenant 2 creates 1 bookmark
        await client2.post(
            "/bookmarks",
            json={"url": "https://example3.com", "title": "Tenant 2 Bookmark"},
        )

        # Tenant 1 lists bookmarks - should see only 2
        response = await client1.get("/bookmarks")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        # Verify all bookmarks belong to tenant-1
        for item in data["items"]:
            assert item["tenant_id"] == "550e8400-e29b-41d4-a716-446655440001"

        # Tenant 2 lists bookmarks - should see only 1
        response = await client2.get("/bookmarks")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["tenant_id"] == "550e8400-e29b-41d4-a716-446655440002"

        await client1.aclose()
        await client2.aclose()

    @pytest.mark.asyncio
    async def test_missing_tenant_header_returns_401(self, test_db):
        """Request without X-Tenant-ID header returns 401."""
        from app.database import get_db

        async def override_get_db():
            yield test_db

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/bookmarks")
            assert response.status_code == 401
            assert "X-Tenant-ID" in response.json()["detail"]

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_empty_tenant_header_returns_401(self, test_db):
        """Request with empty X-Tenant-ID header returns 401."""
        from app.database import get_db

        async def override_get_db():
            yield test_db

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Tenant-ID": ""},
        ) as client:
            response = await client.get("/bookmarks")
            assert response.status_code == 401
            assert "empty" in response.json()["detail"].lower()

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_invalid_tenant_id_format_returns_401(self, test_db):
        """Request with invalid tenant ID format returns 401."""
        from app.database import get_db

        async def override_get_db():
            yield test_db

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Tenant-ID": "tenant@invalid!chars"},
        ) as client:
            response = await client.get("/bookmarks")
            assert response.status_code == 401
            assert "uuid" in response.json()["detail"].lower()

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_duplicate_url_per_tenant_returns_409(
        self, authenticated_client, sample_bookmark_data
    ):
        """Same tenant cannot create duplicate URLs (409), but different tenants can."""
        client = await authenticated_client("550e8400-e29b-41d4-a716-446655440001")

        # Create first bookmark
        response1 = await client.post("/bookmarks", json=sample_bookmark_data)
        assert response1.status_code == 201

        # Try to create duplicate - should fail
        response2 = await client.post("/bookmarks", json=sample_bookmark_data)
        assert response2.status_code == 409
        assert "already exists" in response2.json()["detail"].lower()

        await client.aclose()

    @pytest.mark.asyncio
    async def test_tenant_id_too_long_returns_401(self, test_db):
        """Request with tenant ID exceeding 255 characters returns 401."""
        from app.database import get_db

        async def override_get_db():
            yield test_db

        app.dependency_overrides[get_db] = override_get_db

        long_tenant_id = "a" * 256
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Tenant-ID": long_tenant_id},
        ) as client:
            response = await client.get("/bookmarks")
            assert response.status_code == 401
            assert "maximum length" in response.json()["detail"].lower()

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_tenant_id_persists_in_response(
        self, authenticated_client, sample_bookmark_data
    ):
        """Tenant ID is correctly stored and returned in responses."""
        client = await authenticated_client("550e8400-e29b-41d4-a716-446655440003")

        # Create bookmark
        response = await client.post("/bookmarks", json=sample_bookmark_data)
        assert response.status_code == 201
        data = response.json()
        assert data["tenant_id"] == "550e8400-e29b-41d4-a716-446655440003"

        # Get bookmark
        bookmark_id = data["id"]
        response = await client.get(f"/bookmarks/{bookmark_id}")
        assert response.status_code == 200
        assert response.json()["tenant_id"] == "550e8400-e29b-41d4-a716-446655440003"

        # List bookmarks
        response = await client.get("/bookmarks")
        assert response.status_code == 200
        assert (
            response.json()["items"][0]["tenant_id"]
            == "550e8400-e29b-41d4-a716-446655440003"
        )

        await client.aclose()
