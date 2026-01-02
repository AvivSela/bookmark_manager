"""Kafka integration for validation service."""

from app.kafka.bookmark_consumer import BookmarkConsumer
from app.kafka.producer import ValidationEventProducer
from app.kafka.schemas import BookmarkCreatedEvent, ValidationCompletedEvent

__all__ = [
    "ValidationEventProducer",
    "BookmarkConsumer",
    "BookmarkCreatedEvent",
    "ValidationCompletedEvent",
]
