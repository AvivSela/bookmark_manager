"""Trafilatura enricher - extracts content and metadata using trafilatura."""

import logging
import time
from typing import Any, Dict

import httpx
from lxml.etree import _Element
from trafilatura import bare_extraction

from app.config import get_settings
from app.enrichers.core.base_enricher import (
    BaseEnricher,
    EnricherContext,
    EnricherResult,
)
from app.enrichers.core.resource_types import ResourceType

logger = logging.getLogger(__name__)
settings = get_settings()


class TrafilaturaEnricher(BaseEnricher):
    """Extract webpage content and metadata using trafilatura."""

    # Maximum response size: 5MB to prevent memory exhaustion
    MAX_RESPONSE_SIZE = 5 * 1024 * 1024  # 5MB in bytes

    def _make_json_serializable(self, obj: Any) -> Any:
        """
        Recursively convert non-JSON-serializable objects to serializable forms.

        Handles lxml Elements and other non-serializable types that trafilatura
        may return in its extraction results.

        Args:
            obj: Object to convert

        Returns:
            JSON-serializable version of the object
        """
        if isinstance(obj, _Element):
            # Convert lxml Element to string representation
            return str(obj.text) if obj.text else None
        elif isinstance(obj, dict):
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        else:
            # Fallback: convert to string
            return str(obj)

    async def enrich(self, context: EnricherContext) -> EnricherResult:
        """
        Enrich webpage by extracting content and metadata using trafilatura.

        Args:
            context: Enrichment context with URL and metadata

        Returns:
            EnricherResult with extracted webpage content metadata
        """
        start_time = time.time()

        try:
            # Fetch HTML content
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

            # Extract metadata using trafilatura
            extracted = bare_extraction(
                html,
                url=context.url,
                include_comments=False,  # Skip comment sections
                include_tables=True,  # Preserve structured data
                include_images=True,  # Capture image URLs
                include_links=False,  # Skip links to reduce noise
                deduplicate=True,  # Remove duplicate content
                output_format="python",  # Return Python objects
                as_dict=True,  # Return dict instead of Document
            )

            # Handle None result (extraction failed)
            if extracted is None:
                self.logger.warning(
                    "Trafilatura extraction returned None for %s", context.url
                )
                extracted = {}

            # Ensure all data is JSON-serializable (convert lxml Elements, etc.)
            extracted = self._make_json_serializable(extracted)

            # Filter out None values for cleaner storage
            metadata = {k: v for k, v in extracted.items() if v is not None}

            execution_time = (time.time() - start_time) * 1000

            self.logger.info(
                "Trafilatura extracted %d fields from %s in %.2fms",
                len(metadata),
                context.url,
                execution_time,
            )

            return EnricherResult(
                enricher=self,
                success=True,
                data={"webpage_metadata": metadata},
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self.logger.error(
                "Trafilatura enrichment failed for %s: %s",
                context.url,
                e,
                exc_info=True,
            )

            return EnricherResult(
                enricher=self,
                success=False,
                data={},
                error=str(e),
                execution_time_ms=execution_time,
            )

    def is_applicable(self, resource_type: ResourceType) -> bool:
        """
        TrafilaturaEnricher applies only to WEBPAGE resource type.

        Unlike WebPageEnricher which also handles API and UNKNOWN types,
        TrafilaturaEnricher is specifically for webpage content extraction.

        Args:
            resource_type: Detected resource type

        Returns:
            True if resource type is WEBPAGE
        """
        return resource_type == ResourceType.WEBPAGE

    @property
    def name(self) -> str:
        """Enricher name for registry."""
        return "trafilatura"

    @property
    def required(self) -> bool:
        """TrafilaturaEnricher is not required (optional enhancement)."""
        return False
