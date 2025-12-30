from pydantic import (
    BaseModel,
    HttpUrl,
    Field,
    ConfigDict,
    field_validator,
    ValidationError,
)
from datetime import datetime
from uuid import UUID
from typing import Optional


class BookmarkBase(BaseModel):
    """Base schema with common bookmark fields."""

    url: HttpUrl  # Pydantic validates URL format
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)

    @field_validator("title", mode="after")
    @classmethod
    def title_must_not_be_empty(cls, v: str) -> str:
        """Validate that title is not empty or whitespace-only."""
        if v and not v.strip():
            raise ValueError("Title cannot be empty or whitespace-only")
        return v


class BookmarkCreate(BookmarkBase):
    """Request schema for creating bookmarks.

    Inherits all fields from BookmarkBase without modifications.
    This class exists to provide semantic clarity and allow for future
    create-specific validations or fields if needed.
    """


class BookmarkUpdate(BaseModel):
    """Request schema for updating bookmarks (all fields optional for partial updates)."""

    url: Optional[HttpUrl] = None
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)

    # Enrichment fields (populated by enrichment service)
    og_title: Optional[str] = Field(None, max_length=500)
    og_description: Optional[str] = Field(None, max_length=5000)
    og_image: Optional[str] = Field(None, max_length=2048)
    og_type: Optional[str] = Field(None, max_length=100)
    og_site_name: Optional[str] = Field(None, max_length=200)
    meta_description: Optional[str] = Field(None, max_length=5000)
    favicon_url: Optional[str] = Field(None, max_length=2048)

    # Validation fields (populated by validation service)
    validation_status: Optional[str] = Field(None, max_length=20)
    validation_last_checked: Optional[datetime] = None
    validation_http_status: Optional[int] = None
    validation_final_url: Optional[str] = Field(None, max_length=2048)
    validation_error_message: Optional[str] = None

    @field_validator("title", mode="after")
    @classmethod
    def title_must_not_be_empty(cls, v: Optional[str]) -> Optional[str]:
        """Validate that title is not empty or whitespace-only when provided."""
        if v is not None and v and not v.strip():
            raise ValueError("Title cannot be empty or whitespace-only")
        return v


class BookmarkResponse(BookmarkBase):
    """Response schema with all fields including timestamps."""

    id: UUID
    user_id: str
    created_time: datetime
    changed_time: datetime

    # Enrichment fields
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None
    og_type: Optional[str] = None
    og_site_name: Optional[str] = None
    meta_description: Optional[str] = None
    favicon_url: Optional[str] = None

    # Validation fields
    validation_status: Optional[str] = None
    validation_last_checked: Optional[datetime] = None
    validation_http_status: Optional[int] = None
    validation_final_url: Optional[str] = None
    validation_error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)  # Enable ORM mode


class BookmarkListResponse(BaseModel):
    """Paginated list response."""

    items: list[BookmarkResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
