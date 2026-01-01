from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type,
)
import httpx
import logging
from uuid import UUID
from app.config import get_settings
from app.enrichers.core.enrichment_orchestrator import EnrichmentOrchestrator

logger = logging.getLogger(__name__)
settings = get_settings()

# Retry on network errors and HTTP 5xx errors
RETRYABLE_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.NetworkError,
    httpx.HTTPStatusError,
)


def is_retryable_http_error(exception: Exception) -> bool:
    """Check if HTTP error is retryable (5xx status codes)."""
    if isinstance(exception, httpx.HTTPStatusError):
        return 500 <= exception.response.status_code < 600
    return isinstance(exception, RETRYABLE_EXCEPTIONS)


class EnrichmentRetryHandler:
    """Handle retry logic with exponential backoff."""

    @retry(
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        stop=stop_after_attempt(settings.enrichment_max_attempts),
        wait=wait_random_exponential(
            multiplier=settings.enrichment_backoff_multiplier,
            min=settings.enrichment_initial_retry_delay,
            max=settings.enrichment_max_retry_delay,
        ),
        reraise=True,
    )
    async def enrich_with_retry(
        self,
        orchestrator: EnrichmentOrchestrator,
        url: str,
        bookmark_id: str,
        tenant_id: str,
    ):
        """
        Enrich bookmark with retry logic using orchestrator.

        Args:
            orchestrator: EnrichmentOrchestrator instance
            url: Bookmark URL
            bookmark_id: Bookmark ID
            tenant_id: Tenant ID

        Returns:
            EnrichmentResult

        Raises:
            - Original exception after max retries exhausted
            - Immediately on 4xx errors (client errors, no retry)
        """
        try:
            return await orchestrator.enrich_bookmark(url, bookmark_id, tenant_id)
        except httpx.HTTPStatusError as e:
            # Don't retry 4xx errors (client errors)
            if 400 <= e.response.status_code < 500:
                logger.warning(
                    f"Non-retryable HTTP error {e.response.status_code} for {url}"
                )
                raise
            # Retry 5xx errors
            logger.warning(f"Retrying after HTTP {e.response.status_code} for {url}")
            raise

    @retry(
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        stop=stop_after_attempt(settings.enrichment_max_attempts),
        wait=wait_random_exponential(
            multiplier=settings.enrichment_backoff_multiplier,
            min=settings.enrichment_initial_retry_delay,
            max=settings.enrichment_max_retry_delay,
        ),
        reraise=True,
    )
    async def update_with_retry(
        self, client, bookmark_id: UUID, tenant_id: str, enrichment_result
    ):
        """
        Update bookmark via API with retry logic.

        Args:
            client: BookmarkServiceClient instance
            bookmark_id: Bookmark UUID
            tenant_id: Tenant ID for authentication
            enrichment_result: EnrichmentResult with metadata

        Raises:
            - Original exception after max retries exhausted
            - Immediately on 4xx errors (client errors, no retry)
        """
        try:
            return await client.update_bookmark_enrichment(
                bookmark_id, tenant_id, enrichment_result
            )
        except httpx.HTTPStatusError as e:
            # Don't retry 4xx errors (client errors)
            if 400 <= e.response.status_code < 500:
                logger.warning(
                    f"Non-retryable HTTP error {e.response.status_code} updating bookmark {bookmark_id}"
                )
                raise
            # Retry 5xx errors
            logger.warning(
                f"Retrying after HTTP {e.response.status_code} for bookmark {bookmark_id}"
            )
            raise
