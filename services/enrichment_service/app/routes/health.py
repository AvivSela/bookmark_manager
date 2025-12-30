from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging
from datetime import datetime, timezone, timedelta
from app.database import get_db

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    """
    Health check endpoint that verifies:
    - API is running
    - Database connection is alive
    - Kafka consumer is running and healthy
    """
    # Check database
    db_status = "connected"
    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar()
    except Exception as e:
        logger.error(
            "Health check failed - database connection error",
            extra={"error": str(e), "error_type": type(e).__name__},
            exc_info=True,
        )
        db_status = "disconnected"

    # Check Kafka consumer
    kafka_status = "unknown"
    consumer = getattr(request.app.state, "consumer", None)

    if consumer is None:
        kafka_status = "not_initialized"
    else:
        from app.consumers.bookmark_consumer import ConsumerStatus

        if consumer.status == ConsumerStatus.HEALTHY:
            # Additional check: ensure consumer polled recently (within 5 minutes)
            if consumer.last_successful_poll:
                time_since_poll = datetime.now(timezone.utc) - consumer.last_successful_poll
                if time_since_poll > timedelta(minutes=5):
                    kafka_status = "stale"
                else:
                    kafka_status = "connected"
            else:
                # Just started, no polls yet
                kafka_status = "connected"
        elif consumer.status == ConsumerStatus.STARTING:
            kafka_status = "starting"
        elif consumer.status == ConsumerStatus.NOT_STARTED:
            kafka_status = "not_started"
        elif consumer.status == ConsumerStatus.STOPPED:
            kafka_status = "stopped"
        else:  # UNHEALTHY
            kafka_status = "disconnected"
            if consumer.last_error:
                logger.error(
                    "Health check - Kafka consumer unhealthy",
                    extra={"error": consumer.last_error}
                )

    # Determine overall health
    overall_status = "healthy" if (db_status == "connected" and kafka_status == "connected") else "unhealthy"

    return {
        "status": overall_status,
        "database": db_status,
        "kafka": kafka_status,
        "service": "enrichment"
    }
