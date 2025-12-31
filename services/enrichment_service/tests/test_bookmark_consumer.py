import pytest
from unittest.mock import AsyncMock, patch
from uuid import UUID
from app.consumers.bookmark_consumer import BookmarkEnrichmentConsumer
from app.schemas.enrichment import EnrichmentResult


@pytest.mark.asyncio
class TestBookmarkEnrichmentConsumer:
    """Tests for Kafka bookmark enrichment consumer."""

    async def test_enrich_bookmark_success(self, sample_bookmark_event):
        """Test complete successful enrichment flow."""
        consumer = BookmarkEnrichmentConsumer()

        # Mock the dependencies
        mock_enrichment_result = EnrichmentResult(
            og_title="Test Title", og_description="Test Description"
        )

        consumer.retry_handler.fetch_with_retry = AsyncMock(
            return_value=mock_enrichment_result
        )
        consumer.retry_handler.update_with_retry = AsyncMock(return_value=True)

        # Execute enrichment
        await consumer._enrich_bookmark(sample_bookmark_event)

        # Verify fetch was called with correct URL
        consumer.retry_handler.fetch_with_retry.assert_called_once()
        call_args = consumer.retry_handler.fetch_with_retry.call_args
        assert call_args[0][1] == sample_bookmark_event.data["url"]

        # Verify update was called with correct parameters
        consumer.retry_handler.update_with_retry.assert_called_once()
        update_args = consumer.retry_handler.update_with_retry.call_args
        assert isinstance(update_args[0][1], UUID)
        assert update_args[0][2] == sample_bookmark_event.data["tenant_id"]
        assert update_args[0][3] == mock_enrichment_result

    async def test_enrich_bookmark_missing_url_logs_error(
        self, sample_bookmark_event_missing_url
    ):
        """Test that missing URL field is handled gracefully."""
        consumer = BookmarkEnrichmentConsumer()

        consumer.retry_handler.fetch_with_retry = AsyncMock()
        consumer.retry_handler.update_with_retry = AsyncMock()

        # Should not raise exception
        await consumer._enrich_bookmark(sample_bookmark_event_missing_url)

        # Should not call fetch or update when URL is missing
        consumer.retry_handler.fetch_with_retry.assert_not_called()
        consumer.retry_handler.update_with_retry.assert_not_called()

    async def test_enrich_bookmark_missing_bookmark_id_logs_error(self):
        """Test that missing bookmark_id field is handled gracefully."""
        from datetime import datetime, timezone
        from uuid import uuid4
        from app.schemas.kafka_events import BookmarkEvent

        event = BookmarkEvent(
            event_id=uuid4(),
            event_type="created",
            timestamp=datetime.now(timezone.utc),
            data={
                "url": "https://example.com",
                "tenant_id": "test-user-123",
                # Missing 'id' field
            },
            metadata={"service": "bookmark-service", "version": "1.0.0"},
        )

        consumer = BookmarkEnrichmentConsumer()
        consumer.retry_handler.fetch_with_retry = AsyncMock()
        consumer.retry_handler.update_with_retry = AsyncMock()

        # Should not raise exception
        await consumer._enrich_bookmark(event)

        # Should not call fetch or update when ID is missing
        consumer.retry_handler.fetch_with_retry.assert_not_called()
        consumer.retry_handler.update_with_retry.assert_not_called()

    async def test_enrich_bookmark_missing_tenant_id_logs_error(self):
        """Test that missing tenant_id field is handled gracefully."""
        from datetime import datetime, timezone
        from uuid import uuid4
        from app.schemas.kafka_events import BookmarkEvent

        event = BookmarkEvent(
            event_id=uuid4(),
            event_type="created",
            timestamp=datetime.now(timezone.utc),
            data={
                "id": str(uuid4()),
                "url": "https://example.com",
                # Missing 'tenant_id' field
            },
            metadata={"service": "bookmark-service", "version": "1.0.0"},
        )

        consumer = BookmarkEnrichmentConsumer()
        consumer.retry_handler.fetch_with_retry = AsyncMock()
        consumer.retry_handler.update_with_retry = AsyncMock()

        # Should not raise exception
        await consumer._enrich_bookmark(event)

        # Should not call fetch or update when tenant_id is missing
        consumer.retry_handler.fetch_with_retry.assert_not_called()
        consumer.retry_handler.update_with_retry.assert_not_called()

    async def test_enrich_bookmark_fetch_error_does_not_crash(
        self, sample_bookmark_event
    ):
        """Test that fetch errors are caught and don't crash consumer."""
        consumer = BookmarkEnrichmentConsumer()

        # Mock fetch to raise an exception
        consumer.retry_handler.fetch_with_retry = AsyncMock(
            side_effect=Exception("Fetch failed")
        )
        consumer.retry_handler.update_with_retry = AsyncMock()

        # Should not raise exception
        await consumer._enrich_bookmark(sample_bookmark_event)

        # Fetch should have been called
        consumer.retry_handler.fetch_with_retry.assert_called_once()

        # Update should not be called because fetch failed
        consumer.retry_handler.update_with_retry.assert_not_called()

    async def test_enrich_bookmark_update_error_does_not_crash(
        self, sample_bookmark_event
    ):
        """Test that update errors are caught and don't crash consumer."""
        consumer = BookmarkEnrichmentConsumer()

        mock_enrichment_result = EnrichmentResult(og_title="Test")

        # Mock fetch to succeed but update to fail
        consumer.retry_handler.fetch_with_retry = AsyncMock(
            return_value=mock_enrichment_result
        )
        consumer.retry_handler.update_with_retry = AsyncMock(
            side_effect=Exception("Update failed")
        )

        # Should not raise exception
        await consumer._enrich_bookmark(sample_bookmark_event)

        # Both should have been called
        consumer.retry_handler.fetch_with_retry.assert_called_once()
        consumer.retry_handler.update_with_retry.assert_called_once()

    async def test_enrich_bookmark_calls_retry_handler_fetch(
        self, sample_bookmark_event
    ):
        """Test that enrichment calls retry handler's fetch method."""
        consumer = BookmarkEnrichmentConsumer()

        mock_enrichment_result = EnrichmentResult(og_title="Test")
        consumer.retry_handler.fetch_with_retry = AsyncMock(
            return_value=mock_enrichment_result
        )
        consumer.retry_handler.update_with_retry = AsyncMock(return_value=True)

        await consumer._enrich_bookmark(sample_bookmark_event)

        # Verify fetch_with_retry was called with fetcher and URL
        consumer.retry_handler.fetch_with_retry.assert_called_once()
        args = consumer.retry_handler.fetch_with_retry.call_args[0]
        assert args[0] == consumer.fetcher
        assert args[1] == sample_bookmark_event.data["url"]

    async def test_enrich_bookmark_calls_retry_handler_update(
        self, sample_bookmark_event
    ):
        """Test that enrichment calls retry handler's update method."""
        consumer = BookmarkEnrichmentConsumer()

        mock_enrichment_result = EnrichmentResult(og_title="Test")
        consumer.retry_handler.fetch_with_retry = AsyncMock(
            return_value=mock_enrichment_result
        )
        consumer.retry_handler.update_with_retry = AsyncMock(return_value=True)

        await consumer._enrich_bookmark(sample_bookmark_event)

        # Verify update_with_retry was called with correct parameters
        consumer.retry_handler.update_with_retry.assert_called_once()
        args = consumer.retry_handler.update_with_retry.call_args[0]
        assert args[0] == consumer.bookmark_client
        assert isinstance(args[1], UUID)
        assert args[2] == sample_bookmark_event.data["tenant_id"]
        assert args[3] == mock_enrichment_result

    async def test_enrich_bookmark_converts_string_to_uuid(self, sample_bookmark_event):
        """Test that bookmark ID string is converted to UUID."""
        consumer = BookmarkEnrichmentConsumer()

        mock_enrichment_result = EnrichmentResult(og_title="Test")
        consumer.retry_handler.fetch_with_retry = AsyncMock(
            return_value=mock_enrichment_result
        )
        consumer.retry_handler.update_with_retry = AsyncMock(return_value=True)

        await consumer._enrich_bookmark(sample_bookmark_event)

        # Verify UUID conversion
        update_args = consumer.retry_handler.update_with_retry.call_args[0]
        bookmark_id = update_args[1]

        assert isinstance(bookmark_id, UUID)
        assert str(bookmark_id) == sample_bookmark_event.data["id"]

    async def test_enrich_bookmark_logs_success(self, sample_bookmark_event):
        """Test that successful enrichment is logged."""
        consumer = BookmarkEnrichmentConsumer()

        mock_enrichment_result = EnrichmentResult(og_title="Test")
        consumer.retry_handler.fetch_with_retry = AsyncMock(
            return_value=mock_enrichment_result
        )
        consumer.retry_handler.update_with_retry = AsyncMock(return_value=True)

        # Capture log output
        with patch("app.consumers.bookmark_consumer.logger") as mock_logger:
            await consumer._enrich_bookmark(sample_bookmark_event)

            # Verify success logging
            mock_logger.info.assert_any_call(
                f"Successfully enriched bookmark {sample_bookmark_event.data['id']}"
            )
