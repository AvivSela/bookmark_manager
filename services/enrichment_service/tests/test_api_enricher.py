"""Tests for ApiEnricher."""

import pytest
import httpx

from app.enrichers.implementations.api_enricher import ApiEnricher
from app.enrichers.core.base_enricher import EnricherContext
from app.enrichers.core.resource_types import ResourceType


@pytest.fixture
def api_enricher():
    """Create ApiEnricher instance."""
    return ApiEnricher()


@pytest.fixture
def enricher_context():
    """Create enricher context for testing."""
    return EnricherContext(
        url="https://api.example.com/",
        bookmark_id="test-bookmark-id",
        tenant_id="test-tenant-id",
        resource_type=ResourceType.API,
        timeout=10.0,
    )


@pytest.fixture
def openapi_3_spec():
    """Sample OpenAPI 3.0 specification."""
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "Test API",
            "version": "1.0.0",
            "description": "Test API description",
        },
        "servers": [{"url": "https://api.example.com"}],
        "paths": {
            "/users": {
                "get": {"summary": "List users"},
                "post": {"summary": "Create user"},
            },
            "/posts": {
                "get": {"summary": "List posts"},
            },
        },
        "components": {
            "securitySchemes": {
                "apiKey": {"type": "apiKey", "in": "header", "name": "X-API-Key"}
            }
        },
        "tags": [{"name": "users"}, {"name": "posts"}],
    }


@pytest.fixture
def swagger_2_spec():
    """Sample Swagger 2.0 specification."""
    return {
        "swagger": "2.0",
        "info": {
            "title": "Legacy API",
            "version": "2.0.0",
            "description": "Legacy API description",
        },
        "host": "api.example.com",
        "schemes": ["https"],
        "basePath": "/v2",
        "paths": {
            "/items": {
                "get": {"summary": "List items"},
            },
        },
        "securityDefinitions": {"oauth2": {"type": "oauth2", "flow": "implicit"}},
    }


@pytest.fixture
def api_docs_html():
    """Sample API documentation HTML."""
    return """
    <html>
        <head>
            <title>Test API Documentation</title>
            <meta name="description" content="API for testing">
        </head>
        <body>
            <h1>Test API Documentation</h1>
            <div>Version: 1.5.0</div>
        </body>
    </html>
    """


