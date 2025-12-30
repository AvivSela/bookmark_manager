"""Main application entry point for validation service."""

import asyncio
import logging
import signal
from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn

from app.config import get_settings
from app.kafka import ValidationEventProducer, BookmarkConsumer
from app.scheduler import RevalidationScheduler
from app.validators import URLValidator, BookmarkServiceClient
from app.routes import health_router, validation_router
from app.routes.validation import set_dependencies

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Global references for cleanup
producer: ValidationEventProducer = None
consumer: BookmarkConsumer = None
scheduler: RevalidationScheduler = None
consumer_task: asyncio.Task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.

    Startup:
    - Initialize Kafka producer
    - Initialize Kafka consumer
    - Optionally start scheduler
    - Start consuming events

    Shutdown:
    - Stop consumer
    - Stop scheduler
    - Stop producer
    """
    global producer, consumer, scheduler, consumer_task

    logger.info("Starting Bookmark Validation Service...")

    try:
        # Initialize components
        producer = ValidationEventProducer()
        await producer.start()
        logger.info("✓ Kafka producer started")

        consumer = BookmarkConsumer(producer)
        await consumer.start()
        logger.info("✓ Kafka consumer started")

        # Start consuming in background
        consumer_task = asyncio.create_task(consumer.consume())
        logger.info("✓ Consumer task started")

        # Initialize scheduler (only if enabled)
        scheduler = RevalidationScheduler(producer)
        scheduler.start()  # This checks ENABLE_SCHEDULER internally
        if settings.enable_scheduler:
            logger.info("✓ Scheduler started")
        else:
            logger.info("✓ Scheduler disabled (ENABLE_SCHEDULER=false)")

        # Set dependencies for route handlers
        validator = URLValidator()
        bookmark_client = BookmarkServiceClient()
        set_dependencies(validator, bookmark_client, producer)
        logger.info("✓ Route dependencies configured")

        logger.info("🚀 Validation service is ready!")

        yield

    finally:
        # Shutdown sequence
        logger.info("Shutting down Bookmark Validation Service...")

        # Stop consumer
        if consumer:
            await consumer.stop()
            logger.info("✓ Consumer stopped")

        # Cancel consumer task
        if consumer_task and not consumer_task.done():
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass
            logger.info("✓ Consumer task cancelled")

        # Stop scheduler
        if scheduler:
            scheduler.stop()
            logger.info("✓ Scheduler stopped")

        # Stop producer
        if producer:
            await producer.stop()
            logger.info("✓ Producer stopped")

        logger.info("👋 Validation service shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan
)

# Register routes
app.include_router(health_router)
app.include_router(validation_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running"
    }


def handle_shutdown_signal(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    # FastAPI/uvicorn will handle the actual shutdown via lifespan


if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGTERM, handle_shutdown_signal)
    signal.signal(signal.SIGINT, handle_shutdown_signal)

    # Run the application
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        log_level="info",
        access_log=True
    )
