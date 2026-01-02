import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError

from app.config import get_settings
from app.database import init_db
from app.kafka import init_kafka, shutdown_kafka
from app.routes import bookmarks, health
from app.validation_exception_handler import (
    global_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - runs on startup and shutdown."""
    # Initialize database and Kafka
    await init_db()
    await init_kafka()
    yield
    # Shutdown: Cleanup Kafka producer
    await shutdown_kafka()


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    REST API for managing bookmarks with full CRUD operations.

    **Authentication**: All bookmark endpoints require the X-Tenant-ID header.
    Each tenant maintains their own isolated collection of bookmarks.
    Multiple tenants can bookmark the same URL without conflicts.
    """,
    lifespan=lifespan,
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc UI
)


# Middleware
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Add X-Request-ID header for request correlation across services."""
    # Get existing request ID or generate new one
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    # Store in request state for access in route handlers
    request.state.request_id = request_id

    # Process request
    response = await call_next(request)

    # Add request ID to response headers
    response.headers["X-Request-ID"] = request_id

    return response


# Exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, global_exception_handler)  # type: ignore[arg-type]

# Include routers
app.include_router(health.router)
app.include_router(bookmarks.router)


# Root endpoint
@app.get("/")
async def root() -> dict[str, str]:
    """API information endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "Bookmark management API",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }
