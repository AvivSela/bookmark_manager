from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from app.config import get_settings
from app.database import init_db
from app.routes import bookmarks, health
from app.kafka import init_kafka, shutdown_kafka

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - runs on startup and shutdown."""
    # Startup: Initialize database and Kafka
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

    **Authentication**: All bookmark endpoints require the X-User-ID header.
    Each user maintains their own isolated collection of bookmarks.
    Multiple users can bookmark the same URL without conflicts.
    """,
    lifespan=lifespan,
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc UI
)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle validation errors with detailed error messages."""
    # Convert errors to JSON-serializable format
    errors = []
    for error in exc.errors():
        error_dict = {
            "loc": list(error.get("loc", [])),
            "msg": str(error.get("msg", "")),
            "type": str(error.get("type", "")),
        }
        # Add input if it exists
        if "input" in error:
            error_dict["input"] = str(error["input"])
        errors.append(error_dict)

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST, content={"detail": errors}
    )


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
