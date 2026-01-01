import httpx
import logging
from uuid import UUID
from datetime import datetime
from app.schemas.validation import ValidationResult
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class URLValidator:
    """Validates URLs by making HTTP requests."""

    def __init__(self):
        self.timeout = httpx.Timeout(settings.validation_timeout_seconds)
        self.headers = {"User-Agent": settings.validation_user_agent}

    async def validate_url(self, bookmark_id: UUID, url: str) -> ValidationResult:
        """
        Validate URL with HTTP HEAD request, fallback to GET if needed.

        Validation Logic:
        1. Use HEAD request first (faster, no body download)
        2. Fallback to GET if HEAD returns 405 (Method Not Allowed)
        3. Follow redirects (max 5 hops)
        4. Accept 2xx status codes as valid
        5. Store final URL after redirects
        6. Handle network errors gracefully

        Args:
            bookmark_id: UUID of the bookmark being validated
            url: URL to validate

        Returns:
            ValidationResult with status, http_status, final_url, etc.
        """
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, follow_redirects=True, max_redirects=5
            ) as client:
                # Try HEAD first (lightweight, no body download)
                logger.info(f"Validating URL {url} for bookmark {bookmark_id}")
                response = await client.head(url, headers=self.headers)

                # Fallback to GET if HEAD not supported (405 Method Not Allowed)
                if response.status_code == 405:
                    logger.debug(f"HEAD not supported for {url}, falling back to GET")
                    response = await client.get(url, headers=self.headers)

                # Determine validation status based on HTTP status code
                if 200 <= response.status_code < 300:
                    validation_status = "valid"
                else:
                    validation_status = "invalid"

                # Check if URL was redirected
                final_url = str(response.url) if str(response.url) != url else None

                logger.info(
                    f"Validation result for {url}: {validation_status} "
                    f"(HTTP {response.status_code})"
                )

                return ValidationResult(
                    bookmark_id=bookmark_id,
                    url=url,
                    validation_status=validation_status,
                    http_status=response.status_code,
                    final_url=final_url,
                    error_message=None,
                    checked_at=datetime.utcnow(),
                )

        except httpx.TimeoutException as e:
            logger.warning(f"Timeout validating {url}: {str(e)}")
            return ValidationResult(
                bookmark_id=bookmark_id,
                url=url,
                validation_status="error",
                http_status=None,
                final_url=None,
                error_message=f"Request timeout after {settings.validation_timeout_seconds}s",
                checked_at=datetime.utcnow(),
            )

        except httpx.NetworkError as e:
            logger.warning(f"Network error validating {url}: {str(e)}")
            return ValidationResult(
                bookmark_id=bookmark_id,
                url=url,
                validation_status="error",
                http_status=None,
                final_url=None,
                error_message=f"Network error: {str(e)}",
                checked_at=datetime.utcnow(),
            )

        except Exception as e:
            logger.error(f"Unexpected error validating {url}: {str(e)}", exc_info=True)
            return ValidationResult(
                bookmark_id=bookmark_id,
                url=url,
                validation_status="error",
                http_status=None,
                final_url=None,
                error_message=f"Unexpected error: {str(e)}",
                checked_at=datetime.utcnow(),
            )
