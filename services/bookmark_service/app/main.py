from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from contextlib import asynccontextmanager
import logging
import uuid
from app.config import get_settings
from app.database import init_db
from app.routes import bookmarks, health
from app.kafka import init_kafka, shutdown_kafka

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - runs on startup and shutdown."""
    # Startup: Validate configuration
    settings = get_settings()  # This will fail early if required configs are missing

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
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle validation errors with detailed error messages.

    Transforms Pydantic validation errors into properly formatted HTTP 400 responses
    with detailed field-level error information.
    """
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


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request, exc: HTTPException
) -> JSONResponse:
    """Handle HTTP exceptions with structured logging and request correlation.

    Logs HTTP exceptions with context (request ID, method, path, status code)
    and includes X-Request-ID header in error responses for request tracing.
    """
    # Get request ID from middleware
    request_id = getattr(request.state, "request_id", "unknown")

    # Log with appropriate level based on status code
    log_message = (
        f"HTTP exception: status_code={exc.status_code} "
        f"detail={exc.detail} path={request.url.path} "
        f"method={request.method} request_id={request_id}"
    )

    if exc.status_code >= 500:
        logger.error(log_message)
    else:
        logger.warning(log_message)

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={"X-Request-ID": request_id}
    )


@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Handle all unexpected exceptions with generic error message."""
    # Get request ID if available
    request_id = getattr(request.state, "request_id", None)

    # Log detailed error server-side with structured logging
    logger.error(
        "Unexpected error occurred",
        extra={
            "error": str(exc),
            "error_type": type(exc).__name__,
            "path": request.url.path,
            "method": request.method,
            "request_id": request_id,
        },
        exc_info=True,
    )

    # Return generic error to client (no sensitive information)
    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Please try again later."}
    )

    # Add request ID to error response
    if request_id:
        response.headers["X-Request-ID"] = request_id

    return response


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
