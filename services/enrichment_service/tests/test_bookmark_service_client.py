import pytest
import httpx
import respx
from uuid import uuid4
from app.enrichers.bookmark_service_client import BookmarkServiceClient
from app.schemas.enrichment import EnrichmentResult


@pytest.mark.asyncio
class TestBookmarkServiceClient:
    """Tests for Bookmark Service API client."""

    async def test_update_bookmark_enrichment_success(self, sample_enrichment_result):
        """Test successful bookmark update returns True."""
        bookmark_id = uuid4()
        user_id = "test-user-123"

        async with respx.mock:
            route = respx.put(
                f"http://bookmark-service:8000/bookmarks/{bookmark_id}"
            ).mock(return_value=httpx.Response(200, json={"success": True}))

            client = BookmarkServiceClient()
            result = await client.update_bookmark_enrichment(
                bookmark_id, user_id, sample_enrichment_result
            )

            assert result is True
            assert route.called

    async def test_update_bookmark_enrichment_sends_correct_payload(
        self, sample_enrichment_result
    ):
        """Test that correct payload is sent to API."""
        bookmark_id = uuid4()
        user_id = "test-user-123"

        async with respx.mock:
            route = respx.put(
                f"http://bookmark-service:8000/bookmarks/{bookmark_id}"
            ).mock(return_value=httpx.Response(200, json={"success": True}))

            client = BookmarkServiceClient()
            await client.update_bookmark_enrichment(
                bookmark_id, user_id, sample_enrichment_result
            )

            # Verify payload structure
            request = route.calls.last.request
            payload = request.content.decode("utf-8")

            assert '"og_title": "Test Title"' in payload
            assert '"og_description": "Test Description"' in payload
            assert '"og_image": "https://example.com/image.jpg"' in payload
            assert '"og_type": "article"' in payload
            assert '"og_site_name": "Test Site"' in payload
            assert '"meta_description": "Meta description"' in payload
            assert '"favicon_url": "https://example.com/favicon.ico"' in payload

    async def test_update_bookmark_enrichment_sends_user_id_header(
        self, sample_enrichment_result
    ):
        """Test that X-User-ID header is included in request."""
        bookmark_id = uuid4()
        user_id = "test-user-123"

        async with respx.mock:
            route = respx.put(
                f"http://bookmark-service:8000/bookmarks/{bookmark_id}"
            ).mock(return_value=httpx.Response(200, json={"success": True}))

            client = BookmarkServiceClient()
            await client.update_bookmark_enrichment(
                bookmark_id, user_id, sample_enrichment_result
            )

            # Verify X-User-ID header
            request = route.calls.last.request
            assert request.headers.get("X-User-ID") == user_id

    async def test_update_bookmark_enrichment_raises_on_404_error(
        self, sample_enrichment_result
    ):
        """Test that 404 error raises HTTPStatusError."""
        bookmark_id = uuid4()
        user_id = "test-user-123"

        async with respx.mock:
            respx.put(f"http://bookmark-service:8000/bookmarks/{bookmark_id}").mock(
                return_value=httpx.Response(404, json={"error": "Not found"})
            )

            client = BookmarkServiceClient()
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await client.update_bookmark_enrichment(
                    bookmark_id, user_id, sample_enrichment_result
                )

            assert exc_info.value.response.status_code == 404

    async def test_update_bookmark_enrichment_raises_on_500_error(
        self, sample_enrichment_result
    ):
        """Test that 500 error raises HTTPStatusError."""
        bookmark_id = uuid4()
        user_id = "test-user-123"

        async with respx.mock:
            respx.put(f"http://bookmark-service:8000/bookmarks/{bookmark_id}").mock(
                return_value=httpx.Response(
                    500, json={"error": "Internal server error"}
                )
            )

            client = BookmarkServiceClient()
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await client.update_bookmark_enrichment(
                    bookmark_id, user_id, sample_enrichment_result
                )

            assert exc_info.value.response.status_code == 500

    async def test_update_bookmark_enrichment_raises_on_timeout(
        self, sample_enrichment_result
    ):
        """Test that timeout raises TimeoutException."""
        bookmark_id = uuid4()
        user_id = "test-user-123"

        async with respx.mock:
            respx.put(f"http://bookmark-service:8000/bookmarks/{bookmark_id}").mock(
                side_effect=httpx.TimeoutException("Request timeout")
            )

            client = BookmarkServiceClient()
            with pytest.raises(httpx.TimeoutException):
                await client.update_bookmark_enrichment(
                    bookmark_id, user_id, sample_enrichment_result
                )

    async def test_update_bookmark_enrichment_correct_url_construction(
        self, sample_enrichment_result
    ):
        """Test that PUT request URL is correctly constructed."""
        bookmark_id = uuid4()
        user_id = "test-user-123"

        async with respx.mock:
            route = respx.put(
                f"http://bookmark-service:8000/bookmarks/{bookmark_id}"
            ).mock(return_value=httpx.Response(200, json={"success": True}))

            client = BookmarkServiceClient()
            await client.update_bookmark_enrichment(
                bookmark_id, user_id, sample_enrichment_result
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
        user_id = "test-user-123"

        async with respx.mock:
            respx.put(f"http://bookmark-service:8000/bookmarks/{bookmark_id}").mock(
                side_effect=httpx.ConnectError("Connection failed")
            )

            client = BookmarkServiceClient()
            with pytest.raises(httpx.ConnectError):
                await client.update_bookmark_enrichment(
                    bookmark_id, user_id, sample_enrichment_result
                )
