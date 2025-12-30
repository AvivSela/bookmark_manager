from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.config import get_settings
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
    docs_url=None,  # Disable swagger UI for minimal footprint
    redoc_url=None,  # Disable redoc UI for minimal footprint
)

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
