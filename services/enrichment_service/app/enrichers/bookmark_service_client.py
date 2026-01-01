import httpx
import logging
from typing import Optional
from uuid import UUID
from app.config import get_settings
from app.schemas.enrichment import EnrichmentResult

logger = logging.getLogger(__name__)
settings = get_settings()


class BookmarkServiceClient:
    """HTTP client for communicating with Bookmark Service API.

    Uses connection pooling via shared httpx.AsyncClient for better performance.
    Must be used as an async context manager or manually started/closed.
    """

    def __init__(self):
        self.base_url = settings.bookmark_service_url
        self.timeout = httpx.Timeout(settings.bookmark_service_timeout_seconds)
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry - creates shared client."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - closes client."""
        await self.close()

    async def start(self):
        """Start shared HTTP client with connection pooling."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(
                    max_keepalive_connections=5,
                    max_connections=10,
                    keepalive_expiry=30.0,
                ),
            )

    async def close(self):
        """Close shared HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def update_bookmark_enrichment(
        self, bookmark_id: UUID, tenant_id: str, enrichment_result: EnrichmentResult
    ) -> bool:
        """
        Update bookmark with enrichment data via API.

        Args:
            bookmark_id: Bookmark UUID
            tenant_id: Tenant ID for X-Tenant-ID header
            enrichment_result: EnrichmentResult with metadata

        Returns:
            True if successful

        Raises:
            httpx.HTTPStatusError: On HTTP errors (handled by retry logic)
            httpx.RequestError: On network errors (handled by retry logic)
            RuntimeError: If client not started (call start() or use as context manager)
        """
        if self._client is None:
            raise RuntimeError(
                "Client not started. Use 'async with client:' or call start() first."
            )

        url = f"{self.base_url}/bookmarks/{bookmark_id}"
        headers = {"X-Tenant-ID": tenant_id}

        # Build enrichments object with all enrichment data
        enrichments = {
            "og_title": enrichment_result.og_title,
            "og_description": enrichment_result.og_description,
            "og_image": enrichment_result.og_image,
            "og_type": enrichment_result.og_type,
            "og_site_name": enrichment_result.og_site_name,
            "meta_description": enrichment_result.meta_description,
            "favicon_url": enrichment_result.favicon_url,
            "screenshot_url": enrichment_result.screenshot_url,
            "api_metadata": enrichment_result.api_metadata,
            "dataset_metadata": enrichment_result.dataset_metadata,
            "media_metadata": enrichment_result.media_metadata,
        }

        # Filter out None values to keep JSON clean
        enrichments = {k: v for k, v in enrichments.items() if v is not None}

        payload = {
            "enrichments": enrichments,
            "resource_type": enrichment_result.resource_type,
        }

        logger.debug(f"Sending PUT request to {url} for bookmark {bookmark_id}")

        response = await self._client.put(url, json=payload, headers=headers)

        logger.debug(
            f"Received response: status={response.status_code} "
            f"for bookmark {bookmark_id}"
        )

        response.raise_for_status()

        logger.info(f"Successfully updated bookmark {bookmark_id} via API")
        return True
