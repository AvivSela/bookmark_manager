"""Kafka producer for publishing validation events."""

import json
import logging
from typing import Optional

from aiokafka import AIOKafkaProducer

from app.config import get_settings
from app.kafka.schemas import ValidationCompletedEvent

logger = logging.getLogger(__name__)
settings = get_settings()


class ValidationEventProducer:
    """Kafka producer for validation completed events."""

    def __init__(self):
        self.bootstrap_servers = settings.kafka_bootstrap_servers
        self.topic = settings.kafka_validation_topic
        self.producer: Optional[AIOKafkaProducer] = None

    async def start(self):
        """Start the Kafka producer."""
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                compression_type="gzip",
            )
            await self.producer.start()
            logger.info("Kafka producer started for topic: %s", self.topic)
        except Exception as e:
            logger.error("Failed to start Kafka producer: %s", e)
            raise

    async def stop(self):
        """Stop the Kafka producer."""
        if self.producer:
            try:
                await self.producer.stop()
                logger.info("Kafka producer stopped")
            except Exception as e:
                logger.error("Error stopping Kafka producer: %s", e)

    async def publish_validation_event(self, event: ValidationCompletedEvent):
        """
        Publish a validation completed event to Kafka.

        Args:
            event: ValidationCompletedEvent to publish

        Raises:
            Exception: If publishing fails
        """
        if not self.producer:
            raise RuntimeError("Producer not started. Call start() first.")

        try:
            # Convert Pydantic model to dict for serialization
            event_dict = event.model_dump(mode="json")

            # Send to Kafka
            await self.producer.send_and_wait(
                topic=self.topic,
                value=event_dict,
                key=str(event.bookmark_id).encode("utf-8"),
            )

            logger.info(
                "Published validation event for bookmark %s: status=%s, http_status=%s",
                event.bookmark_id,
                event.validation_status,
                event.validation_http_status,
            )

        except Exception as e:
            logger.error(
                "Failed to publish validation event for bookmark %s: %s",
                event.bookmark_id,
                e,
            )
            raise
