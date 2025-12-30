import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


class TestMultiTenancy:
    """Tests for multi-user isolation and authentication."""

    @pytest.mark.asyncio
    async def test_users_can_have_same_url(
        self, authenticated_client, sample_bookmark_data
    ):
        """Two different users can bookmark the same URL."""
        client1 = await authenticated_client("user-1")
        client2 = await authenticated_client("user-2")

        # User 1 creates bookmark
        response1 = await client1.post("/bookmarks", json=sample_bookmark_data)
        assert response1.status_code == 201
        data1 = response1.json()
        assert data1["user_id"] == "user-1"

        # User 2 creates same URL - should succeed
        response2 = await client2.post("/bookmarks", json=sample_bookmark_data)
        assert response2.status_code == 201
        data2 = response2.json()
        assert data2["user_id"] == "user-2"

        # Verify different bookmark IDs but same URL
        assert data1["id"] != data2["id"]
        assert str(data1["url"]) == str(data2["url"])

        await client1.aclose()
        await client2.aclose()

    @pytest.mark.asyncio
    async def test_user_cannot_access_other_users_bookmarks(
        self, authenticated_client, sample_bookmark_data
    ):
        """Users cannot access bookmarks belonging to other users."""
        client1 = await authenticated_client("user-1")
        client2 = await authenticated_client("user-2")

        # User 1 creates bookmark
        response = await client1.post("/bookmarks", json=sample_bookmark_data)
        bookmark_id = response.json()["id"]

        # User 2 tries to access User 1's bookmark
        response = await client2.get(f"/bookmarks/{bookmark_id}")
        assert response.status_code == 404  # Not 403 - prevents ID leakage

        await client1.aclose()
        await client2.aclose()

    @pytest.mark.asyncio
    async def test_user_cannot_update_other_users_bookmarks(
        self, authenticated_client, sample_bookmark_data
    ):
        """Users cannot update bookmarks belonging to other users."""
        client1 = await authenticated_client("user-1")
        client2 = await authenticated_client("user-2")

        # User 1 creates bookmark
        response = await client1.post("/bookmarks", json=sample_bookmark_data)
        bookmark_id = response.json()["id"]

        # User 2 tries to update User 1's bookmark
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
    async def test_user_cannot_delete_other_users_bookmarks(
        self, authenticated_client, sample_bookmark_data
    ):
        """Users cannot delete bookmarks belonging to other users."""
        client1 = await authenticated_client("user-1")
        client2 = await authenticated_client("user-2")

        # User 1 creates bookmark
        response = await client1.post("/bookmarks", json=sample_bookmark_data)
        bookmark_id = response.json()["id"]

        # User 2 tries to delete User 1's bookmark
        response = await client2.delete(f"/bookmarks/{bookmark_id}")
        assert response.status_code == 404

        # Verify bookmark still exists for User 1
        response = await client1.get(f"/bookmarks/{bookmark_id}")
        assert response.status_code == 200

        await client1.aclose()
        await client2.aclose()

    @pytest.mark.asyncio
    async def test_list_only_returns_users_bookmarks(
        self, authenticated_client
    ):
        """List endpoint only returns bookmarks for the authenticated user."""
        client1 = await authenticated_client("user-1")
        client2 = await authenticated_client("user-2")

        # User 1 creates 2 bookmarks
        await client1.post("/bookmarks", json={
            "url": "https://example1.com",
            "title": "User 1 Bookmark 1"
        })
        await client1.post("/bookmarks", json={
            "url": "https://example2.com",
            "title": "User 1 Bookmark 2"
        })

        # User 2 creates 1 bookmark
        await client2.post("/bookmarks", json={
            "url": "https://example3.com",
            "title": "User 2 Bookmark"
        })

        # User 1 lists bookmarks - should see only 2
        response = await client1.get("/bookmarks")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        # Verify all bookmarks belong to user-1
        for item in data["items"]:
            assert item["user_id"] == "user-1"

        # User 2 lists bookmarks - should see only 1
        response = await client2.get("/bookmarks")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["user_id"] == "user-2"

        await client1.aclose()
        await client2.aclose()

    @pytest.mark.asyncio
    async def test_missing_user_header_returns_401(self, test_db):
        """Request without X-User-ID header returns 401."""
        from app.database import get_db

        async def override_get_db():
            yield test_db

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get("/bookmarks")
            assert response.status_code == 401
            assert "X-User-ID" in response.json()["detail"]

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_empty_user_header_returns_401(self, test_db):
        """Request with empty X-User-ID header returns 401."""
        from app.database import get_db

        async def override_get_db():
            yield test_db

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-User-ID": ""}
        ) as client:
            response = await client.get("/bookmarks")
            assert response.status_code == 401
            assert "empty" in response.json()["detail"].lower()

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_invalid_user_id_format_returns_401(self, test_db):
        """Request with invalid user ID format returns 401."""
        from app.database import get_db

        async def override_get_db():
            yield test_db

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-User-ID": "user@invalid!chars"}
        ) as client:
            response = await client.get("/bookmarks")
            assert response.status_code == 401
            assert "invalid characters" in response.json()["detail"].lower()

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_duplicate_url_per_user_returns_409(
        self, authenticated_client, sample_bookmark_data
    ):
        """Same user cannot create duplicate URLs (409), but different users can."""
        client = await authenticated_client("user-1")

        # Create first bookmark
        response1 = await client.post("/bookmarks", json=sample_bookmark_data)
        assert response1.status_code == 201

        # Try to create duplicate - should fail
        response2 = await client.post("/bookmarks", json=sample_bookmark_data)
        assert response2.status_code == 409
        assert "already exists" in response2.json()["detail"].lower()

        await client.aclose()

    @pytest.mark.asyncio
    async def test_user_id_too_long_returns_401(self, test_db):
        """Request with user ID exceeding 255 characters returns 401."""
        from app.database import get_db

        async def override_get_db():
            yield test_db

        app.dependency_overrides[get_db] = override_get_db

        long_user_id = "a" * 256
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-User-ID": long_user_id}
        ) as client:
            response = await client.get("/bookmarks")
            assert response.status_code == 401
            assert "maximum length" in response.json()["detail"].lower()

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_user_id_persists_in_response(
        self, authenticated_client, sample_bookmark_data
    ):
        """User ID is correctly stored and returned in responses."""
        client = await authenticated_client("my-test-user")

        # Create bookmark
        response = await client.post("/bookmarks", json=sample_bookmark_data)
        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == "my-test-user"

        # Get bookmark
        bookmark_id = data["id"]
        response = await client.get(f"/bookmarks/{bookmark_id}")
        assert response.status_code == 200
        assert response.json()["user_id"] == "my-test-user"

        # List bookmarks
        response = await client.get("/bookmarks")
        assert response.status_code == 200
        assert response.json()["items"][0]["user_id"] == "my-test-user"

        await client.aclose()
