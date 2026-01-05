from uuid import uuid4

import httpx
import pytest
import respx
from app.enrichers.clients.bookmark_service_client import BookmarkServiceClient


@pytest.mark.asyncio
class TestBookmarkServiceClient:
    """Tests for Bookmark Service API client."""

    async def test_update_bookmark_enrichment_success(self, sample_enrichment_result):
        """Test successful bookmark update returns True."""
        bookmark_id = uuid4()
        tenant_id = "test-user-123"

        async with respx.mock:
            route = respx.put(
                f"http://bookmark-service:8000/bookmarks/{bookmark_id}"
            ).mock(return_value=httpx.Response(200, json={"success": True}))

            async with BookmarkServiceClient() as client:
                result = await client.update_bookmark_enrichment(
                    bookmark_id, tenant_id, sample_enrichment_result
                )

                assert result is True
                assert route.called

    async def test_update_bookmark_enrichment_sends_correct_payload(
        self, sample_enrichment_result
    ):
        """Test that correct payload is sent to API."""
        bookmark_id = uuid4()
        tenant_id = "test-user-123"

        async with respx.mock:
            route = respx.put(
                f"http://bookmark-service:8000/bookmarks/{bookmark_id}"
            ).mock(return_value=httpx.Response(200, json={"success": True}))

            async with BookmarkServiceClient() as client:
                await client.update_bookmark_enrichment(
                    bookmark_id, tenant_id, sample_enrichment_result
                )

                # Verify payload structure - enrichments should be nested in enrichments object
                request = route.calls.last.request
                payload = request.content.decode("utf-8")

                # Check that enrichments are nested
                assert '"enrichments"' in payload
                assert '"og_title": "Test Title"' in payload
                assert '"og_description": "Test Description"' in payload
                assert '"og_image": "https://example.com/image.jpg"' in payload
                assert '"og_type": "article"' in payload
                assert '"og_site_name": "Test Site"' in payload
                assert '"meta_description": "Meta description"' in payload
                assert '"favicon_url": "https://example.com/favicon.ico"' in payload
                assert '"webpage_metadata"' in payload
                assert '"text": "Sample extracted text content"' in payload

    async def test_update_bookmark_enrichment_sends_tenant_id_header(
        self, sample_enrichment_result
    ):
        """Test that X-Tenant-ID header is included in request."""
        bookmark_id = uuid4()
        tenant_id = "test-user-123"

        async with respx.mock:
            route = respx.put(
                f"http://bookmark-service:8000/bookmarks/{bookmark_id}"
            ).mock(return_value=httpx.Response(200, json={"success": True}))

            async with BookmarkServiceClient() as client:
                await client.update_bookmark_enrichment(
                    bookmark_id, tenant_id, sample_enrichment_result
                )

                # Verify X-Tenant-ID header
                request = route.calls.last.request
                assert request.headers.get("X-Tenant-ID") == tenant_id

    async def test_update_bookmark_enrichment_raises_on_404_error(
        self, sample_enrichment_result
    ):
        """Test that 404 error raises HTTPStatusError."""
        bookmark_id = uuid4()
        tenant_id = "test-user-123"

        async with respx.mock:
            respx.put(f"http://bookmark-service:8000/bookmarks/{bookmark_id}").mock(
                return_value=httpx.Response(404, json={"error": "Not found"})
            )

            async with BookmarkServiceClient() as client:
                with pytest.raises(httpx.HTTPStatusError) as exc_info:
                    await client.update_bookmark_enrichment(
                        bookmark_id, tenant_id, sample_enrichment_result
                    )

                assert exc_info.value.response.status_code == 404

    async def test_update_bookmark_enrichment_raises_on_500_error(
        self, sample_enrichment_result
    ):
        """Test that 500 error raises HTTPStatusError."""
        bookmark_id = uuid4()
        tenant_id = "test-user-123"

        async with respx.mock:
            respx.put(f"http://bookmark-service:8000/bookmarks/{bookmark_id}").mock(
                return_value=httpx.Response(
                    500, json={"error": "Internal server error"}
                )
            )

            async with BookmarkServiceClient() as client:
                with pytest.raises(httpx.HTTPStatusError) as exc_info:
                    await client.update_bookmark_enrichment(
                        bookmark_id, tenant_id, sample_enrichment_result
                    )

                assert exc_info.value.response.status_code == 500

    async def test_update_bookmark_enrichment_raises_on_timeout(
        self, sample_enrichment_result
    ):
        """Test that timeout raises TimeoutException."""
        bookmark_id = uuid4()
        tenant_id = "test-user-123"

        async with respx.mock:
            respx.put(f"http://bookmark-service:8000/bookmarks/{bookmark_id}").mock(
                side_effect=httpx.TimeoutException("Request timeout")
            )

            async with BookmarkServiceClient() as client:
                with pytest.raises(httpx.TimeoutException):
                    await client.update_bookmark_enrichment(
                        bookmark_id, tenant_id, sample_enrichment_result
                    )

    async def test_update_bookmark_enrichment_correct_url_construction(
        self, sample_enrichment_result
    ):
        """Test that PUT request URL is correctly constructed."""
        bookmark_id = uuid4()
        tenant_id = "test-user-123"

        async with respx.mock:
            route = respx.put(
                f"http://bookmark-service:8000/bookmarks/{bookmark_id}"
            ).mock(return_value=httpx.Response(200, json={"success": True}))

            async with BookmarkServiceClient() as client:
                await client.update_bookmark_enrichment(
                    bookmark_id, tenant_id, sample_enrichment_result
                )

                # Verify URL construction
                request = route.calls.last.request
                expected_url = f"http://bookmark-service:8000/bookmarks/{bookmark_id}"
                assert str(request.url) == expected_url

    async def test_update_bookmark_enrichment_handles_connection_error(
        self, sample_enrichment_result
    ):
        """Test that connection error raises ConnectError."""
        bookmark_id = uuid4()
        tenant_id = "test-user-123"

        async with respx.mock:
            respx.put(f"http://bookmark-service:8000/bookmarks/{bookmark_id}").mock(
                side_effect=httpx.ConnectError("Connection failed")
            )

            async with BookmarkServiceClient() as client:
                with pytest.raises(httpx.ConnectError):
                    await client.update_bookmark_enrichment(
                        bookmark_id, tenant_id, sample_enrichment_result
                    )

    async def test_update_bookmark_enrichment_includes_webpage_metadata(self):
        """Test that webpage_metadata is included in enrichment payload."""
        from app.schemas.enrichment import EnrichmentResult

        bookmark_id = uuid4()
        tenant_id = "test-user-123"
        enrichment_result = EnrichmentResult(
            og_title="Test Title",
            webpage_metadata={
                "text": "Sample content",
                "title": "Article Title",
                "author": "Author Name",
            },
        )

        async with respx.mock:
            route = respx.put(
                f"http://bookmark-service:8000/bookmarks/{bookmark_id}"
            ).mock(return_value=httpx.Response(200, json={"success": True}))

            async with BookmarkServiceClient() as client:
                result = await client.update_bookmark_enrichment(
                    bookmark_id, tenant_id, enrichment_result
                )

            # Verify webpage_metadata is in the payload
            request = route.calls.last.request
            payload = request.content.decode("utf-8")
            assert '"webpage_metadata"' in payload
            assert '"text": "Sample content"' in payload
            assert result is True

    async def test_update_bookmark_enrichment_filters_none_webpage_metadata(self):
        """Test that None webpage_metadata is filtered out."""
        from app.schemas.enrichment import EnrichmentResult

        bookmark_id = uuid4()
        tenant_id = "test-user-123"
        enrichment_result = EnrichmentResult(
            og_title="Test Title",
            webpage_metadata=None,
        )

        async with respx.mock:
            route = respx.put(
                f"http://bookmark-service:8000/bookmarks/{bookmark_id}"
            ).mock(return_value=httpx.Response(200, json={"success": True}))

            async with BookmarkServiceClient() as client:
                await client.update_bookmark_enrichment(
                    bookmark_id, tenant_id, enrichment_result
                )

            # Verify webpage_metadata is NOT in payload when None
            request = route.calls.last.request
            payload = request.content.decode("utf-8")
            assert '"webpage_metadata"' not in payload
