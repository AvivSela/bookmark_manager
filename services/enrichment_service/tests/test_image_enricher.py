"""Tests for ImageEnricher."""

import pytest
import httpx
import io
from PIL import Image
from unittest.mock import AsyncMock

from app.enrichers.implementations.image_enricher import ImageEnricher
from app.enrichers.core.base_enricher import EnricherContext
from app.enrichers.core.resource_types import ResourceType


@pytest.fixture
def image_enricher():
    """Create ImageEnricher instance."""
    return ImageEnricher()


@pytest.fixture
def enricher_context():
    """Create enricher context for testing."""
    return EnricherContext(
        url="https://example.com/image.jpg",
        bookmark_id="test-bookmark-id",
        tenant_id="test-tenant-id",
        resource_type=ResourceType.IMAGE,
        timeout=10.0,
    )


@pytest.fixture
def sample_jpeg_bytes():
    """Create minimal JPEG image bytes for testing."""
    # Create a small JPEG image
    img = Image.new("RGB", (800, 600), color="red")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture
def sample_png_bytes():
    """Create minimal PNG image bytes for testing."""
    # Create a small PNG image
    img = Image.new("RGB", (1920, 1080), color="blue")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


class TestImageEnricher:
    """Test ImageEnricher functionality."""

    def test_enricher_name(self, image_enricher):
        """Test enricher name property."""
        assert image_enricher.name == "image"

    def test_enricher_not_required(self, image_enricher):
        """Test enricher is not required."""
        assert image_enricher.required is False

    def test_is_applicable_for_image_type(self, image_enricher):
        """Test enricher applies to IMAGE resource type."""
        assert image_enricher.is_applicable(ResourceType.IMAGE) is True

    def test_not_applicable_for_other_types(self, image_enricher):
        """Test enricher doesn't apply to non-image types."""
        assert image_enricher.is_applicable(ResourceType.WEBPAGE) is False
        assert image_enricher.is_applicable(ResourceType.API) is False
        assert image_enricher.is_applicable(ResourceType.DATASET) is False
        assert image_enricher.is_applicable(ResourceType.VIDEO) is False

    @pytest.mark.asyncio
    async def test_extract_jpeg_metadata(
        self, image_enricher, enricher_context, sample_jpeg_bytes, respx_mock
    ):
        """Test extracting metadata from JPEG image."""
        # Mock HEAD request
        respx_mock.head("https://example.com/image.jpg").mock(
            return_value=httpx.Response(
                200,
                headers={
                    "content-type": "image/jpeg",
                    "content-length": str(len(sample_jpeg_bytes)),
                },
            )
        )

        # Mock Range request
        respx_mock.get("https://example.com/image.jpg").mock(
            return_value=httpx.Response(
                206,  # Partial Content
                headers={"content-range": f"bytes 0-{len(sample_jpeg_bytes)-1}/{len(sample_jpeg_bytes)}"},
                content=sample_jpeg_bytes[:32768],  # First 32KB
            )
        )

        # Test enrichment
        result = await image_enricher.enrich(enricher_context)

        assert result.success is True
        assert "media_metadata" in result.data

        metadata = result.data["media_metadata"]
        assert metadata["type"] == "image"
        assert metadata["format"] == "jpeg"
        assert metadata["width"] == 800
        assert metadata["height"] == 600
        assert metadata["content_type"] == "image/jpeg"
        assert metadata["file_size_bytes"] == len(sample_jpeg_bytes)

    @pytest.mark.asyncio
    async def test_extract_png_metadata(
        self, image_enricher, enricher_context, sample_png_bytes, respx_mock
    ):
        """Test extracting metadata from PNG image."""
        enricher_context.url = "https://example.com/image.png"

        # Mock HEAD request
        respx_mock.head("https://example.com/image.png").mock(
            return_value=httpx.Response(
                200,
                headers={
                    "content-type": "image/png",
                    "content-length": str(len(sample_png_bytes)),
                },
            )
        )

        # Mock Range request
        respx_mock.get("https://example.com/image.png").mock(
            return_value=httpx.Response(
                206,
                headers={"content-range": f"bytes 0-{len(sample_png_bytes)-1}/{len(sample_png_bytes)}"},
                content=sample_png_bytes[:32768],
            )
        )

        # Test enrichment
        result = await image_enricher.enrich(enricher_context)

        assert result.success is True
        metadata = result.data["media_metadata"]
        assert metadata["format"] == "png"
        assert metadata["width"] == 1920
        assert metadata["height"] == 1080

    @pytest.mark.asyncio
    async def test_head_request_fallback(
        self, image_enricher, enricher_context, respx_mock
    ):
        """Test fallback to HEAD when Range not supported."""
        # Mock HEAD request
        respx_mock.head("https://example.com/image.jpg").mock(
            return_value=httpx.Response(
                200,
                headers={
                    "content-type": "image/jpeg",
                    "content-length": "102400",
                },
            )
        )

        # Mock Range request returning 416 (Range Not Satisfiable)
        respx_mock.get("https://example.com/image.jpg").mock(
            return_value=httpx.Response(416)
        )

        # Test enrichment
        result = await image_enricher.enrich(enricher_context)

        assert result.success is True
        metadata = result.data["media_metadata"]
        assert metadata["type"] == "image"
        assert metadata["content_type"] == "image/jpeg"
        assert metadata["file_size_bytes"] == 102400
        # Width and height should not be present (fallback mode)
        assert "width" not in metadata or metadata["width"] is None
        assert "height" not in metadata or metadata["height"] is None

    @pytest.mark.asyncio
    async def test_network_error_handling(
        self, image_enricher, enricher_context, respx_mock
    ):
        """Test handling of network errors."""
        # Mock HEAD request to raise network error
        respx_mock.head("https://example.com/image.jpg").mock(
            side_effect=httpx.ConnectError("Connection failed")
        )

        # Test enrichment
        result = await image_enricher.enrich(enricher_context)

        assert result.success is False
        assert result.error is not None
        assert "Connection failed" in result.error
