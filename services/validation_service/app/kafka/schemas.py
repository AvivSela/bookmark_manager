"""Kafka event schemas for validation service."""

from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional


class BookmarkCreatedEvent(BaseModel):
    """Event schema for bookmark.created events consumed from Kafka."""

    event_id: UUID
    event_type: str = "bookmark.created"
    timestamp: datetime
    bookmark_id: UUID
    user_id: UUID
    url: str
    title: Optional[str] = None
    description: Optional[str] = None


class ValidationCompletedEvent(BaseModel):
    """Event schema for validation.completed events published to Kafka."""

    event_id: UUID = Field(default_factory=lambda: __import__("uuid").uuid4())
    event_type: str = "validation.completed"
    timestamp: datetime = Field(default_factory=lambda: datetime.utcnow())
    bookmark_id: UUID
    url: str
    validation_status: str  # 'valid', 'invalid', 'error'
    validation_http_status: Optional[int] = None
    validation_final_url: Optional[str] = None
    validation_error_message: Optional[str] = None
    validation_checked_at: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), UUID: lambda v: str(v)}
