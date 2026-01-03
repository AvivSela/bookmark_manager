from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.metrics import setup_metrics
from app.routes import health

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - minimal startup/shutdown."""
    # No startup tasks needed - consumer handles its own lifecycle
    yield
    # No shutdown tasks needed - consumer handles its own cleanup


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Bookmark Enrichment Service - Health Check API",
    lifespan=lifespan,
    root_path="/api/v1/enrichment",
    docs_url=None,  # Disable swagger UI for minimal footprint
    redoc_url=None,  # Disable redoc UI for minimal footprint
)

# Setup Prometheus metrics
setup_metrics(app, settings.app_name, settings.app_version)

# Include health router
app.include_router(health.router)


# Root endpoint
@app.get("/")
async def root() -> dict[str, str]:
    """Service information endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "Bookmark enrichment service",
        "health": "/health",
    }
