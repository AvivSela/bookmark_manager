"""Orchestrates parallel enrichment across multiple enrichers."""

import asyncio
import logging
from typing import Any, Dict, List

from app.enrichers.core.base_enricher import (
    BaseEnricher,
    EnricherContext,
    EnricherResult,
)
from app.enrichers.core.enricher_registry import registry
from app.enrichers.core.resource_type_detector import ResourceTypeDetector
from app.enrichers.core.resource_types import ResourceType
from app.enrichers.implementations.webpage_enricher import WebPageEnricher
from app.schemas.enrichment import EnrichmentResult

logger = logging.getLogger(__name__)


class EnrichmentOrchestrator:
    """Orchestrates parallel enrichment across multiple enrichers."""

    def __init__(self, detector: ResourceTypeDetector, config: Dict[str, Any]):
        self.detector = detector
        self.config = config
        self.enabled_enrichers = config.get("enabled_enrichers", ["webpage"])
        self.enrichment_timeout = config.get("enrichment_timeout_seconds", 10.0)

        # Register default enrichers
        self._register_default_enrichers()

    def _register_default_enrichers(self):
        """Register default enrichers with the registry."""
        # Register WebPageEnricher
        if "webpage" not in registry.list_enrichers():
            registry.register(WebPageEnricher)

        # Register ImageEnricher
        if "image" not in registry.list_enrichers():
            from app.enrichers.implementations.image_enricher import ImageEnricher

            registry.register(ImageEnricher)

        # Register DatasetEnricher
        if "dataset" not in registry.list_enrichers():
            from app.enrichers.implementations.dataset_enricher import DatasetEnricher

            registry.register(DatasetEnricher)

        # Register ApiEnricher
        if "api" not in registry.list_enrichers():
            from app.enrichers.implementations.api_enricher import ApiEnricher

            registry.register(ApiEnricher)

    def _select_enrichers(self, resource_type: "ResourceType") -> list["BaseEnricher"]:
        """
        Select applicable enrichers for the resource type with fallback logic.

        Args:
            resource_type: Detected resource type enum

        Returns:
            List of enrichers to run (guaranteed non-empty due to fallback)
        """
        # Select applicable enrichers
        enrichers = registry.get_applicable_enrichers(
            resource_type, self.enabled_enrichers, self.config
        )

        if not enrichers:
            logger.warning(
                f"No applicable enrichers for type {resource_type.value}, "
                f"using webpage enricher as fallback"
            )
            # Fallback to webpage enricher
            enrichers = [registry.get_enricher("webpage", self.config)]

        logger.info(
            f"Running {len(enrichers)} enrichers: {[e.name for e in enrichers]}"
        )

        return enrichers

    async def _execute_enrichers(
        self,
        enrichers: List[BaseEnricher],
        url: str,
        bookmark_id: str,
        tenant_id: str,
        resource_type: "ResourceType",
    ) -> List[EnricherResult]:
        """
        Execute enrichers in parallel and return results.

        Args:
            enrichers: List of enrichers to run
            url: Bookmark URL
            bookmark_id: Bookmark ID
            tenant_id: Tenant ID
            resource_type: Resource type for context

        Returns:
            List of EnricherResult from all enrichers
        """
        # Create enrichment context
        context = EnricherContext(
            url=url,
            bookmark_id=bookmark_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            timeout=self.enrichment_timeout,
        )

        # Run enrichers in parallel with safe wrapper
        tasks = [enricher.enrich_safe(context) for enricher in enrichers]
        results: List[EnricherResult] = await asyncio.gather(*tasks)

        return results

    async def enrich_bookmark(
        self, url: str, bookmark_id: str, tenant_id: str
    ) -> EnrichmentResult:
        """
        Orchestrate enrichment for a bookmark.

        Args:
            url: Bookmark URL
            bookmark_id: Bookmark ID
            tenant_id: Tenant ID

        Returns:
            EnrichmentResult with merged data from all enrichers

        Raises:
            Exception if required enrichers fail
        """
        # Step 1: Detect resource type
        resource_type_info = await self.detector.detect_resource_type(url)

        # Step 2: Select applicable enrichers (with fallback)
        enrichers = self._select_enrichers(resource_type_info.primary_type)

        # Step 3: Run enrichers in parallel
        results = await self._execute_enrichers(
            enrichers, url, bookmark_id, tenant_id, resource_type_info.primary_type
        )

        # Step 4-5: Process results, merge data, and validate required enrichers
        merged_data = self._process_results(
            results, resource_type_info.primary_type.value
        )

        # Step 6: Build EnrichmentResult
        return self._build_enrichment_result(merged_data)

    def _process_results(
        self,
        results: List[EnricherResult],
        resource_type_value: str,
    ) -> Dict[str, Any]:
        """
        Process enricher results, merge data, and validate required enrichers.

        Args:
            results: List of enricher results
            resource_type_value: String value to include in merged data

        Returns:
            Merged data dictionary

        Raises:
            Exception: If any required enrichers failed
        """
        merged_data = {"resource_type": resource_type_value}
        required_failures = []

        for result in results:
            if not result.success:
                # Enricher failed (timeout, exception, or graceful failure)
                logger.warning(
                    f"Enricher {result.enricher.name} failed: {result.error} "
                    f"(execution_time: {result.execution_time_ms:.2f}ms)"
                )
                if result.enricher.required:
                    required_failures.append(result.enricher.name)

            else:
                # Success - merge data
                logger.info(
                    f"Enricher {result.enricher.name} succeeded "
                    f"(execution_time: {result.execution_time_ms:.2f}ms)"
                )
                merged_data.update(result.data)

        # Fail overall enrichment if required enrichers failed
        if required_failures:
            error_msg = f"Required enrichers failed: {', '.join(required_failures)}"
            logger.error(error_msg)
            raise Exception(error_msg)

        return merged_data

    def _build_enrichment_result(self, merged_data: Dict[str, Any]) -> EnrichmentResult:
        """
        Convert merged enricher data to EnrichmentResult schema.

        Args:
            merged_data: Dictionary with all enriched fields

        Returns:
            EnrichmentResult instance
        """
        # Filter to only fields that EnrichmentResult accepts
        # This allows enrichers to add extra fields without breaking the schema
        valid_fields = {
            k: v for k, v in merged_data.items() if k in EnrichmentResult.model_fields
        }
        return EnrichmentResult(**valid_fields)
