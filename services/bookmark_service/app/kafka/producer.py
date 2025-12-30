import logging
import json
from typing import Dict, Any, Optional
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError, KafkaTimeoutError
from app.kafka.schemas import BookmarkEvent, BookmarkEventType

logger = logging.getLogger(__name__)


class KafkaEventProducer:
    """
    Async Kafka producer for publishing bookmark events.

    Features:
    - Async/await compatible with FastAPI
    - Best-effort delivery (logs errors, doesn't raise exceptions)
    - Structured logging for observability
    - Graceful error handling
    """

    def __init__(
        self,
        bootstrap_servers: str,
        topic_prefix: str,
        compression_type: str = "gzip",
        max_retries: int = 3,
        request_timeout_ms: int = 30000,
    ):
        """
        Initialize Kafka producer configuration.

        Args:
            bootstrap_servers: Kafka broker connection string
            topic_prefix: Prefix for topic names (e.g., 'bookmarks')
            compression_type: Compression algorithm ('gzip', 'lz4', 'snappy', or 'none')
            max_retries: Maximum number of retry attempts
            request_timeout_ms: Request timeout in milliseconds
        """
        self._bootstrap_servers = bootstrap_servers
        self._topic_prefix = topic_prefix
        self._compression_type = compression_type
        self._max_retries = max_retries
        self._request_timeout_ms = request_timeout_ms
        self._producer: Optional[AIOKafkaProducer] = None

    async def start(self) -> None:
        """
        Initialize and start the Kafka producer.

        Creates AIOKafkaProducer instance and starts it.
        Should be called during application startup.
        """
        try:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self._bootstrap_servers,
                compression_type=self._compression_type,
                max_batch_size=16384,  # 16KB
                linger_ms=10,  # Wait up to 10ms to batch messages
                request_timeout_ms=self._request_timeout_ms,
                retry_backoff_ms=100,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            await self._producer.start()
            logger.info(
                "Kafka producer started successfully",
                extra={
                    "bootstrap_servers": self._bootstrap_servers,
                    "topic_prefix": self._topic_prefix,
                    "compression": self._compression_type,
                },
            )
        except Exception as e:
            logger.error(
                "Failed to start Kafka producer",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "bootstrap_servers": self._bootstrap_servers,
                },
                exc_info=True,
            )
            # Don't raise - allow application to start without Kafka
            self._producer = None

    async def stop(self) -> None:
        """
        Gracefully stop the Kafka producer.

        Flushes pending messages and closes the producer.
        Should be called during application shutdown.
        """
        if self._producer is not None:
            try:
                await self._producer.stop()
                logger.info("Kafka producer stopped gracefully")
            except Exception as e:
                logger.error(
                    "Error stopping Kafka producer",
                    extra={"error": str(e), "error_type": type(e).__name__},
                    exc_info=True,
                )

    async def publish_event(
        self,
        event_type: str,
        bookmark_data: Dict[str, Any],
        additional_metadata: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Publish a bookmark event to Kafka.

        Best-effort delivery: logs errors but doesn't raise exceptions.
        This ensures database operations succeed even if Kafka is unavailable.

        Args:
            event_type: Type of event ('created', 'updated', 'deleted')
            bookmark_data: Bookmark data to include in event payload
            additional_metadata: Optional additional metadata to include

        Returns:
            bool: True if publish succeeded, False otherwise
        """
        # If producer is not initialized, log warning and return False
        if self._producer is None:
            logger.warning(
                "Kafka producer not initialized - skipping event publish",
                extra={
                    "event_type": event_type,
                    "bookmark_id": bookmark_data.get("id"),
                },
            )
            return False

        try:
            # Create event with metadata
            event_metadata = {"service": "bookmark-service", "version": "1.0.0"}
            if additional_metadata:
                event_metadata.update(additional_metadata)

            # Create BookmarkEvent
            event = BookmarkEvent(
                event_type=event_type, data=bookmark_data, metadata=event_metadata
            )

            # Determine topic name
            topic = f"{self._topic_prefix}.bookmark.{event_type}"

            # Use bookmark ID as partition key for ordering
            partition_key = bookmark_data.get("id", "")
            if isinstance(partition_key, str):
                partition_key_bytes = partition_key.encode("utf-8")
            else:
                partition_key_bytes = str(partition_key).encode("utf-8")

            # Publish to Kafka
            await self._producer.send_and_wait(
                topic=topic, value=event.to_json_dict(), key=partition_key_bytes
            )

            logger.info(
                "Published Kafka event successfully",
                extra={
                    "event_id": str(event.event_id),
                    "event_type": event_type,
                    "bookmark_id": bookmark_data.get("id"),
                    "user_id": bookmark_data.get("user_id"),
                    "topic": topic,
                },
            )
            return True

        except KafkaTimeoutError as e:
            logger.error(
                "Kafka timeout - broker unreachable or slow",
                extra={
                    "event_type": event_type,
                    "bookmark_id": bookmark_data.get("id"),
                    "user_id": bookmark_data.get("user_id"),
                    "error": str(e),
                    "bootstrap_servers": self._bootstrap_servers,
                },
                exc_info=True,
            )
            return False

        except KafkaError as e:
            logger.error(
                "Kafka error during event publish",
                extra={
                    "event_type": event_type,
                    "bookmark_id": bookmark_data.get("id"),
                    "user_id": bookmark_data.get("user_id"),
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            return False

        except Exception as e:
            logger.exception(
                "Unexpected error publishing Kafka event",
                extra={
                    "event_type": event_type,
                    "bookmark_id": bookmark_data.get("id"),
                    "user_id": bookmark_data.get("user_id"),
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            return False
