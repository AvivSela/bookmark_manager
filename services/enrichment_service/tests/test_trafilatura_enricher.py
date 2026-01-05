"""Tests for TrafilaturaEnricher."""

import pytest
import httpx
import respx

from app.enrichers.implementations.trafilatura_enricher import TrafilaturaEnricher
from app.enrichers.core.base_enricher import EnricherContext
from app.enrichers.core.resource_types import ResourceType


@pytest.fixture
def trafilatura_enricher():
    """Create TrafilaturaEnricher instance."""
    return TrafilaturaEnricher()


@pytest.fixture
def enricher_context():
    """Create enricher context for testing."""
    return EnricherContext(
        url="https://example.com/article",
        bookmark_id="test-bookmark-id",
        tenant_id="test-tenant-id",
        resource_type=ResourceType.WEBPAGE,
        timeout=10.0,
    )


@pytest.fixture
def sample_article_html():
    """Sample article HTML for testing."""
    return """
    <html>
    <head>
        <title>Test Article</title>
        <meta name="author" content="John Doe">
        <meta name="description" content="A test article about testing">
    </head>
    <body>
        <article>
            <h1>Test Article Title</h1>
            <p>This is the main content of the article.</p>
            <p>It contains multiple paragraphs with interesting information.</p>
            <p>Trafilatura should be able to extract this text content.</p>
        </article>
    </body>
    </html>
    """


@pytest.fixture
def sample_blog_html():
    """Sample blog post HTML for testing."""
    return """
    <html>
    <head>
        <title>My Blog Post</title>
        <meta name="author" content="Jane Smith">
    </head>
    <body>
        <div class="post">
            <h1>How to Write Good Tests</h1>
            <p class="date">Published on 2024-01-15</p>
            <div class="content">
                <p>Testing is crucial for software quality.</p>
                <p>Here are some best practices for writing tests.</p>
            </div>
        </div>
    </body>
    </html>
    """


# ===== Basic Tests =====


def test_enricher_name(trafilatura_enricher):
    """Test that enricher name is 'trafilatura'."""
    assert trafilatura_enricher.name == "trafilatura"


def test_enricher_not_required(trafilatura_enricher):
    """Test that TrafilaturaEnricher is not required."""
    assert trafilatura_enricher.required is False


def test_is_applicable_for_webpage_type(trafilatura_enricher):
    """Test that enricher applies to WEBPAGE resource type."""
    assert trafilatura_enricher.is_applicable(ResourceType.WEBPAGE) is True


def test_not_applicable_for_other_types(trafilatura_enricher):
    """Test that enricher doesn't apply to non-WEBPAGE types."""
    assert trafilatura_enricher.is_applicable(ResourceType.IMAGE) is False
    assert trafilatura_enricher.is_applicable(ResourceType.API) is False
    assert trafilatura_enricher.is_applicable(ResourceType.DATASET) is False
    assert trafilatura_enricher.is_applicable(ResourceType.VIDEO) is False
    assert trafilatura_enricher.is_applicable(ResourceType.UNKNOWN) is False


# ===== Functional Tests =====


@pytest.mark.asyncio
async def test_extract_article_metadata(
    trafilatura_enricher, enricher_context, sample_article_html, respx_mock
):
    """Test extracting metadata from article HTML."""
    # Mock HTTP GET request
    respx_mock.get("https://example.com/article").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=sample_article_html.encode("utf-8"),
        )
    )

    # Execute enrichment
    result = await trafilatura_enricher.enrich(enricher_context)

    # Assertions
    assert result.success is True
    assert result.error is None
    assert "webpage_metadata" in result.data
    assert result.execution_time_ms > 0

    metadata = result.data["webpage_metadata"]
    assert isinstance(metadata, dict)

    # Verify some extracted fields (trafilatura should extract these)
    # Note: exact fields depend on trafilatura's extraction
    assert len(metadata) > 0  # Should extract at least some fields

    # Common fields that should be present
    if "text" in metadata:
        assert "article" in metadata["text"].lower() or "content" in metadata["text"].lower()

    if "title" in metadata:
        assert len(metadata["title"]) > 0


@pytest.mark.asyncio
async def test_extract_blog_post_metadata(
    trafilatura_enricher, enricher_context, sample_blog_html, respx_mock
):
    """Test extracting metadata from blog HTML."""
    # Mock HTTP GET request
    respx_mock.get("https://example.com/article").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=sample_blog_html.encode("utf-8"),
        )
    )

    # Execute enrichment
    result = await trafilatura_enricher.enrich(enricher_context)

    # Assertions
    assert result.success is True
    assert "webpage_metadata" in result.data

    metadata = result.data["webpage_metadata"]
    assert isinstance(metadata, dict)
    assert len(metadata) > 0


