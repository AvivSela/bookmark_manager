from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from typing import Optional


class ValidationResult(BaseModel):
    """Result of a URL validation check."""

    bookmark_id: UUID
    url: str
    validation_status: str  # 'valid', 'invalid', 'error'
    http_status: Optional[int] = None
    final_url: Optional[str] = None  # Final URL after following redirects
    error_message: Optional[str] = None
    checked_at: datetime = Field(default_factory=lambda: datetime.utcnow())


class ValidationResultResponse(BaseModel):
    """Response for single validation request."""

    result: ValidationResult


class BatchValidationResponse(BaseModel):
    """Response for batch validation request."""

    job_id: UUID
    total_bookmarks: int
    status: str  # 'queued', 'processing', 'completed'
