import httpx
import logging
from uuid import UUID
from app.config import get_settings
from app.schemas.enrichment import EnrichmentResult

logger = logging.getLogger(__name__)
settings = get_settings()


class BookmarkServiceClient:
    """HTTP client for communicating with Bookmark Service API."""

    def __init__(self):
        self.base_url = settings.bookmark_service_url
        self.timeout = httpx.Timeout(settings.bookmark_service_timeout_seconds)

    async def update_bookmark_enrichment(
        self, bookmark_id: UUID, user_id: str, enrichment_result: EnrichmentResult
    ) -> bool:
        """
        Update bookmark with enrichment data via API.

        Args:
            bookmark_id: Bookmark UUID
            user_id: User ID for X-User-ID header
            enrichment_result: EnrichmentResult with metadata

        Returns:
            True if successful

        Raises:
            httpx.HTTPStatusError: On HTTP errors (handled by retry logic)
            httpx.RequestError: On network errors (handled by retry logic)
        """
        url = f"{self.base_url}/bookmarks/{bookmark_id}"
        headers = {"X-User-ID": user_id}

        payload = {
            "og_title": enrichment_result.og_title,
            "og_description": enrichment_result.og_description,
            "og_image": enrichment_result.og_image,
            "og_type": enrichment_result.og_type,
            "og_site_name": enrichment_result.og_site_name,
            "meta_description": enrichment_result.meta_description,
            "favicon_url": enrichment_result.favicon_url,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.put(url, json=payload, headers=headers)
            response.raise_for_status()

            logger.info(f"Successfully updated bookmark {bookmark_id} via API")
            return True