@pytest.mark.asyncio
async def test_handle_non_html_content(
    trafilatura_enricher, enricher_context, respx_mock
):
    """Test graceful failure on non-HTML content."""
    # Mock JSON response
    respx_mock.get("https://example.com/article").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=b'{"key": "value"}',
        )
    )

    # Execute enrichment
    result = await trafilatura_enricher.enrich(enricher_context)

    # Should fail gracefully
    assert result.success is False
    assert result.error is not None
    assert "non-html" in result.error.lower()
    assert result.data == {}


@pytest.mark.asyncio
async def test_handle_extraction_failure(
    trafilatura_enricher, enricher_context, respx_mock
):
    """Test handling when trafilatura returns None (extraction failed)."""
    # Mock HTML that might cause trafilatura to return None
    empty_html = "<html><head></head><body></body></html>"

    respx_mock.get("https://example.com/article").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=empty_html.encode("utf-8"),
        )
    )

    # Execute enrichment
    result = await trafilatura_enricher.enrich(enricher_context)

    # Should succeed but with empty or minimal metadata
    assert result.success is True
    assert "webpage_metadata" in result.data

    # Metadata might be empty dict if trafilatura returns None
    metadata = result.data["webpage_metadata"]
    assert isinstance(metadata, dict)


@pytest.mark.asyncio
async def test_response_size_limit(
    trafilatura_enricher, enricher_context, respx_mock
):
    """Test that response size limit is enforced."""
    # Create large content (6MB, exceeds 5MB limit)
    large_html = "<html><body>" + ("x" * (6 * 1024 * 1024)) + "</body></html>"

    respx_mock.get("https://example.com/article").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=large_html.encode("utf-8"),
        )
    )

    # Execute enrichment
    result = await trafilatura_enricher.enrich(enricher_context)

    # Should fail due to size limit
    assert result.success is False
    assert result.error is not None
    assert "size limit" in result.error.lower() or "too large" in result.error.lower()


@pytest.mark.asyncio
async def test_network_error_handling(
    trafilatura_enricher, enricher_context, respx_mock
):
    """Test handling of network connection errors."""
    # Mock network error
    respx_mock.get("https://example.com/article").mock(
        side_effect=httpx.ConnectError("Connection failed")
    )

    # Execute enrichment
    result = await trafilatura_enricher.enrich(enricher_context)

    # Should fail gracefully
    assert result.success is False
    assert result.error is not None
    assert result.data == {}


@pytest.mark.asyncio
async def test_filter_none_values(
    trafilatura_enricher, enricher_context, sample_article_html, respx_mock
):
    """Test that None values are filtered out from webpage_metadata."""
    respx_mock.get("https://example.com/article").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=sample_article_html.encode("utf-8"),
        )
    )

    # Execute enrichment
    result = await trafilatura_enricher.enrich(enricher_context)

    assert result.success is True
    metadata = result.data["webpage_metadata"]

    # Verify no None values in metadata
    for key, value in metadata.items():
        assert value is not None, f"Field {key} should not be None"


# ===== Edge Cases =====


@pytest.mark.asyncio
async def test_minimal_html(trafilatura_enricher, enricher_context, respx_mock):
    """Test handling of pages with minimal content."""
    minimal_html = "<html><head><title>Minimal</title></head><body><p>Short.</p></body></html>"

    respx_mock.get("https://example.com/article").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=minimal_html.encode("utf-8"),
        )
    )

    # Execute enrichment
    result = await trafilatura_enricher.enrich(enricher_context)

    # Should succeed even with minimal content
    assert result.success is True
    assert "webpage_metadata" in result.data


@pytest.mark.asyncio
async def test_empty_html(trafilatura_enricher, enricher_context, respx_mock):
    """Test handling of empty HTML."""
    empty_html = ""

    respx_mock.get("https://example.com/article").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=empty_html.encode("utf-8"),
        )
    )

    # Execute enrichment
    result = await trafilatura_enricher.enrich(enricher_context)

    # Should succeed but with empty/minimal metadata
    assert result.success is True
    assert "webpage_metadata" in result.data


@pytest.mark.asyncio
async def test_non_utf8_encoding(trafilatura_enricher, enricher_context, respx_mock):
    """Test handling of different encodings."""
    # HTML with special characters
    html_with_special_chars = """
    <html>
    <head><title>Café München</title></head>
    <body><p>Content with special characters: café, naïve, résumé</p></body>
    </html>
    """

    respx_mock.get("https://example.com/article").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html; charset=iso-8859-1"},
            content=html_with_special_chars.encode("iso-8859-1"),
        )
    )

    # Execute enrichment
    result = await trafilatura_enricher.enrich(enricher_context)

    # Should handle encoding gracefully
    assert result.success is True
    assert "webpage_metadata" in result.data


@pytest.mark.asyncio
async def test_http_error_status(trafilatura_enricher, enricher_context, respx_mock):
    """Test handling of HTTP error status codes."""
    respx_mock.get("https://example.com/article").mock(
        return_value=httpx.Response(404, content=b"Not Found")
    )

    # Execute enrichment
    result = await trafilatura_enricher.enrich(enricher_context)

    # Should fail gracefully
    assert result.success is False
    assert result.error is not None
