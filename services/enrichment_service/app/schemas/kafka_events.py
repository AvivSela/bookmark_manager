from pydantic import BaseModel, ConfigDict
from typing import Dict, Any
from datetime import datetime
from uuid import UUID


class BookmarkEvent(BaseModel):
    """
    Kafka event schema matching bookmark_service producer.

    Topic: bookmarks.bookmark.created
    """
    event_id: UUID
    event_type: str  # "created", "updated", "deleted"
    timestamp: datetime
    data: Dict[str, Any]  # Contains bookmark data
    metadata: Dict[str, str]  # service, version

    model_config = ConfigDict()
