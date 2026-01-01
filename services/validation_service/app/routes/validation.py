"""Validation API endpoints."""

import logging
import asyncio
from uuid import UUID
from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from app.schemas.validation import (
    ValidationResultResponse,
    BatchValidationResponse,
)
from app.validators import (
    URLValidator,
    ValidationRetryHandler,
    BookmarkUpdateRetryHandler,
    BookmarkServiceClient,
)
from app.kafka.producer import ValidationEventProducer
from app.kafka.schemas import ValidationCompletedEvent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/validate", tags=["validation"])

# Shared instances (will be set during app startup)
_validator: Optional[URLValidator] = None
_bookmark_client: Optional[BookmarkServiceClient] = None
_producer: Optional[ValidationEventProducer] = None


def set_dependencies(
    validator: URLValidator,
    client: BookmarkServiceClient,
    producer: ValidationEventProducer,
):
    """Set shared dependencies for route handlers."""
    global _validator, _bookmark_client, _producer
    _validator = validator
    _bookmark_client = client
    _producer = producer


@router.post("/{bookmark_id}", response_model=ValidationResultResponse)
async def validate_bookmark(
    bookmark_id: UUID, x_user_id: str = Header(..., alias="X-User-ID")
):
    """
    Validate a specific bookmark on-demand.

    Args:
        bookmark_id: UUID of the bookmark to validate
        x_user_id: User ID from header for authentication

    Returns:
        ValidationResultResponse with validation status
    """
    if not _validator or not _bookmark_client or not _producer:
        raise HTTPException(status_code=503, detail="Service not ready")

    try:
        # Fetch bookmark from API
        bookmark = await _bookmark_client.get_bookmark(bookmark_id, x_user_id)

        if not bookmark:
            raise HTTPException(status_code=404, detail="Bookmark not found")

        url = bookmark["url"]
        logger.info(f"On-demand validation for bookmark {bookmark_id}: {url}")

        # Validate URL with retry
        validation_result = await ValidationRetryHandler.validate_with_retry(
            _validator, bookmark_id, url
        )

        # Update bookmark via API with retry
        try:
            await BookmarkUpdateRetryHandler.update_with_retry(
                _bookmark_client, bookmark_id, x_user_id, validation_result
            )
        except Exception as e:
            logger.error(f"Failed to update bookmark {bookmark_id}: {e}")
            # Continue even if update fails

        # Publish validation event
        validation_event = ValidationCompletedEvent(
            bookmark_id=bookmark_id,
            url=url,
            validation_status=validation_result.validation_status,
            validation_http_status=validation_result.http_status,
            validation_final_url=validation_result.final_url,
            validation_error_message=validation_result.error_message,
            validation_checked_at=validation_result.checked_at,
        )

        await _producer.publish_validation_event(validation_event)

        return ValidationResultResponse(
            success=True, validation_result=validation_result
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating bookmark {bookmark_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.post("/revalidate-all", response_model=BatchValidationResponse)
async def revalidate_all(
    limit: int = 100, x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """
    Trigger revalidation of all bookmarks needing validation.

    This endpoint is available regardless of whether the scheduler is enabled.

    Args:
        limit: Maximum number of bookmarks to revalidate (default: 100)
        x_user_id: Optional user ID to filter bookmarks

    Returns:
        BatchValidationResponse with results
    """
    if not _validator or not _bookmark_client or not _producer:
        raise HTTPException(status_code=503, detail="Service not ready")

    try:
        # Fetch bookmarks needing validation
        bookmarks = await _bookmark_client.get_bookmarks(
            needs_validation=True, limit=limit, user_id=x_user_id
        )

        if not bookmarks:
            return BatchValidationResponse(
                success=True, total_processed=0, successful=0, failed=0, results=[]
            )

        logger.info(f"Manual revalidation triggered for {len(bookmarks)} bookmarks")

        # Process bookmarks with concurrency control
        semaphore = asyncio.Semaphore(10)  # Max 10 concurrent validations
        results = []
        successful = 0
        failed = 0

        async def validate_bookmark_task(bookmark_data):
            nonlocal successful, failed
            async with semaphore:
                try:
                    bookmark_id = bookmark_data["id"]
                    url = bookmark_data["url"]
                    user_id = str(bookmark_data["user_id"])

                    # Validate URL
                    validation_result = (
                        await ValidationRetryHandler.validate_with_retry(
                            _validator, bookmark_id, url
                        )
                    )

                    # Update bookmark
                    try:
                        await BookmarkUpdateRetryHandler.update_with_retry(
                            _bookmark_client, bookmark_id, user_id, validation_result
                        )
                    except Exception as e:
                        logger.error(f"Failed to update bookmark {bookmark_id}: {e}")

                    # Publish event
                    validation_event = ValidationCompletedEvent(
                        bookmark_id=bookmark_id,
                        url=url,
                        validation_status=validation_result.validation_status,
                        validation_http_status=validation_result.http_status,
                        validation_final_url=validation_result.final_url,
                        validation_error_message=validation_result.error_message,
                        validation_checked_at=validation_result.checked_at,
                    )

                    await _producer.publish_validation_event(validation_event)

                    successful += 1
                    return validation_result

                except Exception as e:
                    logger.error(
                        f"Error validating bookmark {bookmark_data.get('id')}: {e}"
                    )
                    failed += 1
                    return None

        # Run validations concurrently
        validation_results = await asyncio.gather(
            *[validate_bookmark_task(b) for b in bookmarks], return_exceptions=True
        )

        # Filter out None results
        results = [r for r in validation_results if r is not None]

        return BatchValidationResponse(
            success=True,
            total_processed=len(bookmarks),
            successful=successful,
            failed=failed,
            results=results,
        )

    except Exception as e:
        logger.error(f"Error during batch revalidation: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Batch validation failed: {str(e)}"
        )


@router.get("/status")
async def validation_status():
    """Get validation service status."""
    from app.config import get_settings

    settings = get_settings()

    return {
        "service": "validation-service",
        "scheduler_enabled": settings.enable_scheduler,
        "revalidation_interval_hours": settings.revalidation_interval_hours,
        "validation_timeout_seconds": settings.validation_timeout_seconds,
        "max_attempts": settings.validation_max_attempts,
    }
