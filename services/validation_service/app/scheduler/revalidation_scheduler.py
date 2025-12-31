"""Periodic revalidation scheduler using APScheduler."""

import logging
import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.config import get_settings
from app.validators import (
    URLValidator,
    ValidationRetryHandler,
    BookmarkUpdateRetryHandler,
    BookmarkServiceClient,
)
from app.kafka.producer import ValidationEventProducer
from app.kafka.schemas import ValidationCompletedEvent

logger = logging.getLogger(__name__)
settings = get_settings()


class RevalidationScheduler:
    """Scheduler for periodic URL revalidation."""

    def __init__(self, producer: ValidationEventProducer):
        self.scheduler = AsyncIOScheduler()
        self.producer = producer
        self.validator = URLValidator()
        self.bookmark_client = BookmarkServiceClient()
        self.running = False

    def start(self):
        """Start the scheduler."""
        if not settings.enable_scheduler:
            logger.info("Scheduler is disabled via ENABLE_SCHEDULER=false")
            return

        # Schedule periodic revalidation
        self.scheduler.add_job(
            func=self._revalidate_bookmarks,
            trigger=IntervalTrigger(hours=settings.revalidation_interval_hours),
            id="revalidate_bookmarks",
            name="Periodic bookmark revalidation",
            replace_existing=True,
            max_instances=1,  # Prevent overlapping runs
        )

        self.scheduler.start()
        self.running = True
        logger.info(
            f"Scheduler started: revalidation every {settings.revalidation_interval_hours} hours"
        )

    def stop(self):
        """Stop the scheduler."""
        if self.running:
            self.scheduler.shutdown(wait=True)
            self.running = False
            logger.info("Scheduler stopped")

    async def _revalidate_bookmarks(self):
        """
        Periodic task to revalidate bookmarks.

        Queries bookmarks that need revalidation and processes them in batches.
        """
        logger.info("Starting periodic revalidation...")

        try:
            # Fetch bookmarks needing validation
            # Note: This assumes bookmark service supports filtering by needs_validation
            bookmarks = await self.bookmark_client.get_bookmarks(
                needs_validation=True, limit=settings.revalidation_batch_size
            )

            if not bookmarks:
                logger.info("No bookmarks need revalidation")
                return

            logger.info(f"Revalidating {len(bookmarks)} bookmarks...")

            # Process bookmarks concurrently (but with a semaphore to limit concurrency)
            semaphore = asyncio.Semaphore(10)  # Max 10 concurrent validations

            async def validate_bookmark(bookmark_data):
                async with semaphore:
                    await self._validate_single_bookmark(bookmark_data)

            # Run validations concurrently
            await asyncio.gather(
                *[validate_bookmark(b) for b in bookmarks], return_exceptions=True
            )

            logger.info(f"Completed revalidation of {len(bookmarks)} bookmarks")

        except Exception as e:
            logger.error(f"Error during periodic revalidation: {e}", exc_info=True)

    async def _validate_single_bookmark(self, bookmark_data: dict):
        """
        Validate a single bookmark.

        Args:
            bookmark_data: Bookmark dictionary from API
        """
        try:
            bookmark_id = bookmark_data["id"]
            url = bookmark_data["url"]
            user_id = bookmark_data["user_id"]

            logger.debug(f"Revalidating bookmark {bookmark_id}: {url}")

            # Step 1: Validate URL with retry
            validation_result = await ValidationRetryHandler.validate_with_retry(
                self.validator, bookmark_id, url
            )

            # Step 2: Update bookmark via API with retry
            try:
                await BookmarkUpdateRetryHandler.update_with_retry(
                    self.bookmark_client, bookmark_id, str(user_id), validation_result
                )
            except Exception as e:
                logger.error(
                    f"Failed to update bookmark {bookmark_id} after retries: {e}"
                )
                # Continue to publish event even if update fails

            # Step 3: Publish validation.completed event
            validation_event = ValidationCompletedEvent(
                bookmark_id=bookmark_id,
                url=url,
                validation_status=validation_result.validation_status,
                validation_http_status=validation_result.http_status,
                validation_final_url=validation_result.final_url,
                validation_error_message=validation_result.error_message,
                validation_checked_at=validation_result.checked_at,
            )

            await self.producer.publish_validation_event(validation_event)

            logger.debug(
                f"Revalidated bookmark {bookmark_id}: "
                f"{validation_result.validation_status}"
            )

        except Exception as e:
            logger.error(
                f"Error revalidating bookmark {bookmark_data.get('id', 'unknown')}: {e}",
                exc_info=True,
            )
