"""API routes package."""

from app.routes.health import router as health_router
from app.routes.validation import router as validation_router

__all__ = ["health_router", "validation_router"]
