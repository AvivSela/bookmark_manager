"""Health check endpoint."""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: datetime


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for container orchestration."""
    return HealthResponse(
        status="healthy", service="validation-service", timestamp=datetime.utcnow()
    )
