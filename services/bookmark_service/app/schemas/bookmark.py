from pydantic import BaseModel, HttpUrl, Field, ConfigDict, field_validator, ValidationError
from datetime import datetime
from uuid import UUID
from typing import Optional


class BookmarkBase(BaseModel):
    """Base schema with common bookmark fields."""

    url: HttpUrl  # Pydantic validates URL format
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)

    @field_validator('title', mode='after')
    @classmethod
    def title_must_not_be_empty(cls, v: str) -> str:
        """Validate that title is not empty or whitespace-only."""
        if v and not v.strip():
            raise ValueError('Title cannot be empty or whitespace-only')
        return v


class BookmarkCreate(BookmarkBase):
    """Request schema for creating bookmarks."""

    pass


class BookmarkUpdate(BaseModel):
    """Request schema for updating bookmarks (all fields optional for partial updates)."""

    url: Optional[HttpUrl] = None
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)

    @field_validator('title', mode='after')
    @classmethod
    def title_must_not_be_empty(cls, v: Optional[str]) -> Optional[str]:
        """Validate that title is not empty or whitespace-only when provided."""
        if v is not None and v and not v.strip():
            raise ValueError('Title cannot be empty or whitespace-only')
        return v


class BookmarkResponse(BookmarkBase):
    """Response schema with all fields including timestamps."""

    id: UUID
    user_id: str
    created_time: datetime
    changed_time: datetime

    model_config = ConfigDict(from_attributes=True)  # Enable ORM mode


class BookmarkListResponse(BaseModel):
    """Paginated list response."""

    items: list[BookmarkResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
