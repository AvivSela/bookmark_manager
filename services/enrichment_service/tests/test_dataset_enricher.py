"""Tests for DatasetEnricher."""

import httpx
import pytest
from app.enrichers.core.base_enricher import EnricherContext
from app.enrichers.core.resource_types import ResourceType
from app.enrichers.implementations.dataset_enricher import DatasetEnricher


@pytest.fixture
def dataset_enricher():
    """Create DatasetEnricher instance."""
    return DatasetEnricher()


@pytest.fixture
def enricher_context():
    """Create enricher context for testing."""
    return EnricherContext(
        url="https://example.com/data.csv",
        bookmark_id="test-bookmark-id",
        tenant_id="test-tenant-id",
        resource_type=ResourceType.DATASET,
        timeout=15.0,
    )


@pytest.fixture
def kaggle_html():
    """Sample Kaggle dataset page HTML."""
    return """
    <html>
        <head><title>Test Dataset</title></head>
        <body>
            <h1>Test Dataset Title</h1>
            <div class="dataset-description">This is a test dataset description.</div>
        </body>
    </html>
    """


@pytest.fixture
def data_gov_html():
    """Sample data.gov dataset page HTML."""
    return """
    <html>
        <head><title>Government Dataset</title></head>
        <body>
            <h1>Government Dataset Title</h1>
            <div class="notes">This dataset contains government data.</div>
        </body>
    </html>
    """


