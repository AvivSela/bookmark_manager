import pytest
from httpx import AsyncClient
from uuid import uuid4
from datetime import datetime
import asyncio


class TestBookmarkCRUD:
    """Tests for CRUD operations on bookmarks."""

    @pytest.mark.asyncio
    async def test_create_bookmark_duplicate_url_returns_409_conflict(
        self, client: AsyncClient, sample_bookmark_data: dict
    ):
        """
        Test 1: Creating a bookmark with a URL that already exists returns HTTP 409.

        Critical for data integrity - URL uniqueness is the core business constraint.
        """
        # Create first bookmark
        response1 = await client.post("/bookmarks", json=sample_bookmark_data)
        assert response1.status_code == 201

        # Attempt to create second bookmark with same URL
        response2 = await client.post("/bookmarks", json=sample_bookmark_data)
        assert response2.status_code == 409
        assert "A bookmark with this URL already exists" in response2.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_bookmark_to_existing_url_returns_409_conflict(
        self, client: AsyncClient
    ):
        """
        Test 2: Updating a bookmark to an already-existing URL returns HTTP 409.

        Critical edge case - update operations must also respect URL uniqueness.
        """
        # Create bookmark A
        bookmark_a_data = {
            "url": "https://example.com",
            "title": "Bookmark A",
            "description": "First bookmark"
        }
        response_a = await client.post("/bookmarks", json=bookmark_a_data)
        assert response_a.status_code == 201

        # Create bookmark B
        bookmark_b_data = {
            "url": "https://test.com",
            "title": "Bookmark B",
            "description": "Second bookmark"
        }
        response_b = await client.post("/bookmarks", json=bookmark_b_data)
        assert response_b.status_code == 201
        bookmark_b_id = response_b.json()["id"]

        # Attempt to update bookmark B's URL to bookmark A's URL
        update_data = {"url": "https://example.com"}
        response_update = await client.put(f"/bookmarks/{bookmark_b_id}", json=update_data)
        assert response_update.status_code == 409
        assert "A bookmark with this URL already exists" in response_update.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_bookmark_auto_updates_changed_time(
        self, client: AsyncClient, sample_bookmark_data: dict
    ):
        """
        Test 3: The changed_time timestamp is automatically updated on modification.

        Critical for audit trail integrity - users need to track when bookmarks were modified.
        """
        # Create a bookmark
        response = await client.post("/bookmarks", json=sample_bookmark_data)
        assert response.status_code == 201
        bookmark_data = response.json()
        bookmark_id = bookmark_data["id"]
        original_changed_time = datetime.fromisoformat(
            bookmark_data["changed_time"].replace("Z", "+00:00")
        )

        # Wait a moment to ensure time difference
        await asyncio.sleep(0.1)

        # Update the bookmark
        update_data = {"title": "Updated Title"}
        response_update = await client.put(f"/bookmarks/{bookmark_id}", json=update_data)
        assert response_update.status_code == 200
        updated_bookmark = response_update.json()
        updated_changed_time = datetime.fromisoformat(
            updated_bookmark["changed_time"].replace("Z", "+00:00")
        )

        # Assert changed_time was updated
        assert updated_changed_time > original_changed_time
        assert updated_bookmark["title"] == "Updated Title"

    @pytest.mark.asyncio
    async def test_delete_nonexistent_bookmark_returns_404(self, client: AsyncClient):
        """
        Test 4: Deleting a non-existent bookmark returns HTTP 404.

        Critical for proper error signaling and idempotency.
        """
        # Generate a random UUID that doesn't exist
        non_existent_id = str(uuid4())

        # Attempt to delete
        response = await client.delete(f"/bookmarks/{non_existent_id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_bookmark_by_id_returns_404_for_nonexistent(
        self, client: AsyncClient
    ):
        """
        Test 5: Fetching a non-existent bookmark by ID returns HTTP 404.

        Most common error scenario for GET operations - essential for client error handling.
        """
        # Generate a random UUID
        non_existent_id = str(uuid4())

        # Attempt to get
        response = await client.get(f"/bookmarks/{non_existent_id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_and_retrieve_bookmark_happy_path(
        self, client: AsyncClient, sample_bookmark_data: dict
    ):
        """
        Test 14: End-to-end flow: create a bookmark (POST), then retrieve it (GET).

        Most common user workflow - validates data persistence and schema consistency.
        """
        # Create a bookmark
        response_create = await client.post("/bookmarks", json=sample_bookmark_data)
        assert response_create.status_code == 201
        created_bookmark = response_create.json()

        # Verify response structure
        assert "id" in created_bookmark
        assert "user_id" in created_bookmark
        assert created_bookmark["user_id"] == "test-user-123"
        # Pydantic's HttpUrl adds trailing slash - compare normalized URLs
        assert created_bookmark["url"].rstrip("/") == sample_bookmark_data["url"].rstrip("/")
        assert created_bookmark["title"] == sample_bookmark_data["title"]
        assert created_bookmark["description"] == sample_bookmark_data["description"]
        assert "created_time" in created_bookmark
        assert "changed_time" in created_bookmark

        # Retrieve the bookmark by ID
        bookmark_id = created_bookmark["id"]
        response_get = await client.get(f"/bookmarks/{bookmark_id}")
        assert response_get.status_code == 200
        retrieved_bookmark = response_get.json()

        # Verify retrieved data matches created data
        assert retrieved_bookmark["id"] == created_bookmark["id"]
        assert retrieved_bookmark["url"] == created_bookmark["url"]
        assert retrieved_bookmark["title"] == created_bookmark["title"]
        assert retrieved_bookmark["description"] == created_bookmark["description"]
        assert retrieved_bookmark["created_time"] == created_bookmark["created_time"]
        assert retrieved_bookmark["changed_time"] == created_bookmark["changed_time"]

    @pytest.mark.asyncio
    async def test_update_bookmark_partial_update_only_changes_specified_fields(
        self, client: AsyncClient
    ):
        """
        Test 15: Partial updates only modify provided fields, leaving others unchanged.

        Critical for RESTful partial updates - ensures fields not in request remain intact.
        """
        # Create a bookmark
        original_data = {
            "url": "https://example.com",
            "title": "Original Title",
            "description": "Original Description"
        }
        response_create = await client.post("/bookmarks", json=original_data)
        assert response_create.status_code == 201
        created_bookmark = response_create.json()
        bookmark_id = created_bookmark["id"]
        original_created_time = created_bookmark["created_time"]

        # Update only the title
        update_data = {"title": "Updated Title"}
        response_update = await client.put(f"/bookmarks/{bookmark_id}", json=update_data)
        assert response_update.status_code == 200
        updated_bookmark = response_update.json()

        # Verify only title was updated
        assert updated_bookmark["title"] == "Updated Title"
        # Pydantic's HttpUrl adds trailing slash - compare normalized URLs
        assert updated_bookmark["url"].rstrip("/") == original_data["url"].rstrip("/")  # Unchanged
        assert updated_bookmark["description"] == original_data["description"]  # Unchanged

        # Verify created_time remains unchanged, but changed_time was updated
        assert updated_bookmark["created_time"] == original_created_time
        assert updated_bookmark["changed_time"] != created_bookmark["changed_time"]
