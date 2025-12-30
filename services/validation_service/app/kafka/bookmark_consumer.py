"""Kafka consumer for bookmark.created events."""

import json
import logging
import asyncio
from uuid import UUID
from aiokafka import AIOKafkaConsumer
from app.config import get_settings
from app.kafka.schemas import BookmarkCreatedEvent, ValidationCompletedEvent
from app.kafka.producer import ValidationEventProducer
from app.validators import (
    URLValidator,
    ValidationRetryHandler,
    BookmarkUpdateRetryHandler,
    BookmarkServiceClient
)

logger = logging.getLogger(__name__)
settings = get_settings()


class BookmarkConsumer:
    """Kafka consumer for bookmark.created events."""

    def __init__(self, producer: ValidationEventProducer):
        self.bootstrap_servers = settings.kafka_bootstrap_servers
        self.topic = settings.kafka_topic
        self.group_id = settings.kafka_consumer_group
        self.consumer = None
        self.producer = producer
        self.validator = URLValidator()
        self.bookmark_client = BookmarkServiceClient()
        self.running = False

    async def start(self):
        """Start the Kafka consumer."""
        try:
            self.consumer = AIOKafkaConsumer(
                self.topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                auto_offset_reset=settings.kafka_auto_offset_reset,
                enable_auto_commit=True,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                session_timeout_ms=settings.kafka_session_timeout_ms,
                max_poll_records=settings.kafka_max_poll_records
            )
            await self.consumer.start()
            logger.info(
                f"Kafka consumer started for topic: {self.topic}, "
                f"group: {self.group_id}"
            )
            self.running = True
        except Exception as e:
            logger.error(f"Failed to start Kafka consumer: {e}")
            raise

    async def stop(self):
        """Stop the Kafka consumer."""
        self.running = False
        if self.consumer:
            try:
                await self.consumer.stop()
                logger.info("Kafka consumer stopped")
            except Exception as e:
                logger.error(f"Error stopping Kafka consumer: {e}")

    async def consume(self):
        """
        Consume bookmark.created events and validate URLs.

        This method runs in a loop, processing events as they arrive.
        """
        if not self.consumer:
            raise RuntimeError("Consumer not started. Call start() first.")

        logger.info("Starting to consume bookmark events...")

        try:
            async for message in self.consumer:
                if not self.running:
                    break

                try:
                    # Parse event
                    event_data = message.value
                    event = BookmarkCreatedEvent(**event_data)

                    logger.info(
                        f"Received bookmark.created event: "
                        f"bookmark_id={event.bookmark_id}, url={event.url}"
                    )

                    # Process the event
                    await self._process_bookmark_event(event)

                except Exception as e:
                    logger.error(
                        f"Error processing message from Kafka: {e}",
                        exc_info=True
                    )
                    # Continue processing other messages

        except asyncio.CancelledError:
            logger.info("Consumer cancelled, shutting down...")
        except Exception as e:
            logger.error(f"Fatal error in consumer loop: {e}", exc_info=True)
            raise

    async def _process_bookmark_event(self, event: BookmarkCreatedEvent):
        """
        Process a bookmark.created event by validating the URL.

        Args:
            event: BookmarkCreatedEvent to process
        """
        try:
            # Step 1: Validate URL with retry
            logger.info(f"Validating URL for bookmark {event.bookmark_id}: {event.url}")

            validation_result = await ValidationRetryHandler.validate_with_retry(
                self.validator,
                event.bookmark_id,
                event.url
            )

            logger.info(
                f"Validation completed for bookmark {event.bookmark_id}: "
                f"status={validation_result.validation_status}, "
                f"http_status={validation_result.http_status}"
            )

            # Step 2: Update bookmark via API with retry
            try:
                await BookmarkUpdateRetryHandler.update_with_retry(
                    self.bookmark_client,
                    event.bookmark_id,
                    str(event.user_id),
                    validation_result
                )
                logger.info(f"Updated bookmark {event.bookmark_id} via API")

            except Exception as e:
                logger.error(
                    f"Failed to update bookmark {event.bookmark_id} after retries: {e}"
                )
                # Continue to publish event even if update fails

            # Step 3: Publish validation.completed event
            validation_event = ValidationCompletedEvent(
                bookmark_id=event.bookmark_id,
                url=event.url,
                validation_status=validation_result.validation_status,
                validation_http_status=validation_result.http_status,
                validation_final_url=validation_result.final_url,
                validation_error_message=validation_result.error_message,
                validation_checked_at=validation_result.checked_at
            )

            await self.producer.publish_validation_event(validation_event)

            logger.info(
                f"Successfully processed bookmark {event.bookmark_id}: "
                f"{validation_result.validation_status}"
            )

        except Exception as e:
            logger.error(
                f"Error processing bookmark event {event.bookmark_id}: {e}",
                exc_info=True
            )
            raise