class TestDatasetEnricher:
    """Test DatasetEnricher functionality."""

    def test_enricher_name(self, dataset_enricher):
        """Test enricher name property."""
        assert dataset_enricher.name == "dataset"

    def test_enricher_not_required(self, dataset_enricher):
        """Test enricher is not required."""
        assert dataset_enricher.required is False

    def test_is_applicable_for_dataset_type(self, dataset_enricher):
        """Test enricher applies to DATASET resource type."""
        assert dataset_enricher.is_applicable(ResourceType.DATASET) is True

    def test_not_applicable_for_other_types(self, dataset_enricher):
        """Test enricher doesn't apply to non-dataset types."""
        assert dataset_enricher.is_applicable(ResourceType.WEBPAGE) is False
        assert dataset_enricher.is_applicable(ResourceType.API) is False
        assert dataset_enricher.is_applicable(ResourceType.IMAGE) is False

    def test_detect_kaggle_platform(self, dataset_enricher):
        """Test detection of Kaggle datasets."""
        kaggle_url = "https://www.kaggle.com/datasets/user/dataset-name"
        platform = dataset_enricher._detect_platform(kaggle_url)
        assert platform == "kaggle"

    def test_detect_data_gov_platform(self, dataset_enricher):
        """Test detection of data.gov datasets."""
        data_gov_url = "https://data.gov/dataset/test-dataset"
        platform = dataset_enricher._detect_platform(data_gov_url)
        assert platform == "data_gov"

    def test_detect_github_platform(self, dataset_enricher):
        """Test detection of GitHub data files."""
        github_url = "https://github.com/user/repo/blob/main/data.csv"
        platform = dataset_enricher._detect_platform(github_url)
        assert platform == "github"

    def test_detect_unknown_platform(self, dataset_enricher):
        """Test detection returns None for unknown platforms."""
        unknown_url = "https://example.com/data.csv"
        platform = dataset_enricher._detect_platform(unknown_url)
        assert platform is None

    def test_extract_format_from_url(self, dataset_enricher):
        """Test format detection from file extension."""
        assert (
            dataset_enricher._detect_format_from_url("https://example.com/data.csv")
            == "csv"
        )
        assert (
            dataset_enricher._detect_format_from_url("https://example.com/data.json")
            == "json"
        )
        assert (
            dataset_enricher._detect_format_from_url("https://example.com/data.parquet")
            == "parquet"
        )
        assert (
            dataset_enricher._detect_format_from_url("https://example.com/data.xml")
            == "xml"
        )
        assert (
            dataset_enricher._detect_format_from_url("https://example.com/noextension")
            is None
        )

    def test_content_type_to_format(self, dataset_enricher):
        """Test Content-Type to format mapping."""
        assert dataset_enricher._content_type_to_format("text/csv") == "csv"
        assert dataset_enricher._content_type_to_format("application/json") == "json"
        assert dataset_enricher._content_type_to_format("text/xml") == "xml"
        assert (
            dataset_enricher._content_type_to_format("application/x-parquet")
            == "parquet"
        )
        assert dataset_enricher._content_type_to_format("text/html") is None

    def test_format_file_size(self, dataset_enricher):
        """Test file size formatting."""
        assert dataset_enricher._format_file_size(500) == "500.0 B"
        assert dataset_enricher._format_file_size(1024) == "1.0 KB"
        assert dataset_enricher._format_file_size(1024 * 1024) == "1.0 MB"
        assert dataset_enricher._format_file_size(1024 * 1024 * 1024) == "1.0 GB"

    @pytest.mark.asyncio
    async def test_extract_kaggle_metadata(
        self, dataset_enricher, enricher_context, kaggle_html, respx_mock
    ):
        """Test extracting metadata from Kaggle dataset page."""
        enricher_context.url = "https://www.kaggle.com/datasets/user/test-dataset"

        # Mock GET request to return Kaggle HTML
        respx_mock.get("https://www.kaggle.com/datasets/user/test-dataset").mock(
            return_value=httpx.Response(200, text=kaggle_html)
        )

        # Test enrichment
        result = await dataset_enricher.enrich(enricher_context)

        assert result.success is True
        assert "dataset_metadata" in result.data

        metadata = result.data["dataset_metadata"]
        assert metadata["platform"] == "kaggle"
        assert "Test Dataset Title" in metadata.get("title", "")
        assert "test dataset description" in metadata.get("description", "")

    @pytest.mark.asyncio
    async def test_extract_data_gov_metadata(
        self, dataset_enricher, enricher_context, data_gov_html, respx_mock
    ):
        """Test extracting metadata from data.gov dataset page."""
        enricher_context.url = "https://data.gov/dataset/test-dataset"

        # Mock GET request to return data.gov HTML
        respx_mock.get("https://data.gov/dataset/test-dataset").mock(
            return_value=httpx.Response(200, text=data_gov_html)
        )

        # Test enrichment
        result = await dataset_enricher.enrich(enricher_context)

        assert result.success is True
        metadata = result.data["dataset_metadata"]
        assert metadata["platform"] == "data_gov"
        assert "Government Dataset Title" in metadata.get("title", "")

    @pytest.mark.asyncio
    async def test_generic_fallback_with_head_request(
        self, dataset_enricher, enricher_context, respx_mock
    ):
        """Test generic metadata extraction for unknown platforms."""
        # Mock HEAD request
        respx_mock.head("https://example.com/data.csv").mock(
            return_value=httpx.Response(
                200,
                headers={
                    "content-type": "text/csv",
                    "content-length": "1048576",
                },
            )
        )

        # Test enrichment
        result = await dataset_enricher.enrich(enricher_context)

        assert result.success is True
        metadata = result.data["dataset_metadata"]
        assert metadata["platform"] == "unknown"
        assert metadata["format"] == "csv"
        assert "1.0 MB" in metadata.get("size", "")

    @pytest.mark.asyncio
    async def test_network_error_handling(
        self, dataset_enricher, enricher_context, respx_mock
    ):
        """Test handling of network errors with graceful degradation."""
        # Mock request to raise network error
        respx_mock.head("https://example.com/data.csv").mock(
            side_effect=httpx.ConnectError("Connection failed")
        )

        # Test enrichment - should still succeed with URL-based format detection
        result = await dataset_enricher.enrich(enricher_context)

        # DatasetEnricher gracefully degrades to URL-based detection
        assert result.success is True
        metadata = result.data["dataset_metadata"]
        assert metadata["platform"] == "unknown"
        assert metadata["format"] == "csv"  # Extracted from URL
