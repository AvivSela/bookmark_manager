"""Tests for Kafka event publishing."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestKafkaEventPublishing:
    """Test Kafka event publishing for bookmark operations."""

    async def test_create_bookmark_publishes_created_event(
        self, authenticated_client, mock_kafka_producer, sample_bookmark_data
    ):
        """Verify bookmark.created event is published on successful creation."""
        client = await authenticated_client("test-user-123")

        response = await client.post("/bookmarks", json=sample_bookmark_data)
        assert response.status_code == 201

        # Verify event was published
        assert len(mock_kafka_producer) == 1
        event = mock_kafka_producer[0]
        assert event["event_type"] == "created"
        # URL may be normalized with trailing slash by Pydantic
        assert event["data"]["url"].rstrip("/") == sample_bookmark_data["url"].rstrip(
            "/"
        )
        assert event["data"]["title"] == sample_bookmark_data["title"]
        assert event["data"]["user_id"] == "test-user-123"
        assert "id" in event["data"]
        assert "created_time" in event["data"]
        assert "changed_time" in event["data"]

    async def test_update_bookmark_publishes_updated_event(
        self, authenticated_client, mock_kafka_producer, sample_bookmark_data
    ):
        """Verify bookmark.updated event is published on successful update."""
        client = await authenticated_client("test-user-456")

        # Create bookmark first
        response = await client.post("/bookmarks", json=sample_bookmark_data)
        assert response.status_code == 201
        bookmark_id = response.json()["id"]

        # Clear events from creation
        mock_kafka_producer.clear()

        # Update bookmark
        update_data = {"title": "Updated Title"}
        response = await client.put(f"/bookmarks/{bookmark_id}", json=update_data)
        assert response.status_code == 200

        # Verify event was published
        assert len(mock_kafka_producer) == 1
        event = mock_kafka_producer[0]
        assert event["event_type"] == "updated"
        assert event["data"]["title"] == "Updated Title"
        assert event["data"]["user_id"] == "test-user-456"
        assert event["data"]["id"] == bookmark_id

    async def test_delete_bookmark_publishes_deleted_event(
        self, authenticated_client, mock_kafka_producer, sample_bookmark_data
    ):
        """Verify bookmark.deleted event is published on successful deletion."""
        client = await authenticated_client("test-user-789")

        # Create bookmark first
        response = await client.post("/bookmarks", json=sample_bookmark_data)
        assert response.status_code == 201
        bookmark_data = response.json()
        bookmark_id = bookmark_data["id"]
        bookmark_url = bookmark_data["url"]

        # Clear events from creation
        mock_kafka_producer.clear()

        # Delete bookmark
        response = await client.delete(f"/bookmarks/{bookmark_id}")
        assert response.status_code == 204

        # Verify event was published
        assert len(mock_kafka_producer) == 1
        event = mock_kafka_producer[0]
        assert event["event_type"] == "deleted"
        assert event["data"]["id"] == bookmark_id
        assert event["data"]["user_id"] == "test-user-789"
        assert event["data"]["url"] == bookmark_url
        # Deleted events should only have minimal data
        assert set(event["data"].keys()) == {"id", "user_id", "url"}

    async def test_duplicate_url_creation_does_not_publish_event(
        self, authenticated_client, mock_kafka_producer, sample_bookmark_data
    ):
        """Verify no event is published when creation fails due to duplicate URL."""
        client = await authenticated_client("test-user-duplicate")

        # Create first bookmark
        response = await client.post("/bookmarks", json=sample_bookmark_data)
        assert response.status_code == 201

        # Clear events
        mock_kafka_producer.clear()

        # Attempt duplicate creation
        response = await client.post("/bookmarks", json=sample_bookmark_data)
        assert response.status_code == 409

        # Verify no event was published
        assert len(mock_kafka_producer) == 0

    async def test_update_nonexistent_bookmark_no_event(
        self, authenticated_client, mock_kafka_producer
    ):
        """Verify no event is published when update fails (404)."""
        client = await authenticated_client("test-user-404")

        # Attempt to update non-existent bookmark
        response = await client.put(
            "/bookmarks/00000000-0000-0000-0000-000000000000",
            json={"title": "New Title"},
        )
        assert response.status_code == 404

        # Verify no event was published
        assert len(mock_kafka_producer) == 0

    async def test_delete_nonexistent_bookmark_no_event(
        self, authenticated_client, mock_kafka_producer
    ):
        """Verify no event is published when deletion fails (404)."""
        client = await authenticated_client("test-user-404-delete")

        # Attempt to delete non-existent bookmark
        response = await client.delete(
            "/bookmarks/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404

        # Verify no event was published
        assert len(mock_kafka_producer) == 0

    async def test_events_include_correct_user_id(
        self, authenticated_client, mock_kafka_producer, sample_bookmark_data
    ):
        """Verify events include the correct user_id from X-User-ID header."""
        # Create bookmarks for different users
        client1 = await authenticated_client("user-one")
        client2 = await authenticated_client("user-two")

        # User 1 creates a bookmark
        response1 = await client1.post("/bookmarks", json=sample_bookmark_data)
        assert response1.status_code == 201

        # User 2 creates a bookmark with same URL (allowed for different users)
        response2 = await client2.post("/bookmarks", json=sample_bookmark_data)
        assert response2.status_code == 201

        # Verify both events have correct user_ids
        assert len(mock_kafka_producer) == 2
        assert mock_kafka_producer[0]["data"]["user_id"] == "user-one"
        assert mock_kafka_producer[1]["data"]["user_id"] == "user-two"
