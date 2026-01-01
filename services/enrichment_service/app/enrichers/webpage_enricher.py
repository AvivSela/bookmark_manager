"""Webpage enricher - extracts HTML metadata from web pages."""

import time
from typing import Optional, Dict, Any

from app.enrichers.base_enricher import BaseEnricher, EnricherContext, EnricherResult
from app.enrichers.resource_types import ResourceType
from app.enrichers.metadata_fetcher import MetadataFetcher


class WebPageEnricher(BaseEnricher):
    """Extract HTML metadata from web pages."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.fetcher = MetadataFetcher()

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
            # Use existing MetadataFetcher to extract metadata
            result = await self.fetcher.fetch_metadata(context.url)
            execution_time = (time.time() - start_time) * 1000

            return EnricherResult(
                enricher=self,
                success=True,
                data={
                    "og_title": result.og_title,
                    "og_description": result.og_description,
                    "og_image": result.og_image,
                    "og_type": result.og_type,
                    "og_site_name": result.og_site_name,
                    "meta_description": result.meta_description,
                    "favicon_url": result.favicon_url,
                },
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self.logger.error(f"Failed to enrich webpage {context.url}: {e}")

            return EnricherResult(
                enricher=self,
                success=False,
                data={},
                error=str(e),
                execution_time_ms=execution_time,
            )

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
        return True