class TestApiEnricher:
    """Test ApiEnricher functionality."""

    def test_enricher_name(self, api_enricher):
        """Test enricher name property."""
        assert api_enricher.name == "api"

    def test_enricher_not_required(self, api_enricher):
        """Test enricher is not required."""
        assert api_enricher.required is False

    def test_is_applicable_for_api_type(self, api_enricher):
        """Test enricher applies to API resource type."""
        assert api_enricher.is_applicable(ResourceType.API) is True

    def test_not_applicable_for_other_types(self, api_enricher):
        """Test enricher doesn't apply to non-API types."""
        assert api_enricher.is_applicable(ResourceType.WEBPAGE) is False
        assert api_enricher.is_applicable(ResourceType.IMAGE) is False
        assert api_enricher.is_applicable(ResourceType.DATASET) is False

    @pytest.mark.asyncio
    async def test_detect_openapi_spec(
        self, api_enricher, enricher_context, respx_mock
    ):
        """Test detection of OpenAPI spec."""
        # Mock HEAD requests - fail for first paths, succeed for /openapi.json
        respx_mock.head("https://api.example.com/openapi.json").mock(
            return_value=httpx.Response(
                200, headers={"content-type": "application/json"}
            )
        )

        # Test spec detection
        spec_url = await api_enricher._find_openapi_spec(enricher_context.url)

        assert spec_url == "https://api.example.com/openapi.json"

    @pytest.mark.asyncio
    async def test_parse_openapi_3_spec(
        self, api_enricher, enricher_context, openapi_3_spec, respx_mock
    ):
        """Test parsing OpenAPI 3.0 specification."""
        # Mock HEAD request to find spec
        respx_mock.head("https://api.example.com/openapi.json").mock(
            return_value=httpx.Response(
                200, headers={"content-type": "application/json"}
            )
        )

        # Mock GET request to fetch spec
        respx_mock.get("https://api.example.com/openapi.json").mock(
            return_value=httpx.Response(200, json=openapi_3_spec)
        )

        # Test enrichment
        result = await api_enricher.enrich(enricher_context)

        assert result.success is True
        assert "api_metadata" in result.data

        metadata = result.data["api_metadata"]
        assert metadata["spec_version"] == "3.0.0"
        assert metadata["api_title"] == "Test API"
        assert metadata["api_version"] == "1.0.0"
        assert metadata["description"] == "Test API description"
        assert metadata["base_url"] == "https://api.example.com"
        assert metadata["endpoint_count"] == 3  # 2 for /users + 1 for /posts
        assert "apiKey" in metadata["auth_methods"]
        assert "users" in metadata["tags"]
        assert "posts" in metadata["tags"]

    @pytest.mark.asyncio
    async def test_parse_swagger_2_spec(
        self, api_enricher, enricher_context, swagger_2_spec, respx_mock
    ):
        """Test parsing Swagger 2.0 specification."""
        # Mock HEAD request to find spec
        respx_mock.head("https://api.example.com/swagger.json").mock(
            return_value=httpx.Response(
                200, headers={"content-type": "application/json"}
            )
        )

        # Mock GET request to fetch spec
        respx_mock.get("https://api.example.com/swagger.json").mock(
            return_value=httpx.Response(200, json=swagger_2_spec)
        )

        # Test enrichment
        result = await api_enricher.enrich(enricher_context)

        assert result.success is True
        metadata = result.data["api_metadata"]
        assert metadata["spec_version"] == "swagger-2.0"
        assert metadata["api_title"] == "Legacy API"
        assert metadata["base_url"] == "https://api.example.com/v2"
        assert metadata["endpoint_count"] == 1
        assert "oauth2" in metadata["auth_methods"]

    @pytest.mark.asyncio
    async def test_parse_yaml_spec(
        self, api_enricher, enricher_context, openapi_3_spec, respx_mock
    ):
        """Test parsing YAML OpenAPI spec."""
        import yaml

        # Mock HEAD requests - fail for .json paths, succeed for /api-docs which will return YAML
        respx_mock.head("https://api.example.com/openapi.json").mock(
            return_value=httpx.Response(404)
        )
        respx_mock.head("https://api.example.com/swagger.json").mock(
            return_value=httpx.Response(404)
        )
        respx_mock.head("https://api.example.com/api-docs").mock(
            return_value=httpx.Response(
                200, headers={"content-type": "application/x-yaml"}
            )
        )

        # Mock GET request to fetch YAML spec from /api-docs
        yaml_content = yaml.dump(openapi_3_spec)
        respx_mock.get("https://api.example.com/api-docs").mock(
            return_value=httpx.Response(
                200,
                text=yaml_content,
                headers={"content-type": "application/x-yaml"},
            )
        )

        # Test enrichment
        result = await api_enricher.enrich(enricher_context)

        assert result.success is True
        metadata = result.data["api_metadata"]
        # The YAML should have been parsed successfully
        assert metadata["api_title"] == "Test API"
        assert metadata["spec_url"] == "https://api.example.com/api-docs"

    @pytest.mark.asyncio
    async def test_html_fallback(
        self, api_enricher, enricher_context, api_docs_html, respx_mock
    ):
        """Test HTML scraping fallback when no spec found."""
        # Mock HEAD requests to return 404 for all spec paths
        respx_mock.head(url__regex=r".*/(openapi|swagger|api-docs).*").mock(
            return_value=httpx.Response(404)
        )

        # Mock GET request to return HTML documentation
        respx_mock.get("https://api.example.com/").mock(
            return_value=httpx.Response(200, text=api_docs_html)
        )

        # Test enrichment
        result = await api_enricher.enrich(enricher_context)

        assert result.success is True
        metadata = result.data["api_metadata"]
        assert metadata["api_title"] == "Test API Documentation"
        assert metadata["api_version"] == "1.5.0"

    @pytest.mark.asyncio
    async def test_no_spec_found(self, api_enricher, enricher_context, respx_mock):
        """Test handling when no OpenAPI spec exists."""
        # Mock all HEAD requests to return 404
        respx_mock.head(url__regex=r".*").mock(return_value=httpx.Response(404))

        # Mock GET request for HTML fallback (but return minimal HTML)
        respx_mock.get("https://api.example.com/").mock(
            return_value=httpx.Response(200, text="<html><body></body></html>")
        )

        # Test enrichment
        result = await api_enricher.enrich(enricher_context)

        # Should still succeed but with minimal metadata
        assert result.success is True
        assert "api_metadata" in result.data

    @pytest.mark.asyncio
    async def test_network_error_handling(
        self, api_enricher, enricher_context, respx_mock
    ):
        """Test handling of network errors with graceful degradation."""
        # Mock all requests to raise network error
        respx_mock.head(url__regex=r".*").mock(
            side_effect=httpx.ConnectError("Connection failed")
        )
        respx_mock.get(url__regex=r".*").mock(
            side_effect=httpx.ConnectError("Connection failed")
        )

        # Test enrichment - should still succeed with empty metadata (graceful degradation)
        result = await api_enricher.enrich(enricher_context)

        # ApiEnricher gracefully degrades when all network operations fail
        assert result.success is True
        assert "api_metadata" in result.data
        # Metadata will be empty but enricher doesn't fail
        assert result.data["api_metadata"] == {}
