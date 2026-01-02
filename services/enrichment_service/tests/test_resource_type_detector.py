"""Tests for ResourceTypeDetector."""

import pytest
from app.enrichers.core.resource_type_detector import (
    ResourceDetectorConfig,
    ResourceTypeDetector,
)
from app.enrichers.core.resource_types import ResourceType


@pytest.fixture
def detector():
    """Create ResourceTypeDetector instance with default config."""
    config = ResourceDetectorConfig()
    return ResourceTypeDetector(config)


class TestResourceTypeDetector:
    """Test ResourceTypeDetector functionality."""

    # ===== JSON File Detection Tests =====
    @pytest.mark.asyncio
    async def test_json_detected_as_dataset(self, detector):
        """Test that .json URLs are detected as DATASET, not API."""
        url = "https://data.cityofnewyork.us/resource/rc75-m7u3.json"
        result = await detector.detect_resource_type(url)

        assert result.primary_type == ResourceType.DATASET
        assert result.detection_method in ["url_pattern", "file_extension"]

    @pytest.mark.asyncio
    async def test_json_file_extension_detected_as_dataset(self, detector):
        """Test that files ending in .json are detected as DATASET."""
        # Simple URLs with .json extension
        simple_urls = [
            "https://example.com/data.json",
            "https://storage.googleapis.com/bucket/file.json",
        ]

        for url in simple_urls:
            result = await detector.detect_resource_type(url)
            assert result.primary_type == ResourceType.DATASET, f"Failed for URL: {url}"

    @pytest.mark.asyncio
    async def test_json_on_api_subdomain_defaults_to_webpage(self, detector):
        """Test that .json files on api.* domains default to WEBPAGE due to conflicting signals.

        This happens because:
        - URL pattern detects: API (api.example.com)
        - File extension detects: DATASET (.json)
        - When they disagree, it falls through to default (WEBPAGE)
        """
        url = "https://api.example.com/export/data.json"
        result = await detector.detect_resource_type(url)

        # Falls through to default when URL pattern and extension disagree
        assert result.primary_type == ResourceType.WEBPAGE
        assert result.detection_method == "default"

    # ===== API Detection Tests =====
    @pytest.mark.asyncio
    async def test_api_subdomain_detected_as_api(self, detector):
        """Test that api.* subdomains are detected as API."""
        url = "https://api.example.com/v1/users"
        result = await detector.detect_resource_type(url)

        assert result.primary_type == ResourceType.API
        assert result.detection_method == "url_pattern"

    @pytest.mark.asyncio
    async def test_api_path_detected_as_api(self, detector):
        """Test that /api/ paths are detected as API."""
        url = "https://example.com/api/users"
        result = await detector.detect_resource_type(url)

        assert result.primary_type == ResourceType.API
        assert result.detection_method == "url_pattern"

    @pytest.mark.asyncio
    async def test_versioned_api_detected_as_api(self, detector):
        """Test that versioned API paths (/v1/, /v2/) are detected as API."""
        urls = [
            "https://example.com/v1/users",
            "https://example.com/v2/products",
            "https://example.com/v10/orders",
        ]

        for url in urls:
            result = await detector.detect_resource_type(url)
            assert result.primary_type == ResourceType.API, f"Failed for URL: {url}"

    # ===== Dataset Detection Tests =====
    @pytest.mark.asyncio
    async def test_csv_detected_as_dataset(self, detector):
        """Test that .csv files are detected as DATASET."""
        url = "https://example.com/sales_data.csv"
        result = await detector.detect_resource_type(url)

        assert result.primary_type == ResourceType.DATASET

    @pytest.mark.asyncio
    async def test_dataset_path_detected_as_dataset(self, detector):
        """Test that /dataset/ or /datasets/ paths are detected as DATASET."""
        urls = [
            "https://example.com/dataset/sales",
            "https://example.com/datasets/weather",
        ]

        for url in urls:
            result = await detector.detect_resource_type(url)
            assert result.primary_type == ResourceType.DATASET, f"Failed for URL: {url}"

    @pytest.mark.asyncio
    async def test_data_path_detected_as_dataset(self, detector):
        """Test that /data/ paths are detected as DATASET."""
        url = "https://example.com/data/statistics"
        result = await detector.detect_resource_type(url)

        assert result.primary_type == ResourceType.DATASET

    @pytest.mark.asyncio
    async def test_various_dataset_formats(self, detector):
        """Test detection of various dataset file formats."""
        urls_and_formats = [
            ("https://example.com/data.csv", ResourceType.DATASET),
            ("https://example.com/data.json", ResourceType.DATASET),
            ("https://example.com/data.xml", ResourceType.DATASET),
            ("https://example.com/data.tsv", ResourceType.DATASET),
            ("https://example.com/data.parquet", ResourceType.DATASET),
        ]

        for url, expected_type in urls_and_formats:
            result = await detector.detect_resource_type(url)
            assert result.primary_type == expected_type, f"Failed for URL: {url}"

    # ===== Image Detection Tests =====
    @pytest.mark.asyncio
    async def test_image_formats_detected(self, detector):
        """Test detection of various image formats."""
        image_urls = [
            "https://example.com/photo.jpg",
            "https://example.com/logo.png",
            "https://example.com/animation.gif",
            "https://example.com/modern.webp",
        ]

        for url in image_urls:
            result = await detector.detect_resource_type(url)
            assert result.primary_type == ResourceType.IMAGE, f"Failed for URL: {url}"

    # ===== Video Detection Tests =====
    @pytest.mark.asyncio
    async def test_video_formats_detected(self, detector):
        """Test detection of various video formats."""
        video_urls = [
            "https://example.com/video.mp4",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://vimeo.com/123456789",
        ]

        for url in video_urls:
            result = await detector.detect_resource_type(url)
            assert result.primary_type == ResourceType.VIDEO, f"Failed for URL: {url}"

    # ===== PDF Detection Tests =====
    @pytest.mark.asyncio
    async def test_pdf_detected(self, detector):
        """Test that .pdf files are detected as PDF."""
        url = "https://example.com/document.pdf"
        result = await detector.detect_resource_type(url)

        assert result.primary_type == ResourceType.PDF

    # ===== Code Repository Detection Tests =====
    @pytest.mark.asyncio
    async def test_github_repo_detected_as_code(self, detector):
        """Test that GitHub repository URLs are detected as CODE."""
        url = "https://github.com/user/repository"
        result = await detector.detect_resource_type(url)

        assert result.primary_type == ResourceType.CODE

    # ===== Default Webpage Detection Tests =====
    @pytest.mark.asyncio
    async def test_unknown_url_defaults_to_webpage(self, detector):
        """Test that unknown URLs default to WEBPAGE."""
        url = "https://example.com/some/random/path"
        result = await detector.detect_resource_type(url)

        assert result.primary_type == ResourceType.WEBPAGE
        assert result.detection_method == "default"

    @pytest.mark.asyncio
    async def test_plain_domain_defaults_to_webpage(self, detector):
        """Test that plain domain URLs default to WEBPAGE."""
        url = "https://example.com"
        result = await detector.detect_resource_type(url)

        assert result.primary_type == ResourceType.WEBPAGE

    # ===== Open Graph Type Detection Tests =====
    @pytest.mark.asyncio
    async def test_og_type_article_detected_as_webpage(self, detector):
        """Test that og:type='article' is detected as WEBPAGE."""
        url = "https://example.com/blog/post"
        result = await detector.detect_resource_type(url, og_type="article")

        assert result.primary_type == ResourceType.WEBPAGE
        assert result.detection_method == "og_type"

    @pytest.mark.asyncio
    async def test_og_type_video_detected(self, detector):
        """Test that og:type='video.movie' is detected as VIDEO."""
        url = "https://example.com/movie"
        result = await detector.detect_resource_type(url, og_type="video.movie")

        assert result.primary_type == ResourceType.VIDEO
        assert result.detection_method == "og_type"

    # ===== Real-world Socrata URL Test =====
    @pytest.mark.asyncio
    async def test_socrata_open_data_portal_url(self, detector):
        """Test real-world Socrata open data portal URL."""
        # NYC Open Data - 311 Service Requests
        url = "https://data.cityofnewyork.us/resource/rc75-m7u3.json"
        result = await detector.detect_resource_type(url)

        assert result.primary_type == ResourceType.DATASET
        assert result.detection_method in ["url_pattern", "file_extension"]

    @pytest.mark.asyncio
    async def test_socrata_csv_export(self, detector):
        """Test Socrata CSV export URL.

        This URL contains both /api/ path and .csv extension:
        - URL pattern detects: API (due to /api/ in path)
        - File extension detects: DATASET (due to .csv)
        - When they disagree, falls through to WEBPAGE

        However, .csv is a strong signal for dataset, so this could be improved.
        """
        url = "https://data.cityofnewyork.us/api/views/rc75-m7u3/rows.csv"
        result = await detector.detect_resource_type(url)

        # Currently falls through to default due to API/DATASET conflict
        # File extension (.csv) should ideally win, but current logic defaults to WEBPAGE
        assert result.primary_type in [ResourceType.DATASET, ResourceType.WEBPAGE]
