"""Image enricher - extracts basic image metadata with minimal bandwidth usage."""

import time
import httpx
import logging
import io
from typing import Optional, Dict, Any
from PIL import Image

from app.enrichers.core.base_enricher import (
    BaseEnricher,
    EnricherContext,
    EnricherResult,
)
from app.enrichers.core.resource_types import ResourceType
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ImageEnricher(BaseEnricher):
    """Extract basic image metadata using HTTP headers and minimal parsing."""

    # Maximum header size to fetch (enough for most image headers)
    MAX_HEADER_SIZE = settings.image_max_header_size

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)

    async def enrich(self, context: EnricherContext) -> EnricherResult:
        """
        Enrich image by extracting basic metadata with minimal bandwidth.

        Strategy:
        1. Use HEAD request to get Content-Type and Content-Length
        2. Use Range request to fetch first 32KB (image headers)
        3. Parse headers with Pillow to extract dimensions and format
        4. Fallback to HEAD-only if Range not supported

        Args:
            context: Enrichment context with URL and metadata

        Returns:
            EnricherResult with image metadata
        """
        start_time = time.time()

        try:
            # Step 1: Get basic metadata from HEAD request
            basic_metadata = await self._get_basic_metadata(context.url)

            # Step 2: Try to extract dimensions from image headers
            dimensions = None
            if basic_metadata.get("content_type", "").startswith("image/"):
                dimensions = await self._extract_dimensions(context.url)

            # Step 3: Build result
            metadata = {
                "type": "image",
                "content_type": basic_metadata.get("content_type"),
                "file_size_bytes": basic_metadata.get("file_size"),
            }

            # Add dimensions if successfully extracted
            if dimensions:
                metadata.update(
                    {
                        "format": dimensions.get("format"),
                        "width": dimensions.get("width"),
                        "height": dimensions.get("height"),
                    }
                )

            execution_time = (time.time() - start_time) * 1000

            return EnricherResult(
                enricher=self,
                success=True,
                data={"media_metadata": metadata},
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self.logger.error(f"Failed to enrich image {context.url}: {e}")

            return EnricherResult(
                enricher=self,
                success=False,
                data={},
                error=str(e),
                execution_time_ms=execution_time,
            )

    async def _get_basic_metadata(self, url: str) -> Dict[str, Any]:
        """
        Use HEAD request to get Content-Type and Content-Length.

        Args:
            url: Image URL

        Returns:
            Dict with content_type and file_size
        """
        timeout = httpx.Timeout(settings.image_timeout_seconds)
        headers = {"User-Agent": settings.user_agent}

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.head(url, headers=headers)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            file_size = response.headers.get("content-length")

            return {
                "content_type": content_type,
                "file_size": int(file_size) if file_size else None,
            }

    async def _extract_dimensions(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Fetch image header bytes using Range request and extract dimensions.

        Args:
            url: Image URL

        Returns:
            Dict with width, height, format or None if extraction fails
        """
        try:
            timeout = httpx.Timeout(settings.image_timeout_seconds)
            headers = {
                "User-Agent": settings.user_agent,
                "Range": f"bytes=0-{self.MAX_HEADER_SIZE - 1}",
            }

            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True
            ) as client:
                response = await client.get(url, headers=headers)

                # Accept both 206 (Partial Content) and 200 (full file if small)
                if response.status_code not in (200, 206):
                    self.logger.warning(
                        f"Range request failed with status {response.status_code}, "
                        f"using HEAD-only metadata"
                    )
                    return None

                # Parse image with Pillow
                image_bytes = io.BytesIO(response.content)
                img = Image.open(image_bytes)

                return {
                    "width": img.width,
                    "height": img.height,
                    "format": img.format.lower() if img.format else None,
                }

        except Exception as e:
            self.logger.warning(
                f"Failed to extract dimensions for {url}: {e}. "
                f"Returning basic metadata only."
            )
            return None

    def is_applicable(self, resource_type: ResourceType) -> bool:
        """
        ImageEnricher applies only to IMAGE resource types.

        Args:
            resource_type: Detected resource type

        Returns:
            True if resource is IMAGE
        """
        return resource_type == ResourceType.IMAGE

    @property
    def name(self) -> str:
        """Enricher name."""
        return "image"

    @property
    def required(self) -> bool:
        """ImageEnricher is optional (not required)."""
        return False

    @property
    def timeout(self) -> float:
        """Timeout for image enrichment."""
        return self.config.get("timeout", settings.image_timeout_seconds)
