from pydantic import BaseModel, Field
from enum import Enum
from typing import Any, Dict
from datetime import datetime
from uuid import UUID, uuid4


class BookmarkEventType(str, Enum):
    """Types of bookmark events"""
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


class BookmarkEvent(BaseModel):
    """Schema for bookmark events published to Kafka"""

    event_id: UUID = Field(default_factory=uuid4, description="Unique event identifier")
    event_type: str = Field(..., description="Type of event (created/updated/deleted)")
    timestamp: datetime = Field(default_factory=lambda: datetime.utcnow(), description="Event timestamp in UTC")
    data: Dict[str, Any] = Field(..., description="Event payload with bookmark data")
    metadata: Dict[str, str] = Field(
        default_factory=lambda: {
            "service": "bookmark-service",
            "version": "1.0.0"
        },
        description="Event metadata"
    )

    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat()
        }

    def to_json_dict(self) -> Dict[str, Any]:
        """
        Convert event to JSON-serializable dictionary.

        Handles UUID and datetime serialization.
        """
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "metadata": self.metadata
        }
