import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError

from app.config import get_settings
from app.database import init_db
from app.kafka import init_kafka, shutdown_kafka
from app.logging_config import setup_json_logging
from app.metrics import HTTP_REQUESTS_TOTAL, collect_db_pool_metrics, setup_metrics
from app.routes import bookmarks, health
from app.validation_exception_handler import (
    global_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)

settings = get_settings()

# Setup structured JSON logging
setup_json_logging(service_name="bookmark-service", log_level="INFO")
logger = logging.getLogger(__name__)

# Background task for metrics collection
_metrics_task = None


async def collect_metrics_periodically():
    """Collect database pool metrics every 15 seconds."""
    while True:
        try:
            await collect_db_pool_metrics()
            await asyncio.sleep(15)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Error collecting metrics: %s", e, exc_info=True)
            await asyncio.sleep(15)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - runs on startup and shutdown."""
    global _metrics_task

    # Initialize database and Kafka
    await init_db()
    await init_kafka()

    # Start metrics collection task
    _metrics_task = asyncio.create_task(collect_metrics_periodically())

    yield

    # Shutdown: Stop metrics collection and cleanup
    if _metrics_task:
        _metrics_task.cancel()
        try:
            await _metrics_task
        except asyncio.CancelledError:
            pass

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
    root_path="/api/v1/bookmarks",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc UI
)

# Setup Prometheus metrics
setup_metrics(app, settings.app_name, settings.app_version)


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    method = request.method
    path = request.url.path
    service_name = "bookmark-service" # You can also pull this from an env var
    
    # Start timer
    start_time = time.time()
    
    # Process the request
    response = await call_next(request)
    
    # 2. Record Metrics in ONE place
    duration = time.time() - start_time
    HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=path, service=service_name).inc()
    
    return response

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
