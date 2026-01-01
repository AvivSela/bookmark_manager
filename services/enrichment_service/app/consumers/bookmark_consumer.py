from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError
import json
import logging
from uuid import UUID
from enum import Enum
from datetime import datetime, timezone
from app.config import get_settings
from app.schemas.kafka_events import BookmarkEvent
from app.enrichers.retry_handler import EnrichmentRetryHandler
from app.enrichers.bookmark_service_client import BookmarkServiceClient
from app.enrichers.resource_type_detector import (
    ResourceTypeDetector,
    ResourceDetectorConfig,
)
from app.enrichers.enrichment_orchestrator import EnrichmentOrchestrator

logger = logging.getLogger(__name__)
settings = get_settings()


class ConsumerStatus(Enum):
    """Consumer health status states."""

    NOT_STARTED = "not_started"
    STARTING = "starting"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    STOPPED = "stopped"


class BookmarkEnrichmentConsumer:
    """Kafka consumer for bookmark.created events."""

    def __init__(self):
        self.consumer = None

        # Create resource type detector
        detector_config = ResourceDetectorConfig(
            enable_head_requests=settings.enable_resource_type_head_requests,
            head_request_timeout=settings.resource_type_head_timeout,
        )
        detector = ResourceTypeDetector(detector_config)

        # Create enrichment orchestrator
        orchestrator_config = {
            "enabled_enrichers": settings.enabled_enrichers_list,
            "enrichment_timeout_seconds": settings.enrichment_timeout_seconds,
            "max_parallel_enrichers": settings.max_parallel_enrichers,
        }
        self.orchestrator = EnrichmentOrchestrator(detector, orchestrator_config)

        self.retry_handler = EnrichmentRetryHandler()
        self.bookmark_client = BookmarkServiceClient()
        self.status = ConsumerStatus.NOT_STARTED
        self.last_error = None
        self.last_successful_poll = None

    async def start(self):
        """Start Kafka consumer and HTTP client."""
        self.status = ConsumerStatus.STARTING
        try:
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
            # Start bookmark service client for connection pooling
            await self.bookmark_client.start()
            self.status = ConsumerStatus.HEALTHY
            self.last_error = None
            logger.info(f"Started consumer for topic {settings.kafka_topic}")
        except Exception as e:
            self.status = ConsumerStatus.UNHEALTHY
            self.last_error = str(e)
            raise

    async def stop(self):
        """Stop Kafka consumer and HTTP client."""
        if self.consumer:
            await self.consumer.stop()
        # Close bookmark service client
        await self.bookmark_client.close()
        self.status = ConsumerStatus.STOPPED
        logger.info("Stopped consumer")

    async def consume_and_enrich(self):
        """Main consumer loop."""
        try:
            async for message in self.consumer:
                self.last_successful_poll = datetime.now(timezone.utc)
                try:
                    # Parse event
                    event = BookmarkEvent(**message.value)
                    logger.info(
                        f"Processing bookmark {event.data.get('id')} for tenant {event.data.get('tenant_id')}"
                    )

                    # Enrich with retry
                    await self._enrich_bookmark(event)

                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
                    # Continue processing next message (don't crash consumer)

        except KafkaError as e:
            self.status = ConsumerStatus.UNHEALTHY
            self.last_error = str(e)
            logger.error(f"Kafka error: {e}", exc_info=True)
            raise

    async def _enrich_bookmark(self, event: BookmarkEvent):
        """Enrich a single bookmark via Bookmark Service API."""
        try:
            # Extract event data
            url = event.data.get("url")
            bookmark_id = event.data.get("id")
            tenant_id = event.data.get("tenant_id")

            if not url or not bookmark_id or not tenant_id:
                logger.error(
                    f"Missing required fields in event: url={url}, id={bookmark_id}, tenant_id={tenant_id}"
                )
                return

            # Enrich using orchestrator
            enrichment_result = await self.retry_handler.enrich_with_retry(
                self.orchestrator, url, bookmark_id, tenant_id
            )

            # Update bookmark via API with retry
            await self.retry_handler.update_with_retry(
                self.bookmark_client, UUID(bookmark_id), tenant_id, enrichment_result
            )

            logger.info(f"Successfully enriched bookmark {bookmark_id}")

        except Exception as e:
            # Log error but continue processing (don't crash consumer)
            logger.error(f"Failed to enrich bookmark {event.data.get('id')}: {e}")
