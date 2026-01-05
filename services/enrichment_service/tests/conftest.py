from datetime import datetime, timezone
from uuid import uuid4

import pytest
from app.schemas.enrichment import EnrichmentResult
from app.schemas.kafka_events import BookmarkEvent


@pytest.fixture
def sample_html_with_og_tags():
    """HTML with complete Open Graph tags."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta property="og:title" content="Example Page Title" />
        <meta property="og:description" content="This is an example page description" />
        <meta property="og:image" content="https://example.com/image.jpg" />
        <meta property="og:type" content="website" />
        <meta property="og:site_name" content="Example Site" />
        <meta name="description" content="Standard meta description" />
        <link rel="icon" href="/favicon.ico" />
    </head>
    <body>
        <h1>Example Page</h1>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_without_og_tags():
    """HTML with only standard meta tags (no Open Graph)."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="description" content="Standard meta description only" />
        <link rel="shortcut icon" href="/assets/favicon.png" />
    </head>
    <body>
        <h1>Simple Page</h1>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_with_relative_urls():
    """HTML with relative URLs in meta tags."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta property="og:title" content="Relative URLs Test" />
        <meta property="og:image" content="/images/og-image.jpg" />
        <link rel="icon" href="assets/icon.png" />
    </head>
    <body>
        <h1>Relative URLs</h1>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_minimal():
    """Minimal HTML with no meta tags."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Minimal Page</title>
    </head>
    <body>
        <p>No metadata here</p>
    </body>
    </html>
    """


@pytest.fixture
def sample_enrichment_result():
    """Sample EnrichmentResult for testing."""
    return EnrichmentResult(
        og_title="Test Title",
        og_description="Test Description",
        og_image="https://example.com/image.jpg",
        og_type="article",
        og_site_name="Test Site",
        meta_description="Meta description",
        favicon_url="https://example.com/favicon.ico",
        webpage_metadata={
            "text": "Sample extracted text content",
            "title": "Extracted Title",
            "author": "Sample Author",
            "date": "2024-01-15",
            "language": "en",
        },
    )


@pytest.fixture
def sample_bookmark_event():
    """Sample BookmarkEvent for testing consumer."""
    return BookmarkEvent(
        event_id=uuid4(),
        event_type="created",
        timestamp=datetime.now(timezone.utc),
        data={
            "id": str(uuid4()),
            "url": "https://example.com",
            "tenant_id": "test-tenant-123",
            "title": "Example Bookmark",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        metadata={"service": "bookmark-service", "version": "1.0.0"},
    )


@pytest.fixture
def sample_bookmark_event_missing_url():
    """BookmarkEvent missing required URL field."""
    return BookmarkEvent(
        event_id=uuid4(),
        event_type="created",
        timestamp=datetime.now(timezone.utc),
        data={
            "id": str(uuid4()),
            "tenant_id": "test-tenant-123",
            # Missing 'url' field
        },
        metadata={"service": "bookmark-service", "version": "1.0.0"},
    )
