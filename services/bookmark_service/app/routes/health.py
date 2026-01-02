import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """
    Health check endpoint that verifies:
    - API is running
    - Database connection is alive
    """
    try:
        # Test database connection
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        # Log the detailed error server-side
        logger.error(
            "Health check failed - database connection error",
            extra={"error": str(e), "error_type": type(e).__name__},
            exc_info=True,
        )
        # Return generic error to client (no sensitive information)
        return {"status": "unhealthy", "database": "disconnected"}
