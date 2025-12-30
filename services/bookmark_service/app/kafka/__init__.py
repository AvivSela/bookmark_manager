"""
Kafka module for event-driven architecture.

Provides Kafka producer for publishing bookmark events
(created, updated, deleted) with best-effort delivery.
"""
import logging
from typing import Optional
from app.kafka.producer import KafkaEventProducer
from app.kafka.schemas import BookmarkEvent, BookmarkEventType

logger = logging.getLogger(__name__)

# Global producer instance
_kafka_producer: Optional[KafkaEventProducer] = None


async def init_kafka() -> None:
    """
    Initialize Kafka producer.

    Should be called during application startup (in lifespan context manager).
    Creates and starts the global Kafka producer instance.
    """
    global _kafka_producer

    try:
        from app.config import get_settings
        settings = get_settings()

        if not settings.kafka_enabled:
            logger.info("Kafka is disabled via configuration")
            return

        _kafka_producer = KafkaEventProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            topic_prefix=settings.kafka_topic_prefix,
            compression_type=settings.kafka_compression_type,
            max_retries=settings.kafka_max_retries,
            request_timeout_ms=settings.kafka_request_timeout_ms
        )

        await _kafka_producer.start()

    except Exception as e:
        logger.error(
            "Failed to initialize Kafka",
            extra={"error": str(e), "error_type": type(e).__name__},
            exc_info=True
        )
        # Don't raise - allow application to start without Kafka
        _kafka_producer = None


async def shutdown_kafka() -> None:
    """
    Shutdown Kafka producer.

    Should be called during application shutdown (in lifespan context manager).
    Gracefully stops the global Kafka producer instance.
    """
    global _kafka_producer

    if _kafka_producer is not None:
        await _kafka_producer.stop()
        _kafka_producer = None


async def get_kafka_producer() -> Optional[KafkaEventProducer]:
    """
    Dependency injection function for Kafka producer.

    Returns the global Kafka producer instance to be injected
    into route handlers via FastAPI's Depends().

    Returns:
        Optional[KafkaEventProducer]: Producer instance, or None if not initialized
    """
    return _kafka_producer


# Export public API
__all__ = [
    "KafkaEventProducer",
    "BookmarkEvent",
    "BookmarkEventType",
    "init_kafka",
    "shutdown_kafka",
    "get_kafka_producer"
]
