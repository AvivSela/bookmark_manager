from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError
import json
import logging
from uuid import UUID
from app.config import get_settings
from app.schemas.kafka_events import BookmarkEvent
from app.enrichers.metadata_fetcher import MetadataFetcher
from app.enrichers.retry_handler import EnrichmentRetryHandler
from app.enrichers.bookmark_service_client import BookmarkServiceClient

logger = logging.getLogger(__name__)
settings = get_settings()


class BookmarkEnrichmentConsumer:
    """Kafka consumer for bookmark.created events."""

    def __init__(self):
        self.consumer = None
        self.fetcher = MetadataFetcher()
        self.retry_handler = EnrichmentRetryHandler()
        self.bookmark_client = BookmarkServiceClient()

    async def start(self):
        """Start Kafka consumer."""
        self.consumer = AIOKafkaConsumer(
            settings.kafka_topic,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=settings.kafka_consumer_group,
            auto_offset_reset=settings.kafka_auto_offset_reset,
            session_timeout_ms=settings.kafka_session_timeout_ms,
            max_poll_records=settings.kafka_max_poll_records,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        await self.consumer.start()
        logger.info(f"Started consumer for topic {settings.kafka_topic}")

    async def stop(self):
        """Stop Kafka consumer."""
        if self.consumer:
            await self.consumer.stop()
            logger.info("Stopped consumer")

    async def consume_and_enrich(self):
        """Main consumer loop."""
        try:
            async for message in self.consumer:
                try:
                    # Parse event
                    event = BookmarkEvent(**message.value)
                    logger.info(
                        f"Processing bookmark {event.data.get('id')} for user {event.data.get('user_id')}"
                    )

                    # Enrich with retry
                    await self._enrich_bookmark(event)

                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
                    # Continue processing next message (don't crash consumer)

        except KafkaError as e:
            logger.error(f"Kafka error: {e}", exc_info=True)
            raise

    async def _enrich_bookmark(self, event: BookmarkEvent):
        """Enrich a single bookmark via Bookmark Service API."""
        try:
            # Extract event data
            url = event.data.get("url")
            bookmark_id = event.data.get("id")
            user_id = event.data.get("user_id")

            if not url or not bookmark_id or not user_id:
                logger.error(
                    f"Missing required fields in event: url={url}, id={bookmark_id}, user_id={user_id}"
                )
                return

            # Fetch metadata with retry
            enrichment_result = await self.retry_handler.fetch_with_retry(
                self.fetcher, url
            )

            # Update bookmark via API with retry
            await self.retry_handler.update_with_retry(
                self.bookmark_client, UUID(bookmark_id), user_id, enrichment_result
            )

            logger.info(f"Successfully enriched bookmark {bookmark_id}")

        except Exception as e:
            # Log error but continue processing (don't crash consumer)
            logger.error(f"Failed to enrich bookmark {event.data.get('id')}: {e}")
