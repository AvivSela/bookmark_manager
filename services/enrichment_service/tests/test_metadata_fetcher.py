import pytest
import httpx
import respx
from app.enrichers.metadata_fetcher import MetadataFetcher


@pytest.mark.asyncio
class TestMetadataFetcher:
    """Tests for HTML metadata extraction."""

    async def test_fetch_metadata_with_og_tags_success(self, sample_html_with_og_tags):
        """Test successful metadata extraction from Open Graph tags."""
        async with respx.mock:
            respx.get("https://example.com").mock(
                return_value=httpx.Response(
                    200,
                    text=sample_html_with_og_tags,
                    headers={"content-type": "text/html; charset=utf-8"},
                )
            )

            fetcher = MetadataFetcher()
            result = await fetcher.fetch_metadata("https://example.com")

            assert result.og_title == "Example Page Title"
            assert result.og_description == "This is an example page description"
            assert result.og_image == "https://example.com/image.jpg"
            assert result.og_type == "website"
            assert result.og_site_name == "Example Site"
            assert result.meta_description == "Standard meta description"
            assert result.favicon_url == "https://example.com/favicon.ico"

    async def test_fetch_metadata_without_og_tags_uses_meta_description(
        self, sample_html_without_og_tags
    ):
        """Test fallback to standard meta tags when OG tags are missing."""
        async with respx.mock:
            respx.get("https://example.com").mock(
                return_value=httpx.Response(
                    200,
                    text=sample_html_without_og_tags,
                    headers={"content-type": "text/html"},
                )
            )

            fetcher = MetadataFetcher()
            result = await fetcher.fetch_metadata("https://example.com")

            assert result.og_title is None
            assert result.og_description is None
            assert result.og_image is None
            assert result.og_type is None
            assert result.og_site_name is None
            assert result.meta_description == "Standard meta description only"
            assert result.favicon_url == "https://example.com/assets/favicon.png"

    async def test_fetch_metadata_missing_all_tags_returns_none_values(
        self, sample_html_minimal
    ):
        """Test handling of HTML with no metadata tags."""
        async with respx.mock:
            respx.get("https://example.com").mock(
                return_value=httpx.Response(
                    200, text=sample_html_minimal, headers={"content-type": "text/html"}
                )
            )

            fetcher = MetadataFetcher()
            result = await fetcher.fetch_metadata("https://example.com")

            assert result.og_title is None
            assert result.og_description is None
            assert result.og_image is None
            assert result.og_type is None
            assert result.og_site_name is None
            assert result.meta_description is None
            # Fallback favicon should still be set
            assert result.favicon_url == "https://example.com/favicon.ico"

    async def test_fetch_metadata_rejects_json_content_type(self):
        """Test rejection of non-HTML content type (application/json)."""
        async with respx.mock:
            respx.get("https://api.example.com/data").mock(
                return_value=httpx.Response(
                    200,
                    json={"data": "not html"},
                    headers={"content-type": "application/json"},
                )
            )

            fetcher = MetadataFetcher()
            with pytest.raises(ValueError, match="Non-HTML content type"):
                await fetcher.fetch_metadata("https://api.example.com/data")

    async def test_fetch_metadata_rejects_image_content_type(self):
        """Test rejection of non-HTML content type (image/png)."""
        async with respx.mock:
            respx.get("https://example.com/image.png").mock(
                return_value=httpx.Response(
                    200,
                    content=b"fake image data",
                    headers={"content-type": "image/png"},
                )
            )

            fetcher = MetadataFetcher()
            with pytest.raises(ValueError, match="Non-HTML content type"):
                await fetcher.fetch_metadata("https://example.com/image.png")

    async def test_fetch_metadata_handles_timeout(self):
        """Test handling of network timeout."""
        async with respx.mock:
            respx.get("https://slow-site.com").mock(
                side_effect=httpx.TimeoutException("Request timeout")
            )

            fetcher = MetadataFetcher()
            with pytest.raises(httpx.TimeoutException):
                await fetcher.fetch_metadata("https://slow-site.com")

    async def test_fetch_metadata_handles_connection_error(self):
        """Test handling of connection errors."""
        async with respx.mock:
            respx.get("https://unreachable.com").mock(
                side_effect=httpx.ConnectError("Connection failed")
            )

            fetcher = MetadataFetcher()
            with pytest.raises(httpx.ConnectError):
                await fetcher.fetch_metadata("https://unreachable.com")

    async def test_fetch_metadata_handles_404_error(self):
        """Test handling of HTTP 404 errors."""
        async with respx.mock:
            respx.get("https://example.com/notfound").mock(
                return_value=httpx.Response(
                    404, text="Not Found", headers={"content-type": "text/html"}
                )
            )

            fetcher = MetadataFetcher()
            with pytest.raises(httpx.HTTPStatusError):
                await fetcher.fetch_metadata("https://example.com/notfound")

    async def test_fetch_metadata_handles_500_error(self):
        """Test handling of HTTP 500 errors."""
        async with respx.mock:
            respx.get("https://example.com/error").mock(
                return_value=httpx.Response(
                    500,
                    text="Internal Server Error",
                    headers={"content-type": "text/html"},
                )
            )

            fetcher = MetadataFetcher()
            with pytest.raises(httpx.HTTPStatusError):
                await fetcher.fetch_metadata("https://example.com/error")

    async def test_get_favicon_with_icon_link_tag(self):
        """Test favicon extraction from <link rel='icon'>."""
        html = """
        <html>
        <head>
            <link rel="icon" href="/favicon.png" />
        </head>
        </html>
        """
        async with respx.mock:
            respx.get("https://example.com").mock(
                return_value=httpx.Response(
                    200, text=html, headers={"content-type": "text/html"}
                )
            )

            fetcher = MetadataFetcher()
            result = await fetcher.fetch_metadata("https://example.com")
            assert result.favicon_url == "https://example.com/favicon.png"

    async def test_get_favicon_with_shortcut_icon_link_tag(self):
        """Test favicon extraction from <link rel='shortcut icon'>."""
        html = """
        <html>
        <head>
            <link rel="shortcut icon" href="/assets/icon.ico" />
        </head>
        </html>
        """
        async with respx.mock:
            respx.get("https://example.com").mock(
                return_value=httpx.Response(
                    200, text=html, headers={"content-type": "text/html"}
                )
            )

            fetcher = MetadataFetcher()
            result = await fetcher.fetch_metadata("https://example.com")
            assert result.favicon_url == "https://example.com/assets/icon.ico"

    async def test_get_favicon_fallback_to_default_path(self):
        """Test fallback to /favicon.ico when no link tag exists."""
        html = """
        <html>
        <head>
            <title>No favicon link</title>
        </head>
        </html>
        """
        async with respx.mock:
            respx.get("https://example.com").mock(
                return_value=httpx.Response(
                    200, text=html, headers={"content-type": "text/html"}
                )
            )

            fetcher = MetadataFetcher()
            result = await fetcher.fetch_metadata("https://example.com")
            assert result.favicon_url == "https://example.com/favicon.ico"

    async def test_fetch_metadata_converts_relative_to_absolute_urls(
        self, sample_html_with_relative_urls
    ):
        """Test conversion of relative URLs to absolute URLs."""
        async with respx.mock:
            respx.get("https://example.com/page").mock(
                return_value=httpx.Response(
                    200,
                    text=sample_html_with_relative_urls,
                    headers={"content-type": "text/html"},
                )
            )

            fetcher = MetadataFetcher()
            result = await fetcher.fetch_metadata("https://example.com/page")

            # Relative /images/og-image.jpg should become absolute
            assert result.og_image == "https://example.com/images/og-image.jpg"
            # Relative assets/icon.png should become absolute
            assert result.favicon_url == "https://example.com/assets/icon.png"

    async def test_fetch_metadata_with_empty_response(self):
        """Test handling of empty HTML response."""
        async with respx.mock:
            respx.get("https://example.com").mock(
                return_value=httpx.Response(
                    200, text="", headers={"content-type": "text/html"}
                )
            )

            fetcher = MetadataFetcher()
            result = await fetcher.fetch_metadata("https://example.com")

            # Should not crash, all fields should be None except fallback favicon
            assert result.og_title is None
            assert result.og_description is None
            assert result.favicon_url == "https://example.com/favicon.ico"

    async def test_fetch_metadata_follows_redirects(self):
        """Test that fetcher follows HTTP redirects."""
        html = (
            "<html><head><meta property='og:title' content='Redirected'/></head></html>"
        )

        async with respx.mock:
            # Setup redirect chain
            respx.get("https://example.com/old").mock(
                return_value=httpx.Response(
                    301, headers={"location": "https://example.com/new"}
                )
            )
            respx.get("https://example.com/new").mock(
                return_value=httpx.Response(
                    200, text=html, headers={"content-type": "text/html"}
                )
            )

            fetcher = MetadataFetcher()
            result = await fetcher.fetch_metadata("https://example.com/old")

            assert result.og_title == "Redirected"
