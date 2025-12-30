import httpx
import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ValidationRetryHandler:
    """Handle retry logic for validation operations."""

    @staticmethod
    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(settings.validation_max_attempts),
        wait=wait_exponential(
            multiplier=settings.validation_backoff_multiplier,
            min=settings.validation_initial_retry_delay,
            max=settings.validation_max_retry_delay
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def validate_with_retry(validator, bookmark_id, url):
        """
        Validate URL with retry on transient errors.

        Retries on:
        - httpx.TimeoutException
        - httpx.NetworkError

        Does NOT retry on:
        - HTTP 4xx errors (client errors)
        - Other exceptions

        Args:
            validator: URLValidator instance
            bookmark_id: UUID of bookmark
            url: URL to validate

        Returns:
            ValidationResult
        """
        return await validator.validate_url(bookmark_id, url)


class BookmarkUpdateRetryHandler:
    """Handle retry logic for bookmark service API calls."""

    @staticmethod
    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError)),
        stop=stop_after_attempt(5),  # More retries for API updates
        wait=wait_exponential(
            multiplier=2.0,
            min=1.0,
            max=60.0
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        retry_error_callback=lambda retry_state: logger.error(
            f"Failed to update bookmark after {retry_state.attempt_number} attempts"
        )
    )
    async def update_with_retry(client, bookmark_id, user_id, validation_result):
        """
        Update bookmark via API with retry.

        Retries on:
        - httpx.TimeoutException
        - httpx.NetworkError
        - httpx.HTTPStatusError (for 5xx errors)

        Args:
            client: BookmarkServiceClient instance
            bookmark_id: UUID of bookmark
            user_id: User ID for authentication
            validation_result: ValidationResult to update

        Returns:
            Response from bookmark service
        """
        return await client.update_bookmark_validation(
            bookmark_id, user_id, validation_result
        )
