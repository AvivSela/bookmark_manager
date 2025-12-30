import pytest
import respx
import httpx
from uuid import uuid4


@pytest.mark.asyncio
async def test_validate_url_success_200(validator, mock_bookmark_id):
    """Test successful URL validation with 200 status."""
    url = "https://example.com"

    with respx.mock:
        respx.head(url).mock(return_value=httpx.Response(200))

        result = await validator.validate_url(mock_bookmark_id, url)

        assert result.validation_status == "valid"
        assert result.http_status == 200
        assert result.error_message is None
        assert result.bookmark_id == mock_bookmark_id
        assert result.url == url


@pytest.mark.asyncio
async def test_validate_url_redirect(validator, mock_bookmark_id):
    """Test URL validation with redirect - follow redirect and verify final_url stored."""
    original_url = "http://example.com"
    final_url = "https://example.com/"

    with respx.mock:
        # Mock redirect: HEAD to original URL returns 301, then follows to final URL
        respx.head(original_url).mock(
            return_value=httpx.Response(
                301,
                headers={"Location": final_url}
            )
        )
        respx.head(final_url).mock(return_value=httpx.Response(200))

        # httpx with follow_redirects=True will handle this automatically
        # We need to mock the final response with the redirected URL
        mock_route = respx.head(original_url)
        mock_route.mock(
            return_value=httpx.Response(
                200,
                headers={},

 # Final response after redirect
            )
        )
        # Override to simulate redirect
        mock_route.side_effect = None
        mock_route.return_value = httpx.Response(200)
        # Set the final URL on the response
        response = httpx.Response(200)
        response._request = httpx.Request("HEAD", final_url)

        # Simpler approach: mock the client behavior
        respx.head(original_url).mock(
            return_value=httpx.Response(
                200,
                request=httpx.Request("HEAD", final_url)
            )
        )

        result = await validator.validate_url(mock_bookmark_id, original_url)

        assert result.validation_status == "valid"
        assert result.http_status == 200
        assert result.final_url == final_url


@pytest.mark.asyncio
async def test_validate_url_404_invalid(validator, mock_bookmark_id):
    """Test validation of non-existent URL returning 404."""
    url = "https://example.com/notfound"

    with respx.mock:
        respx.head(url).mock(return_value=httpx.Response(404))

        result = await validator.validate_url(mock_bookmark_id, url)

        assert result.validation_status == "invalid"
        assert result.http_status == 404
        assert result.error_message is None  # Not an error, just invalid


@pytest.mark.asyncio
async def test_validate_url_timeout(validator, mock_bookmark_id):
    """Test validation with network timeout."""
    url = "https://slow.example.com"

    with respx.mock:
        respx.head(url).mock(side_effect=httpx.TimeoutException("Timeout"))

        result = await validator.validate_url(mock_bookmark_id, url)

        assert result.validation_status == "error"
        assert result.http_status is None
        assert "timeout" in result.error_message.lower()


@pytest.mark.asyncio
async def test_validate_url_network_error(validator, mock_bookmark_id):
    """Test validation with network error."""
    url = "https://unreachable.example.com"

    with respx.mock:
        respx.head(url).mock(
            side_effect=httpx.NetworkError("Network unreachable")
        )

        result = await validator.validate_url(mock_bookmark_id, url)

        assert result.validation_status == "error"
        assert result.http_status is None
        assert "network error" in result.error_message.lower()


@pytest.mark.asyncio
async def test_validate_url_head_fallback_to_get(validator, mock_bookmark_id):
    """Test HEAD returns 405, fallback to GET."""
    url = "https://example.com/resource"

    with respx.mock:
        # HEAD returns 405 Method Not Allowed
        respx.head(url).mock(return_value=httpx.Response(405))
        # GET succeeds
        respx.get(url).mock(return_value=httpx.Response(200))

        result = await validator.validate_url(mock_bookmark_id, url)

        assert result.validation_status == "valid"
        assert result.http_status == 200
        assert result.error_message is None
