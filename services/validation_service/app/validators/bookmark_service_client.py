import httpx
import logging
from uuid import UUID
from typing import Optional, List, Dict, Any
from app.schemas.validation import ValidationResult
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class BookmarkServiceClient:
    """Client for interacting with the bookmark service API."""

    def __init__(self):
        self.base_url = settings.bookmark_service_url
        self.timeout = httpx.Timeout(settings.bookmark_service_timeout_seconds)

    async def get_bookmarks(
        self,
        needs_validation: bool = True,
        limit: int = 100,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query bookmarks from bookmark service.

        Args:
            needs_validation: Filter for bookmarks needing validation
            limit: Maximum number of bookmarks to return
            user_id: Optional user ID for filtering (if None, queries all bookmarks)

        Returns:
            List of bookmark dictionaries

        Raises:
            httpx.HTTPStatusError: For HTTP errors
            httpx.TimeoutException: For timeout errors
            httpx.NetworkError: For network errors
        """
        url = f"{self.base_url}/bookmarks"
        params = {"limit": limit}

        if needs_validation:
            params["needs_validation"] = "true"

        headers = {}
        if user_id:
            headers["X-User-ID"] = user_id

        logger.info(f"Fetching bookmarks from {url} with params {params}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()

            data = response.json()
            bookmarks = data.get("bookmarks", [])

            logger.info(f"Retrieved {len(bookmarks)} bookmarks from bookmark service")
            return bookmarks

    async def get_bookmark(
        self, bookmark_id: UUID, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch a single bookmark by ID.

        Args:
            bookmark_id: UUID of the bookmark
            user_id: User ID for authentication

        Returns:
            Bookmark dictionary or None if not found

        Raises:
            httpx.HTTPStatusError: For HTTP errors (except 404)
            httpx.TimeoutException: For timeout errors
            httpx.NetworkError: For network errors
        """
        url = f"{self.base_url}/bookmarks/{bookmark_id}"
        headers = {"X-User-ID": user_id}

        logger.info(f"Fetching bookmark {bookmark_id} from {url}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=headers)

            # Return None for 404, raise for other errors
            if response.status_code == 404:
                logger.warning(f"Bookmark {bookmark_id} not found")
                return None

            response.raise_for_status()

            bookmark = response.json()
            logger.info(f"Retrieved bookmark {bookmark_id}")
            return bookmark

    async def update_bookmark_validation(
        self, bookmark_id: UUID, user_id: str, validation_result: ValidationResult
    ) -> Dict[str, Any]:
        """
        Update bookmark validation fields via PATCH request.

        Args:
            bookmark_id: UUID of the bookmark to update
            user_id: User ID for authentication
            validation_result: ValidationResult with updated fields

        Returns:
            Updated bookmark dictionary

        Raises:
            httpx.HTTPStatusError: For HTTP errors
            httpx.TimeoutException: For timeout errors
            httpx.NetworkError: For network errors
        """
        url = f"{self.base_url}/bookmarks/{bookmark_id}"
        headers = {"X-User-ID": user_id}

        # Prepare payload with validation fields
        payload = {
            "validation_status": validation_result.validation_status,
            "validation_last_checked": validation_result.checked_at.isoformat(),
            "validation_http_status": validation_result.http_status,
            "validation_final_url": validation_result.final_url,
            "validation_error_message": validation_result.error_message,
        }

        logger.info(
            f"Updating bookmark {bookmark_id} validation: "
            f"status={validation_result.validation_status}, "
            f"http_status={validation_result.http_status}"
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.patch(url, json=payload, headers=headers)
            response.raise_for_status()

            updated_bookmark = response.json()
            logger.info(f"Successfully updated bookmark {bookmark_id}")
            return updated_bookmark
