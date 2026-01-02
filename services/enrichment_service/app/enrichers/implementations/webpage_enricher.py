"""Webpage enricher - extracts HTML metadata from web pages."""

import logging
import time
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import get_settings
from app.enrichers.core.base_enricher import (
    BaseEnricher,
    EnricherContext,
    EnricherResult,
)
from app.enrichers.core.resource_types import ResourceType

logger = logging.getLogger(__name__)
settings = get_settings()


class WebPageEnricher(BaseEnricher):
    """Extract HTML metadata from web pages."""

    # Maximum response size: 5MB to prevent memory exhaustion
    MAX_RESPONSE_SIZE = 5 * 1024 * 1024  # 5MB in bytes

    async def enrich(self, context: EnricherContext) -> EnricherResult:
        """
        Enrich webpage by extracting HTML metadata.

        Args:
            context: Enrichment context with URL and metadata

        Returns:
            EnricherResult with Open Graph tags, meta description, favicon
        """
        start_time = time.time()

        try:
            # Fetch and extract metadata
            timeout = httpx.Timeout(settings.enrichment_timeout_seconds)
            headers = {
                "User-Agent": settings.user_agent,
                "Accept": "text/html,application/xhtml+xml",
            }

            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True
            ) as client:
                # Stream response to check size before downloading entire content
                async with client.stream(
                    "GET", context.url, headers=headers
                ) as response:
                    response.raise_for_status()

                    # Only process HTML responses
                    content_type = response.headers.get("content-type", "")
                    if "html" not in content_type.lower():
                        raise ValueError(f"Non-HTML content type: {content_type}")

                    # Check Content-Length header if present
                    content_length = response.headers.get("content-length")
                    if content_length and int(content_length) > self.MAX_RESPONSE_SIZE:
                        raise ValueError(
                            f"Response too large: {content_length} bytes (max {self.MAX_RESPONSE_SIZE})"
                        )

                    # Read response with size limit
                    chunks = []
                    total_size = 0
                    async for chunk in response.aiter_bytes():
                        total_size += len(chunk)
                        if total_size > self.MAX_RESPONSE_SIZE:
                            raise ValueError(
                                f"Response exceeds size limit: {self.MAX_RESPONSE_SIZE} bytes"
                            )
                        chunks.append(chunk)

                    # Decode content
                    html = b"".join(chunks).decode(
                        response.encoding or "utf-8", errors="replace"
                    )
                    soup = BeautifulSoup(html, "lxml")

            # Extract Open Graph tags
            og_title = self._get_meta_tag(soup, "og:title")
            og_description = self._get_meta_tag(soup, "og:description")
            og_image = self._get_meta_tag(soup, "og:image")
            og_type = self._get_meta_tag(soup, "og:type")
            og_site_name = self._get_meta_tag(soup, "og:site_name")

            # Extract standard meta tags (fallback)
            meta_description = self._get_meta_tag(
                soup, "description", property_attr="name"
            )

            # Extract favicon
            favicon_url = self._get_favicon(soup, context.url)

            # Make og_image and favicon absolute URLs
            if og_image:
                og_image = urljoin(context.url, og_image)
            if favicon_url:
                favicon_url = urljoin(context.url, favicon_url)

            execution_time = (time.time() - start_time) * 1000

            return EnricherResult(
                enricher=self,
                success=True,
                data={
                    "og_title": og_title,
                    "og_description": og_description,
                    "og_image": og_image,
                    "og_type": og_type,
                    "og_site_name": og_site_name,
                    "meta_description": meta_description,
                    "favicon_url": favicon_url,
                },
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self.logger.error("Failed to enrich webpage %s: %s", context.url, e)

            return EnricherResult(
                enricher=self,
                success=False,
                data={},
                error=str(e),
                execution_time_ms=execution_time,
            )

    def _get_meta_tag(
        self, soup: BeautifulSoup, property_value: str, property_attr: str = "property"
    ) -> Optional[str]:
        """Extract meta tag content by property/name attribute."""
        tag = soup.find("meta", {property_attr: property_value})
        return tag.get("content") if tag else None

    def _get_favicon(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Extract favicon URL with fallback logic."""
        # Try <link rel="icon">
        icon_link = soup.find(
            "link", rel=lambda x: x and "icon" in x.lower() if x else False
        )
        if icon_link and icon_link.get("href"):
            return icon_link["href"]

        # Fallback: /favicon.ico
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}/favicon.ico"

    def is_applicable(self, resource_type: ResourceType) -> bool:
        """
        WebPageEnricher applies to webpages, APIs (may have docs), and unknown types.

        Args:
            resource_type: Detected resource type

        Returns:
            True if applicable
        """
        return resource_type in {
            ResourceType.WEBPAGE,
            ResourceType.UNKNOWN,
            ResourceType.API,  # APIs may have HTML documentation
        }

    @property
    def name(self) -> str:
        """Enricher name."""
        return "webpage"

    @property
    def required(self) -> bool:
        """WebPageEnricher is required (core enrichment)."""
        return False
