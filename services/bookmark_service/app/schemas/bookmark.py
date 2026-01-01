from pydantic import (
    BaseModel,
    HttpUrl,
    Field,
    ConfigDict,
    field_validator,
)
from datetime import datetime
from uuid import UUID
from typing import Optional, Dict, Any


class BookmarkBase(BaseModel):
    """Base schema with common bookmark fields."""

    url: HttpUrl  # Pydantic validates URL format
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)

    @field_validator("url", mode="after")
    @classmethod
    def validate_url_scheme(cls, v: HttpUrl) -> HttpUrl:
        """Validate that URL uses only http or https schemes."""
        if v.scheme not in ("http", "https"):
            raise ValueError("URL must use http or https scheme")
        return v

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
    enrichments: Optional[Dict[str, Any]] = None
    resource_type: Optional[str] = Field(None, max_length=50)

    # Validation fields (populated by validation service)
    validation_status: Optional[str] = Field(None, max_length=20)
    validation_last_checked: Optional[datetime] = None
    validation_http_status: Optional[int] = None
    validation_final_url: Optional[str] = Field(None, max_length=2048)
    validation_error_message: Optional[str] = None

    @field_validator("url", mode="after")
    @classmethod
    def validate_url_scheme(cls, v: Optional[HttpUrl]) -> Optional[HttpUrl]:
        """Validate that URL uses only http or https schemes when provided."""
        if v is not None and v.scheme not in ("http", "https"):
            raise ValueError("URL must use http or https scheme")
        return v

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
    tenant_id: str
    created_time: datetime
    changed_time: datetime

    # Enrichment fields
    enrichments: Optional[Dict[str, Any]] = None
    resource_type: Optional[str] = None

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
    page: int
    page_size: int
    has_next: bool
